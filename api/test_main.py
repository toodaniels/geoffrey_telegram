import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from api.main import app
from api.database import get_session
from api.models import DownloadTask, DownloadStatus

TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SQLModel.metadata.create_all(test_engine)

    def setUp(self):
        self.client = TestClient(app)

    def test_dashboard_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Geoffrey Downloads", response.text)

    def test_create_and_patch_task(self):
        payload = {
            "user_id": 123456789,
            "message_id": 98765,
            "chat_id": -100123456,
            "file_name": "test_video.mp4",
            "file_size_bytes": 1048576,
        }
        response = self.client.post("/tasks", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["message"], "Task registered successfully")

        task_id = data["task_id"]

        patch_payload = {
            "status": "DOWNLOADING",
            "progress": 0.45,
            "downloaded_bytes": 471859,
        }
        patch_response = self.client.patch(f"/tasks/{task_id}", json=patch_payload)
        self.assertEqual(patch_response.status_code, 200)
        patched_data = patch_response.json()
        self.assertEqual(patched_data["task_id"], task_id)
        self.assertEqual(patched_data["status"], "DOWNLOADING")
        self.assertEqual(patched_data["progress"], 0.45)
        self.assertEqual(patched_data["downloaded_bytes"], 471859)
        self.assertIsNotNone(patched_data["updated_at"])

        invalid_uuid = "00000000-0000-0000-0000-000000000000"
        bad_response = self.client.patch(f"/tasks/{invalid_uuid}", json=patch_payload)
        self.assertEqual(bad_response.status_code, 404)

    def test_active_tasks_filter(self):
        payload = {
            "user_id": 1,
            "message_id": 1,
            "chat_id": -100123456,
            "file_name": "active_test.mp4",
            "file_size_bytes": 512,
        }
        resp = self.client.post("/tasks", json=payload)
        task_id = resp.json()["task_id"]

        active = self.client.get("/tasks/active")
        self.assertEqual(active.status_code, 200)
        ids = [t["task_id"] for t in active.json()]
        self.assertIn(task_id, ids)

        self.client.patch(f"/tasks/{task_id}", json={"status": "COMPLETED"})

        active = self.client.get("/tasks/active")
        ids = [t["task_id"] for t in active.json()]
        self.assertNotIn(task_id, ids)

    def test_reconcile_resets_downloading(self):
        payload = {
            "user_id": 1,
            "message_id": 2,
            "chat_id": -100123456,
            "file_name": "reconcile_test.mp4",
            "file_size_bytes": 1024,
        }
        resp = self.client.post("/tasks", json=payload)
        task_id = resp.json()["task_id"]

        self.client.patch(f"/tasks/{task_id}", json={"status": "DOWNLOADING"})

        reconcile = self.client.post("/tasks/reconcile")
        self.assertEqual(reconcile.status_code, 200)
        result = reconcile.json()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["task_id"], task_id)
        self.assertEqual(result[0]["status"], "PENDING")
        self.assertEqual(result[0]["retry_count"], 1)
        self.assertEqual(result[0]["progress"], 0.0)

    def test_reconcile_marks_failed_after_3_retries(self):
        payload = {
            "user_id": 1,
            "message_id": 3,
            "chat_id": -100123456,
            "file_name": "exhausted_test.mp4",
            "file_size_bytes": 1024,
        }
        resp = self.client.post("/tasks", json=payload)
        task_id = resp.json()["task_id"]

        self.client.patch(f"/tasks/{task_id}", json={"status": "DOWNLOADING", "retry_count": 3})

        reconcile = self.client.post("/tasks/reconcile")
        self.assertEqual(reconcile.status_code, 200)
        result = {t["task_id"]: t for t in reconcile.json()}
        self.assertIn(task_id, result)
        self.assertEqual(result[task_id]["status"], "FAILED")
        self.assertIn("Reintentos agotados", result[task_id]["error_message"])


if __name__ == "__main__":
    unittest.main()
