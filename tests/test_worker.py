import base64
import os
import tempfile
import unittest
from unittest.mock import patch

from app.models.schemas import CreateJobRequest
from app.services.job_store import create_job, get_job
from app.worker import run_one_job


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_environment = patch.dict(
            os.environ,
            {
                "RESUMEIQ_DATABASE_PATH": os.path.join(
                    self.temp_directory.name,
                    "worker.sqlite3",
                )
            },
        )
        self.database_environment.start()
        self.addCleanup(self.database_environment.stop)

    def test_worker_executes_ats_scoring_and_persists_result(self) -> None:
        job = create_job(
            CreateJobRequest(
                operation="ats_scoring",
                payload={
                    "resume": {
                        "contact": {"email": "alex@example.com"},
                        "skills": ["Python"],
                        "experience": [
                            {"bullets": ["Built Python APIs."]}
                        ],
                    },
                    "job_description": {
                        "raw_text": "Backend engineering role.",
                        "required_skills": ["Python"],
                    },
                },
            )
        )

        self.assertTrue(run_one_job())
        completed = get_job(job.job_id)

        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.result)
        assert completed.result is not None
        self.assertIn("overall", completed.result)
        self.assertIn("citations", completed.result)

    def test_worker_marks_invalid_resume_upload_as_failed(self) -> None:
        job = create_job(
            CreateJobRequest(
                operation="resume_parsing",
                payload={
                    "filename": "empty.txt",
                    "content_base64": base64.b64encode(b"").decode("ascii"),
                },
            )
        )

        self.assertTrue(run_one_job())
        failed = get_job(job.job_id)

        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error, "The uploaded file is empty")
        self.assertIsNone(failed.result)


if __name__ == "__main__":
    unittest.main()
