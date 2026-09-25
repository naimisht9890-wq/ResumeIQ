from uuid import uuid4

from app.models.schemas import (
    CreateJobRequest,
    JobStatusResult,
)


_jobs: dict[str, JobStatusResult] = {}

SUPPORTED_OPERATIONS = {
    "resume_parsing",
    "ats_scoring",
    "tailoring",
    "cover_letter",
    "rendering",
}


def create_job(request: CreateJobRequest) -> JobStatusResult:
    operation = request.operation.strip().lower()

    if operation not in SUPPORTED_OPERATIONS:
        supported = ", ".join(sorted(SUPPORTED_OPERATIONS))
        raise ValueError(
            f"Unsupported job operation: {operation}. "
            f"Supported operations: {supported}."
        )

    job = JobStatusResult(
        job_id=str(uuid4()),
        operation=operation,
        status="queued",
    )
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> JobStatusResult:
    job = _jobs.get(job_id)

    if job is None:
        raise ValueError(f"Job was not found: {job_id}")

    return job
