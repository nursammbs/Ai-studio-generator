import tempfile
import unittest
from pathlib import Path

from jobs import JobStore


class JobStoreTests(unittest.TestCase):
    def test_job_state_survives_store_recreation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "jobs"
            store = JobStore(root)
            job = store.create("recording.mp4", Path(folder) / "recording.mp4")
            job["status"] = "ready_for_review"
            job["candidates"] = [{"start": 1.0, "end": 20.0}]
            store.save(job)

            reopened = JobStore(root).load(job["id"])
            self.assertEqual(reopened["status"], "ready_for_review")
            self.assertEqual(reopened["candidates"], [{"start": 1.0, "end": 20.0}])

    def test_list_returns_valid_jobs_and_obeys_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JobStore(folder)
            jobs = [store.create(f"recording-{n}.mp4", Path(folder) / f"{n}.mp4") for n in range(3)]
            self.assertEqual(len(store.list(limit=2)), 2)
            self.assertEqual({item["id"] for item in store.list(limit=3)}, {item["id"] for item in jobs})

    def test_invalid_or_traversing_job_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JobStore(folder)
            for job_id in ("../outside", "not-a-job-id", ""):
                with self.subTest(job_id=job_id), self.assertRaises(ValueError):
                    store.load(job_id)

    def test_unknown_job_cannot_be_created_by_save(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JobStore(folder)
            with self.assertRaises(FileNotFoundError):
                store.save({"id": "0123456789ab", "schema_version": 1})


if __name__ == "__main__":
    unittest.main()

