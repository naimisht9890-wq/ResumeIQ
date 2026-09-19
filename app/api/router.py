from fastapi import APIRouter,File,HTTPException,UploadFile
from app.services.resume_extraction import extract_resume_text

api_router = APIRouter()

@api_router.get("/health")
def health_check() -> dict[str,str]:
    return {"status": "ok","service":"ResumeIQ"}


@api_router.post("/v1/resumes")
async def upload_resume(file: UploadFile=File(...)) -> dict[str,str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="The uploaded file must have a filename")
    file_bytes = await file.read()

    try:
        extracted_text = extract_resume_text(filename=file.filename,file_bytes=file_bytes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {'filename':file.filename,'text':extracted_text}



@api_router.post("/v1/job-descriptions")
def upload_job_description():
    return {"status": "not_implemented"}


@api_router.post("/v1/ats-score")
def ats_score():
    return {"status": "not_implemented"}


@api_router.post("/v1/analysis/strengths-weaknesses")
def strengths_and_weaknesses():
    return {"status": "not_implemented"}


@api_router.post("/v1/resumes/tailor")
def tailor_resume():
    return {"status": "not_implemented"}


@api_router.post("/v1/resumes/render")
def render_resume():
    return {"status": "not_implemented"}


@api_router.post("/v1/cover-letters")
def create_cover_letter():
    return {"status": "not_implemented"}


@api_router.get("/v1/jobs/{job_id}")
def get_job(job_id: str):
    return {"status": "not_implemented", "job_id": job_id}
