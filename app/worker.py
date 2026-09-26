import argparse
import base64
import logging
import time
from typing import Any

from app.models.schemas import (
    ATSScoreRequest,
    CoverLetterRequest,
    JobDescriptionParsingJobPayload,
    RenderResumeRequest,
    ResumeParsingJobPayload,
    SkillGapAnalysisRequest,
    StrengthsWeaknessesRequest,
    TailorResumeRequest,
)
from app.services.ats_scoring import calculate_ats_score
from app.services.cover_letter_generator import generate_cover_letter
from app.services.feedback_generator import generate_grounded_feedback
from app.services.job_description_parser import parse_job_description_text
from app.services.job_store import (
    QueuedJob,
    claim_next_job,
    complete_job,
    fail_job,
    purge_expired_jobs,
    recover_interrupted_jobs,
)
from app.services.resume_extraction import extract_resume_text
from app.services.resume_parser import parse_resume_text
from app.services.resume_renderer import render_resume_docx
from app.services.skill_gap_analysis import analyze_skill_gap
from app.services.resume_tailoring import tailor_resume


LOGGER = logging.getLogger("resumeiq.worker")
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


def _validate_payload(
    payload: dict[str, Any],
    payload_type: type,
) -> Any:
    if hasattr(payload_type, "model_validate"):
        return payload_type.model_validate(payload)
    return payload_type.parse_obj(payload)


def execute_job(job: QueuedJob) -> Any:
    if job.operation == "resume_parsing":
        payload = _validate_payload(
            job.payload,
            ResumeParsingJobPayload,
        )
        try:
            file_bytes = base64.b64decode(
                payload.content_base64,
                validate=True,
            )
        except ValueError as error:
            raise ValueError(
                "Resume parsing payload contains invalid base64 content."
            ) from error
        text = extract_resume_text(payload.filename, file_bytes)
        return parse_resume_text(text)

    if job.operation == "job_description_parsing":
        payload = _validate_payload(
            job.payload,
            JobDescriptionParsingJobPayload,
        )
        return parse_job_description_text(payload.text)

    if job.operation == "ats_scoring":
        request = _validate_payload(job.payload, ATSScoreRequest)
        return calculate_ats_score(request)

    if job.operation == "skill_gap_analysis":
        request = _validate_payload(
            job.payload,
            SkillGapAnalysisRequest,
        )
        return analyze_skill_gap(request)

    if job.operation == "strengths_weaknesses":
        request = _validate_payload(
            job.payload,
            StrengthsWeaknessesRequest,
        )
        return generate_grounded_feedback(request)

    if job.operation == "tailoring":
        request = _validate_payload(job.payload, TailorResumeRequest)
        return tailor_resume(request)

    if job.operation == "cover_letter":
        request = _validate_payload(job.payload, CoverLetterRequest)
        return generate_cover_letter(request)

    if job.operation == "rendering":
        request = _validate_payload(job.payload, RenderResumeRequest)
        document = render_resume_docx(request.resume)
        return {
            "filename": "resume.docx",
            "content_type": DOCX_CONTENT_TYPE,
            "content_base64": base64.b64encode(document).decode("ascii"),
        }

    raise ValueError(f"Unsupported queued job operation: {job.operation}")


def run_one_job() -> bool:
    job = claim_next_job()
    if job is None:
        return False

    try:
        result = execute_job(job)
        complete_job(job.job_id, result)
    except Exception as error:
        LOGGER.exception(
            "Job %s (%s) failed.",
            job.job_id,
            job.operation,
        )
        fail_job(job.job_id, str(error))

    return True


def run_worker(
    poll_interval: float = 1.0,
    once: bool = False,
) -> None:
    if poll_interval <= 0:
        raise ValueError("Worker polling interval must be positive.")

    recovered = recover_interrupted_jobs()
    if recovered:
        LOGGER.warning("Re-queued %d interrupted job(s).", recovered)

    purged = purge_expired_jobs()
    if purged:
        LOGGER.info("Removed %d expired job(s).", purged)

    next_cleanup = time.monotonic() + 24 * 60 * 60
    while True:
        did_work = run_one_job()
        if once:
            return
        if time.monotonic() >= next_cleanup:
            purged = purge_expired_jobs()
            if purged:
                LOGGER.info("Removed %d expired job(s).", purged)
            next_cleanup = time.monotonic() + 24 * 60 * 60
        if not did_work:
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ResumeIQ SQLite-backed job worker."
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds to wait between empty queue checks.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job, then exit.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_worker(poll_interval=args.poll_interval, once=args.once)


if __name__ == "__main__":
    main()
