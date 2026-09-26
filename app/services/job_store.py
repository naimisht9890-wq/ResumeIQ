import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.models.schemas import (
    ATSScoreRequest,
    CoverLetterRequest,
    CreateJobRequest,
    JobDescriptionParsingJobPayload,
    JobStatusResult,
    RenderResumeRequest,
    ResumeParsingJobPayload,
    SkillGapAnalysisRequest,
    StrengthsWeaknessesRequest,
    TailorResumeRequest,
)
from app.services.sqlite_database import database_path


JOB_RETENTION_DAYS = 7

PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "ats_scoring": ATSScoreRequest,
    "cover_letter": CoverLetterRequest,
    "job_description_parsing": JobDescriptionParsingJobPayload,
    "rendering": RenderResumeRequest,
    "resume_parsing": ResumeParsingJobPayload,
    "skill_gap_analysis": SkillGapAnalysisRequest,
    "strengths_weaknesses": StrengthsWeaknessesRequest,
    "tailoring": TailorResumeRequest,
}
SUPPORTED_OPERATIONS = set(PAYLOAD_MODELS)


@dataclass(frozen=True)
class QueuedJob:
    job_id: str
    operation: str
    payload: dict[str, Any]


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")

    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('queued', 'running', 'completed', 'failed')
                ),
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS jobs_status_created_at
            ON jobs (status, created_at)
            """
        )
        connection.commit()
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_payload(
    operation: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_model = PAYLOAD_MODELS[operation]

    try:
        if hasattr(payload_model, "model_validate"):
            validated = payload_model.model_validate(payload)
        else:
            validated = payload_model.parse_obj(payload)
    except ValidationError as error:
        raise ValueError(
            f"Invalid payload for job operation '{operation}'."
        ) from error

    if hasattr(validated, "model_dump"):
        return validated.model_dump(mode="json")
    return validated.dict()


def create_job(request: CreateJobRequest) -> JobStatusResult:
    operation = request.operation.strip().lower()

    if operation not in SUPPORTED_OPERATIONS:
        supported = ", ".join(sorted(SUPPORTED_OPERATIONS))
        raise ValueError(
            f"Unsupported job operation: {operation}. "
            f"Supported operations: {supported}."
        )

    payload = _validate_payload(operation, request.payload)
    job_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_id, operation, payload_json, status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'queued', ?, ?)
            """,
            (job_id, operation, json.dumps(payload), now, now),
        )

    return JobStatusResult(
        job_id=job_id,
        operation=operation,
        status="queued",
    )


def get_job(job_id: str) -> JobStatusResult:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT job_id, operation, status, error, result_json
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"Job was not found: {job_id}")

    return JobStatusResult(
        job_id=row["job_id"],
        operation=row["operation"],
        status=row["status"],
        error=row["error"],
        result=(
            json.loads(row["result_json"])
            if row["result_json"] is not None
            else None
        ),
    )


def claim_next_job() -> QueuedJob | None:
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT job_id, operation, payload_json
            FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at, job_id
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        updated = connection.execute(
            """
            UPDATE jobs
            SET status = 'running', updated_at = ?, attempts = attempts + 1
            WHERE job_id = ? AND status = 'queued'
            """,
            (now, row["job_id"]),
        )

        if updated.rowcount != 1:
            return None

        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Stored payload for job {row['job_id']} is not an object."
            )

        return QueuedJob(
            job_id=row["job_id"],
            operation=row["operation"],
            payload=payload,
        )


def complete_job(job_id: str, result: Any) -> None:
    if isinstance(result, BaseModel):
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")
        else:
            result = result.dict()

    if not isinstance(result, dict):
        raise TypeError("A completed job result must be a JSON object.")

    now = datetime.now(timezone.utc).isoformat()
    with _connection() as connection:
        updated = connection.execute(
            """
            UPDATE jobs
            SET status = 'completed', result_json = ?, error = NULL,
                payload_json = '{}', updated_at = ?
            WHERE job_id = ? AND status = 'running'
            """,
            (json.dumps(result), now, job_id),
        )

    if updated.rowcount != 1:
        raise ValueError(f"Running job was not found: {job_id}")


def fail_job(job_id: str, error: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as connection:
        updated = connection.execute(
            """
            UPDATE jobs
            SET status = 'failed', error = ?, payload_json = '{}',
                updated_at = ?
            WHERE job_id = ? AND status = 'running'
            """,
            (error, now, job_id),
        )

    if updated.rowcount != 1:
        raise ValueError(f"Running job was not found: {job_id}")


def recover_interrupted_jobs() -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as connection:
        updated = connection.execute(
            """
            UPDATE jobs
            SET status = 'queued', updated_at = ?
            WHERE status = 'running'
            """,
            (now,),
        )
        return updated.rowcount


def purge_expired_jobs(retention_days: int = JOB_RETENTION_DAYS) -> int:
    if retention_days < 1:
        raise ValueError("Job retention must be at least one day.")

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=retention_days)
    ).isoformat()
    with _connection() as connection:
        deleted = connection.execute(
            """
            DELETE FROM jobs
            WHERE status IN ('completed', 'failed') AND updated_at < ?
            """,
            (cutoff,),
        )
        return deleted.rowcount
