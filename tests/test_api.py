import unittest
from io import BytesIO
import os
import tempfile
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.worker import run_one_job
from app.models.schemas import (
    ContactInfo,
    CoverLetterResult,
    ExperienceItem,
    JobDescription,
    Resume,
    StrengthsWeaknessesResult,
    TailorResumeResult,
)


class ResumeIQApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.resume = Resume(
            contact=ContactInfo(
                name="Alex Doe",
                email="alex@example.com",
            ),
            summary="Backend engineer experienced in APIs.",
            experience=[
                ExperienceItem(
                    title="Backend Engineer",
                    company="Example Inc",
                    bullets=["Built Python APIs."],
                )
            ],
            skills=["Python", "FastAPI"],
        )
        self.job_description = JobDescription(
            title="Backend Engineer",
            company="Example Co",
            raw_text="Python FastAPI backend role.",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            preferred_skills=["Docker"],
            responsibilities=["Build backend services."],
        )

    def tearDown(self) -> None:
        self.client.close()

    def test_health_endpoint_returns_service_status(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "ResumeIQ",
            },
        )

    @patch("app.api.router.parse_job_description_text")
    @patch("app.api.router.parse_resume_text")
    @patch("app.api.router.extract_resume_text")
    def test_upload_parse_score_and_skill_gap_flow(
        self,
        mock_extract: object,
        mock_parse_resume: object,
        mock_parse_job: object,
    ) -> None:
        mock_extract.return_value = "resume text"
        mock_parse_resume.return_value = self.resume
        mock_parse_job.return_value = self.job_description

        upload_response = self.client.post(
            "/v1/resumes",
            files={
                "file": (
                    "resume.txt",
                    b"resume content",
                    "text/plain",
                )
            },
        )
        job_response = self.client.post(
            "/v1/job-descriptions",
            json={"text": "Python FastAPI backend role."},
        )

        self.assertEqual(upload_response.status_code, 200)
        self.assertEqual(job_response.status_code, 200)

        analysis_payload = {
            "resume": upload_response.json(),
            "job_description": job_response.json(),
        }
        score_response = self.client.post(
            "/v1/ats-score",
            json=analysis_payload,
        )
        gap_response = self.client.post(
            "/v1/analysis/skill-gap",
            json=analysis_payload,
        )

        self.assertEqual(score_response.status_code, 200)
        self.assertIn("overall", score_response.json())
        self.assertEqual(gap_response.status_code, 200)
        self.assertEqual(
            gap_response.json()["matched_required_skills"],
            ["python", "fastapi"],
        )
        self.assertEqual(
            gap_response.json()["missing_required_skills"],
            ["postgresql"],
        )
        mock_parse_resume.assert_called_once_with("resume text")
        mock_parse_job.assert_called_once_with(
            "Python FastAPI backend role."
        )

    def test_job_description_route_reports_parser_errors(self) -> None:
        with patch(
            "app.api.router.parse_job_description_text",
            side_effect=ValueError("Parser configuration error."),
        ):
            response = self.client.post(
                "/v1/job-descriptions",
                json={"text": "A valid job description."},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Parser configuration error.",
        )

    def test_render_endpoint_returns_valid_docx(self) -> None:
        response = self.client.post(
            "/v1/resumes/render",
            json={"resume": self.resume.model_dump(mode="json")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
            response.headers["content-type"],
        )
        self.assertIn(
            'filename="resume.docx"',
            response.headers["content-disposition"],
        )
        document = Document(BytesIO(response.content))
        rendered_text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )
        self.assertIn("Alex Doe", rendered_text)

    def test_genai_routes_return_validated_mocked_results(self) -> None:
        feedback = StrengthsWeaknessesResult(
            strengths=[],
            weaknesses=[],
        )
        tailoring = TailorResumeResult(
            changes=[],
            warnings=["No supported changes found."],
        )
        cover_letter = CoverLetterResult(
            draft="I am interested in the Backend Engineer role.",
            resume_facts_used=["Python"],
            warnings=[],
        )
        payload = {
            "resume": self.resume.model_dump(mode="json"),
            "job_description": self.job_description.model_dump(mode="json"),
        }

        with (
            patch(
                "app.api.router.generate_grounded_feedback",
                return_value=feedback,
            ),
            patch(
                "app.api.router.tailor_resume",
                return_value=tailoring,
            ),
            patch(
                "app.api.router.generate_cover_letter",
                return_value=cover_letter,
            ),
        ):
            feedback_response = self.client.post(
                "/v1/analysis/strengths-weaknesses",
                json=payload,
            )
            tailoring_response = self.client.post(
                "/v1/resumes/tailor",
                json=payload,
            )
            cover_letter_response = self.client.post(
                "/v1/cover-letters",
                json=payload,
            )

        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(feedback_response.json()["strengths"], [])
        self.assertEqual(tailoring_response.status_code, 200)
        self.assertEqual(
            tailoring_response.json()["warnings"],
            ["No supported changes found."],
        )
        self.assertEqual(cover_letter_response.status_code, 200)
        self.assertEqual(
            cover_letter_response.json()["resume_facts_used"],
            ["Python"],
        )

    def test_background_job_routes_persist_and_return_job_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = os.path.join(directory, "api-jobs.sqlite3")
            with patch.dict(
                os.environ,
                {"RESUMEIQ_DATABASE_PATH": database_path},
            ):
                create_response = self.client.post(
                    "/v1/jobs",
                    json={
                        "operation": "ats_scoring",
                        "payload": {
                            "resume": self.resume.model_dump(mode="json"),
                            "job_description": (
                                self.job_description.model_dump(mode="json")
                            ),
                        },
                    },
                )
                self.assertEqual(create_response.status_code, 202)
                job_id = create_response.json()["job_id"]
                self.assertTrue(run_one_job())

                status_response = self.client.get(f"/v1/jobs/{job_id}")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")
        self.assertEqual(status_response.json()["operation"], "ats_scoring")
        self.assertIsNotNone(status_response.json()["result"])
        self.assertIn("overall", status_response.json()["result"])


if __name__ == "__main__":
    unittest.main()
