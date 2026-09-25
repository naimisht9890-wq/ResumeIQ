import unittest

from app.models.schemas import (
    ContactInfo,
    CoverLetterRequest,
    JobDescription,
    Resume,
)
from app.services.cover_letter_generator import (
    _validate_fact_references,
    _validate_result,
)


class CoverLetterGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = CoverLetterRequest(
            resume=Resume(
                contact=ContactInfo(name="Jane Doe"),
                summary="Backend engineer experienced in APIs.",
                skills=["Python"],
            ),
            job_description=JobDescription(
                raw_text="Python backend developer",
                required_skills=["Python"],
            ),
        )

    def test_valid_draft_and_fact_reference_are_accepted(self) -> None:
        result = _validate_result(
            {
                "draft": (
                    "I am interested in the Python backend developer role. "
                    "My background includes building reliable APIs."
                ),
                "resume_facts_used": [
                    "Backend engineer experienced in APIs.",
                    "Python",
                ],
                "warnings": [],
            }
        )

        _validate_fact_references(result, self.request)

    def test_unknown_fact_reference_is_rejected(self) -> None:
        result = _validate_result(
            {
                "draft": "I managed a large cloud platform.",
                "resume_facts_used": [
                    "Managed a large cloud platform.",
                ],
                "warnings": [],
            }
        )

        with self.assertRaises(ValueError):
            _validate_fact_references(result, self.request)

    def test_empty_draft_is_rejected(self) -> None:
        result = _validate_result(
            {
                "draft": " ",
                "resume_facts_used": [],
                "warnings": ["The resume does not provide enough evidence."],
            }
        )

        with self.assertRaises(ValueError):
            _validate_fact_references(result, self.request)


if __name__ == "__main__":
    unittest.main()
