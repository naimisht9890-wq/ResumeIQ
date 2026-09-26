import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.schemas import (
    JobDescription,
    Resume,
    SkillGapAnalysisRequest,
)
from app.services import knowledge_retriever
from app.services.knowledge_retriever import (
    citations_for_context,
    retrieve_context,
    retrieve_rule,
)
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
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_environment = patch.dict(
            os.environ,
            {
                "RESUMEIQ_DATABASE_PATH": os.path.join(
                    self.temp_directory.name,
                    "knowledge.sqlite3",
                )
            },
        )
        self.database_environment.start()
        self.addCleanup(self.database_environment.stop)

    def test_retrieves_rule_by_category(self) -> None:
        rule = retrieve_rule("quantification")

        self.assertEqual(rule["rule_id"], "BP-METRIC-001")
        self.assertEqual(rule["category"], "quantification")
        self.assertIn("measurable outcomes", rule["text"])

    def test_unknown_category_raises_explicit_error(self) -> None:
        with self.assertRaises(ValueError):
            retrieve_rule("unknown-category")

    def test_bm25_ranks_relevant_rule_and_filters_categories(self) -> None:
        rules = retrieve_context(
            "accurate figures percentages metrics never invent",
            ["quantification"],
            top_k=3,
        )

        self.assertGreaterEqual(len(rules), 2)
        self.assertEqual(rules[0]["rule_id"], "BP-METRIC-002")
        self.assertTrue(
            all(rule["category"] == "quantification" for rule in rules)
        )
        self.assertEqual(rules[0]["retrieval_method"], "sqlite_fts5_bm25")

    def test_retrieved_context_produces_rule_citations(self) -> None:
        rules = retrieve_context(
            "cover letter target role candidate experience",
            ["cover_letter"],
            top_k=1,
        )

        citations = citations_for_context(rules)

        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].rule_id, rules[0]["rule_id"])
        self.assertIn("SQLite FTS5 BM25", citations[0].note)

    def test_index_refreshes_when_the_curated_corpus_changes(self) -> None:
        corpus_path = Path(self.temp_directory.name) / "rules.json"
        first_rule = {
            "rule_id": "TEST-001",
            "category": "test",
            "text": "Original parsing guidance.",
            "source": "test_corpus",
        }
        corpus_path.write_text(
            json.dumps([first_rule]),
            encoding="utf-8",
        )

        with patch.object(knowledge_retriever, "KNOWLEDGE_FILE", corpus_path):
            first = retrieve_context("original parsing", ["test"])
            second_rule = {
                "rule_id": "TEST-002",
                "category": "test",
                "text": "Updated parsing guidance for modern formats.",
                "source": "test_corpus",
            }
            corpus_path.write_text(
                json.dumps([second_rule]),
                encoding="utf-8",
            )
            refreshed = retrieve_context(
                "updated parsing modern formats",
                ["test"],
            )

        self.assertEqual(first[0]["rule_id"], "TEST-001")
        self.assertEqual(refreshed[0]["rule_id"], "TEST-002")

    def test_rejects_zero_top_k_and_returns_empty_for_no_categories(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k"):
            retrieve_context("resume", ["summary"], top_k=0)
        self.assertEqual(retrieve_context("resume", []), [])


if __name__ == "__main__":
    unittest.main()
