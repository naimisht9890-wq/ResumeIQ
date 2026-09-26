import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.schemas import (
    CoverLetterRequest,
    JobDescription,
    Resume,
    StrengthsWeaknessesRequest,
    TailorResumeRequest,
)
from app.services.cover_letter_generator import generate_cover_letter
from app.services.feedback_generator import generate_grounded_feedback
from app.services.resume_tailoring import tailor_resume


class RagPipelineIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.environment = patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "test-api-key",
                "RESUMEIQ_DATABASE_PATH": os.path.join(
                    self.temp_directory.name,
                    "rag.sqlite3",
                ),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.resume = Resume(
            contact={"name": "Alex Doe", "email": "alex@example.com"},
            summary="Backend engineer with Python API experience.",
            experience=[
                {
                    "title": "Backend Engineer",
                    "company": "Example Inc",
                    "bullets": ["Built Python APIs for customer services."],
                }
            ],
            skills=["Python", "FastAPI"],
        )
        self.job_description = JobDescription(
            title="Backend Engineer",
            raw_text=(
                "Backend Engineer. Required skills include Python and "
                "FastAPI. Build reliable APIs."
            ),
            required_skills=["Python", "FastAPI"],
            responsibilities=["Build reliable APIs."],
        )

    @staticmethod
    def mocked_groq_response(content: dict) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(content))
                )
            ]
        )

    @staticmethod
    def assert_prompt_contains_retrieved_context(
        completions: MagicMock,
    ) -> None:
        prompt = completions.create.call_args.kwargs["messages"][1]["content"]
        assert '"retrieval_method": "sqlite_fts5_bm25"' in prompt
        assert '"rule_id":' in prompt

    def test_feedback_generation_uses_and_cites_retrieved_context(self) -> None:
        response = self.mocked_groq_response(
            {"strengths": [], "weaknesses": []}
        )

        with patch(
            "app.services.feedback_generator.Groq"
        ) as groq_client:
            groq_client.return_value.chat.completions.create.return_value = (
                response
            )
            result = generate_grounded_feedback(
                StrengthsWeaknessesRequest(
                    resume=self.resume,
                    job_description=self.job_description,
                )
            )

        self.assertGreater(len(result.citations), 0)
        self.assert_prompt_contains_retrieved_context(
            groq_client.return_value.chat.completions
        )

    def test_tailoring_generation_uses_and_cites_retrieved_context(self) -> None:
        response = self.mocked_groq_response(
            {"changes": [], "warnings": []}
        )

        with patch(
            "app.services.resume_tailoring.Groq"
        ) as groq_client:
            groq_client.return_value.chat.completions.create.return_value = (
                response
            )
            result = tailor_resume(
                TailorResumeRequest(
                    resume=self.resume,
                    job_description=self.job_description,
                )
            )

        self.assertGreater(len(result.citations), 0)
        self.assert_prompt_contains_retrieved_context(
            groq_client.return_value.chat.completions
        )

    def test_cover_letter_generation_uses_and_cites_retrieved_context(
        self,
    ) -> None:
        response = self.mocked_groq_response(
            {
                "draft": (
                    "I am applying for the Backend Engineer role with "
                    "experience building Python APIs."
                ),
                "resume_facts_used": ["Built Python APIs for customer services."],
                "warnings": [],
            }
        )

        with patch(
            "app.services.cover_letter_generator.Groq"
        ) as groq_client:
            groq_client.return_value.chat.completions.create.return_value = (
                response
            )
            result = generate_cover_letter(
                CoverLetterRequest(
                    resume=self.resume,
                    job_description=self.job_description,
                )
            )

        self.assertGreater(len(result.citations), 0)
        self.assert_prompt_contains_retrieved_context(
            groq_client.return_value.chat.completions
        )


if __name__ == "__main__":
    unittest.main()
