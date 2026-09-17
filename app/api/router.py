from fastapi import APIRouter

api_router = APIRouter()


@api_router.post("/v1/resumes")
def upload_resume():
    return {"status": "not_implemented"}


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
