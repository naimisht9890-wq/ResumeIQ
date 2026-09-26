import os
import tempfile
import unittest
from unittest.mock import patch

from app.models.schemas import CreateJobRequest
from app.services.job_store import (
    claim_next_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    recover_interrupted_jobs,
)


class JobStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_environment = patch.dict(
            os.environ,
            {
                "RESUMEIQ_DATABASE_PATH": os.path.join(
                    self.temp_directory.name,
                    "jobs.sqlite3",
                )
            },
        )
        self.database_environment.start()
        self.addCleanup(self.database_environment.stop)

    @staticmethod
    def score_payload() -> dict:
        return {
            "resume": {
                "skills": ["Python"],
                "experience": [{"bullets": ["Built APIs."]}],
            },
            "job_description": {
                "raw_text": "Backend engineer role.",
                "required_skills": ["Python"],
            },
        }

    def test_create_and_get_job_persisted_in_sqlite(self) -> None:
        created = create_job(
            CreateJobRequest(
                operation="  ATS_SCORING ",
                payload=self.score_payload(),
            )
        )

        self.assertTrue(created.job_id)
        self.assertEqual(created.operation, "ats_scoring")
        self.assertEqual(created.status, "queued")

        fetched = get_job(created.job_id)
        self.assertEqual(fetched, created)

    def test_worker_claims_and_completes_job(self) -> None:
        created = create_job(
            CreateJobRequest(
                operation="ats_scoring",
                payload=self.score_payload(),
            )
        )

        claimed = claim_next_job()

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed.job_id, created.job_id)
        self.assertIsNone(claim_next_job())
        self.assertEqual(get_job(created.job_id).status, "running")

        complete_job(
            claimed.job_id,
            {"overall": 82.5, "breakdown": {"keyword_match": 80}},
        )
        completed = get_job(created.job_id)

        self.assertEqual(completed.status, "completed")
        self.assertEqual(
            completed.result,
            {"overall": 82.5, "breakdown": {"keyword_match": 80}},
        )
        self.assertIsNone(completed.error)

    def test_interrupted_job_is_requeued_and_can_fail_explicitly(self) -> None:
        created = create_job(
            CreateJobRequest(
                operation="ats_scoring",
                payload=self.score_payload(),
            )
        )
        first_claim = claim_next_job()
        self.assertIsNotNone(first_claim)

        self.assertEqual(recover_interrupted_jobs(), 1)
        self.assertEqual(get_job(created.job_id).status, "queued")

        second_claim = claim_next_job()
        self.assertIsNotNone(second_claim)
        assert second_claim is not None
        fail_job(second_claim.job_id, "Provider is unavailable.")

        failed = get_job(created.job_id)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error, "Provider is unavailable.")
        self.assertIsNone(failed.result)

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported job operation"):
            create_job(CreateJobRequest(operation="unknown"))

    def test_invalid_operation_payload_is_rejected_before_enqueue(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid payload"):
            create_job(
                CreateJobRequest(
                    operation="ats_scoring",
                    payload={
                        "resume": {},
                        "job_description": {
                            "required_skills": ["Python"],
                        },
                    },
                )
            )

    def test_unknown_job_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Job was not found"):
            get_job("missing-job")

    def test_claim_on_empty_queue_returns_none(self) -> None:
        self.assertIsNone(claim_next_job())


if __name__ == "__main__":
    unittest.main()
