import os
import tempfile
import unittest
from unittest.mock import patch

from app.models.schemas import (
    ATSScoreRequest,
    ContactInfo,
    ExperienceItem,
    JobDescription,
    ProjectItem,
    Resume,
)
from app.services.ats_scoring import calculate_ats_score


class ATSScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_environment = patch.dict(
            os.environ,
            {
                "RESUMEIQ_DATABASE_PATH": os.path.join(
                    self.temp_directory.name,
                    "ats.sqlite3",
                )
            },
        )
        self.database_environment.start()
        self.addCleanup(self.database_environment.stop)

    def test_skill_aliases_match_without_substring_false_positives(self) -> None:
        resume = Resume(
            contact=ContactInfo(name="Alex Doe"),
            skills=["sklearn", "Python"],
            experience=[
                ExperienceItem(
                    title="Data Engineer",
                    bullets=[
                        "Built an NLP pipeline and reduced latency by 30%.",
                    ],
                )
            ],
        )
        job_description = JobDescription(
            raw_text="Data engineer",
            required_skills=[
                "Natural Language Processing",
                "Python",
                "Java",
            ],
        )

        result = calculate_ats_score(
            ATSScoreRequest(
                resume=resume,
                job_description=job_description,
            )
        )

        semantic_citation = next(
            citation
            for citation in result.citations
            if citation.rule_id == "SEMANTIC_SKILL_MATCH"
        )

        self.assertIn("Matched 2/3 required", semantic_citation.note)
        self.assertIn(
            "java",
            next(
                citation.note
                for citation in result.citations
                if citation.rule_id == "MISSING_TARGET_SKILLS"
            ),
        )

    def test_professional_sections_do_not_require_summary_or_projects(self) -> None:
        resume = Resume(
            contact=ContactInfo(email="alex@example.com"),
            skills=["Python"],
            experience=[
                ExperienceItem(
                    title="Backend Engineer",
                    company="Example Inc",
                    bullets=["Built APIs."],
                )
            ],
        )

        result = calculate_ats_score(
            ATSScoreRequest(resume=resume)
        )

        self.assertGreaterEqual(
            result.breakdown.section_completeness,
            70,
        )

    def test_student_role_accepts_education_or_projects(self) -> None:
        resume = Resume(
            contact=ContactInfo(name="Student Doe"),
            skills=["Python"],
            projects=[
                ProjectItem(
                    name="Portfolio API",
                    bullets=["Built a portfolio API."],
                )
            ],
        )
        job_description = JobDescription(
            title="Junior Software Engineer",
            raw_text="Entry-level software engineering role.",
        )

        result = calculate_ats_score(
            ATSScoreRequest(
                resume=resume,
                job_description=job_description,
            )
        )

        citation = next(
            citation
            for citation in result.citations
            if citation.rule_id == "ROLE_APPROPRIATE_SECTIONS"
        )

        self.assertIn("student/entry-level", citation.note)
        self.assertNotIn("education_or_projects", citation.note)

    def test_quantification_rewards_action_and_impact(self) -> None:
        resume = Resume(
            experience=[
                ExperienceItem(
                    bullets=[
                        "Reduced deployment time by 40%.",
                        "Worked on 5 services.",
                        "Maintained documentation.",
                    ]
                )
            ]
        )

        result = calculate_ats_score(
            ATSScoreRequest(resume=resume)
        )

        self.assertEqual(
            result.breakdown.quantification,
            38.33,
        )

    def test_readability_penalizes_complex_and_non_action_bullets(self) -> None:
        resume = Resume(
            experience=[
                ExperienceItem(
                    bullets=[
                        "Built APIs.",
                        (
                            "Responsible for many different activities and "
                            "tasks while coordinating with teams and tools "
                            "that supported several long processes."
                        ),
                    ]
                )
            ]
        )

        result = calculate_ats_score(
            ATSScoreRequest(resume=resume)
        )

        self.assertLess(result.breakdown.readability, 80)

    def test_same_input_produces_same_result(self) -> None:
        resume = Resume(
            contact=ContactInfo(name="Alex Doe"),
            skills=["Python"],
            experience=[
                ExperienceItem(
                    bullets=["Improved performance by 20%."],
                )
            ],
        )
        request = ATSScoreRequest(resume=resume)

        first = calculate_ats_score(request)
        second = calculate_ats_score(request)

        self.assertEqual(first, second)
        self.assertTrue(
            any(
                citation.rule_id == "OVERALL_WEIGHTED_SCORE"
                for citation in first.citations
            )
        )

    def test_score_cites_retrieved_guidance_without_changing_score(self) -> None:
        request = ATSScoreRequest(
            resume=Resume(
                skills=["Python"],
                experience=[
                    ExperienceItem(
                        bullets=["Reduced processing time by 20%."]
                    )
                ],
            ),
            job_description=JobDescription(
                raw_text="Backend Python role.",
                required_skills=["Python"],
            ),
        )

        first = calculate_ats_score(request)
        second = calculate_ats_score(request)

        retrieved_citations = [
            citation
            for citation in first.citations
            if "Related guidance only" in citation.note
        ]
        self.assertGreater(len(retrieved_citations), 0)
        self.assertTrue(
            all(
                citation.source in {"ats_behavior", "resume_best_practices"}
                for citation in retrieved_citations
            )
        )
        self.assertEqual(first.overall, second.overall)


if __name__ == "__main__":
    unittest.main()
