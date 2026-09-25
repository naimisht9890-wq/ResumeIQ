import unittest

from app.models.schemas import (
    ExperienceItem,
    JobDescription,
    Resume,
    TailorResumeRequest,
    TailorResumeResult,
)
from app.services.resume_tailoring import (
    _validate_change_safety,
    _validate_result,
)


class ResumeTailoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = TailorResumeRequest(
            resume=Resume(
                summary="Backend engineer experienced in APIs.",
                experience=[
                    ExperienceItem(
                        title="Backend Engineer",
                        bullets=["Built Python APIs."],
                    )
                ],
            ),
            job_description=JobDescription(
                raw_text="Python backend developer",
                required_skills=["Python"],
            ),
        )

    def test_valid_original_text_is_accepted(self) -> None:
        result = TailorResumeResult(
            changes=[
                {
                    "section": "experience",
                    "original_text": "Built Python APIs.",
                    "suggested_text": "Built and maintained Python APIs.",
                    "reason": "Uses stronger action wording.",
                    "supported_by_resume": True,
                }
            ]
        )

        _validate_change_safety(result, self.request)

    def test_fabricated_original_text_is_rejected(self) -> None:
        result = TailorResumeResult(
            changes=[
                {
                    "section": "experience",
                    "original_text": "Managed AWS infrastructure.",
                    "suggested_text": "Managed scalable AWS infrastructure.",
                    "reason": "Targets the job description.",
                    "supported_by_resume": False,
                }
            ]
        )

        with self.assertRaises(ValueError):
            _validate_change_safety(result, self.request)

    def test_result_schema_requires_review_fields(self) -> None:
        result = _validate_result(
            {
                "changes": [],
                "warnings": ["AWS is not supported by the resume."],
            }
        )

        self.assertEqual(result.changes, [])
        self.assertEqual(
            result.warnings,
            ["AWS is not supported by the resume."],
        )


if __name__ == "__main__":
    unittest.main()
