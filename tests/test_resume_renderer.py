import unittest
from io import BytesIO

from docx import Document

from app.models.schemas import (
    ContactInfo,
    ExperienceItem,
    Resume,
)
from app.services.resume_renderer import render_resume_docx


class ResumeRendererTests(unittest.TestCase):
    def test_rendered_docx_is_valid_and_contains_resume_sections(self) -> None:
        resume = Resume(
            contact=ContactInfo(
                name="Jane Doe",
                email="jane@example.com",
            ),
            summary="Backend engineer experienced in APIs.",
            skills=["Python", "FastAPI"],
            experience=[
                ExperienceItem(
                    title="Backend Engineer",
                    company="Example Inc",
                    bullets=["Built Python APIs."],
                )
            ],
        )

        document_bytes = render_resume_docx(resume)
        document = Document(BytesIO(document_bytes))
        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

        self.assertIn("Jane Doe", text)
        self.assertIn("SUMMARY", text)
        self.assertIn("Backend engineer experienced in APIs.", text)
        self.assertIn("Built Python APIs.", text)


if __name__ == "__main__":
    unittest.main()
