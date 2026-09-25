from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import (
    ATSScoreRequest,
    ATSScoreResult,
    JobDescription,
    JobDescriptionRequest,
    Resume,
    SkillGapAnalysisRequest,
    SkillGapAnalysisResult,
    StrengthsWeaknessesRequest,
    StrengthsWeaknessesResult,
    TailorResumeRequest,
    TailorResumeResult,
)
from app.services.ats_scoring import calculate_ats_score
from app.services.feedback_generator import (generate_grounded_feedback)
from app.services.skill_gap_analysis import analyze_skill_gap
from app.services.job_description_parser import (
    parse_job_description_text,
)
from app.services.resume_extraction import extract_resume_text
from app.services.resume_parser import parse_resume_text
from app.services.resume_tailoring import tailor_resume

api_router = APIRouter()


@api_router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ResumeIQ",
    }


@api_router.post("/v1/resumes", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
) -> Resume:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must have a filename.",
        )

    file_bytes = await file.read()

    try:
        extracted_text = extract_resume_text(
            filename=file.filename,
            file_bytes=file_bytes,
        )

        resume = parse_resume_text(extracted_text)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return resume

@api_router.post(
    "/v1/job-descriptions",
    response_model=JobDescription,
)
def upload_job_description(
    request: JobDescriptionRequest,
) -> JobDescription:
    try:
        return parse_job_description_text(request.text)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@api_router.post("/v1/ats-score", response_model=ATSScoreResult)
def ats_score(request: ATSScoreRequest) -> ATSScoreResult:
    return calculate_ats_score(request)

@api_router.post(
    "/v1/analysis/skill-gap",
    response_model=SkillGapAnalysisResult,
)
def skill_gap_analysis(
    request: SkillGapAnalysisRequest,
) -> SkillGapAnalysisResult:
    return analyze_skill_gap(request)

@api_router.post(
    "/v1/analysis/strengths-weaknesses",
    response_model=StrengthsWeaknessesResult,
)
def strengths_and_weaknesses(
    request: StrengthsWeaknessesRequest,
) -> StrengthsWeaknessesResult:
    try:
        return generate_grounded_feedback(request)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

@api_router.post(
    "/v1/resumes/tailor",
    response_model=TailorResumeResult,
)
def tailor_resume_endpoint(
    request: TailorResumeRequest,
) -> TailorResumeResult:
    try:
        return tailor_resume(request)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@api_router.post("/v1/resumes/render")
def render_resume() -> dict[str, str]:
    return {
        "status": "not_implemented",
    }


@api_router.post("/v1/cover-letters")
def create_cover_letter() -> dict[str, str]:
    return {
        "status": "not_implemented",
    }


@api_router.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, str]:
    return {
        "status": "not_implemented",
        "job_id": job_id,
    }