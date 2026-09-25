import unittest

from app.models.schemas import (
    JobDescription,
    Resume,
    SkillGapAnalysisRequest,
)
from app.services.knowledge_retriever import retrieve_rule
from app.services.skill_gap_analysis import analyze_skill_gap


class SkillGapAnalysisTests(unittest.TestCase):
    def test_skill_gap_requires_and_uses_job_description_targets(self) -> None:
        resume = Resume(
            summary="Backend engineer",
            skills=["Python", "JavaScript", "Postgres"],
        )
        job_description = JobDescription(
            raw_text="Backend role",
            required_skills=[
                "Python",
                "PostgreSQL",
                "Java",
            ],
            preferred_skills=["AWS"],
        )

        result = analyze_skill_gap(
            SkillGapAnalysisRequest(
                resume=resume,
                job_description=job_description,
            )
        )

        self.assertEqual(
            result.matched_required_skills,
            ["python", "postgresql"],
        )
        self.assertEqual(
            result.missing_required_skills,
            ["java"],
        )
        self.assertEqual(
            result.matched_preferred_skills,
            [],
        )
        self.assertEqual(
            result.missing_preferred_skills,
            ["amazon web services"],
        )
        self.assertEqual(result.required_match_rate, 66.67)

    def test_skill_aliases_match_resume_evidence(self) -> None:
        resume = Resume(
            skills=["Python", "Postgres"],
            experience=[],
        )
        job_description = JobDescription(
            raw_text="Data role",
            required_skills=[
                "Python",
                "PostgreSQL",
            ],
        )

        result = analyze_skill_gap(
            SkillGapAnalysisRequest(
                resume=resume,
                job_description=job_description,
            )
        )

        self.assertEqual(
            result.matched_required_skills,
            ["python", "postgresql"],
        )
        self.assertEqual(result.required_match_rate, 100.0)

    def test_no_target_skills_returns_complete_match_rate(self) -> None:
        result = analyze_skill_gap(
            SkillGapAnalysisRequest(
                resume=Resume(skills=["Python"]),
                job_description=JobDescription(
                    raw_text="General role",
                ),
            )
        )

        self.assertEqual(result.required_match_rate, 100.0)
        self.assertEqual(result.total_target_skills, 0)
        self.assertEqual(result.matched_target_skills, 0)


class KnowledgeRetrieverTests(unittest.TestCase):
    def test_retrieves_rule_by_category(self) -> None:
        rule = retrieve_rule("quantification")

        self.assertEqual(rule["rule_id"], "BP-METRIC-001")
        self.assertEqual(rule["category"], "quantification")
        self.assertIn("measurable outcomes", rule["text"])

    def test_unknown_category_raises_explicit_error(self) -> None:
        with self.assertRaises(ValueError):
            retrieve_rule("unknown-category")


if __name__ == "__main__":
    unittest.main()
