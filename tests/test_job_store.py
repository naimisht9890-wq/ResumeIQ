import unittest

from app.models.schemas import CreateJobRequest
from app.services.job_store import create_job, get_job


class JobStoreTests(unittest.TestCase):
    def test_create_and_get_job(self) -> None:
        created = create_job(
            CreateJobRequest(operation="tailoring")
        )

        self.assertTrue(created.job_id)
        self.assertEqual(created.operation, "tailoring")
        self.assertEqual(created.status, "queued")

        fetched = get_job(created.job_id)
        self.assertEqual(fetched, created)

    def test_operation_is_normalized(self) -> None:
        created = create_job(
            CreateJobRequest(operation="  COVER_LETTER ")
        )

        self.assertEqual(created.operation, "cover_letter")

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_job(
                CreateJobRequest(operation="unknown")
            )

    def test_unknown_job_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_job("missing-job")


if __name__ == "__main__":
    unittest.main()
