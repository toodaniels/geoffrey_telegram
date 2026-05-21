import unittest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from api.main import app
from api.database import get_session
from api.models import DownloadTask

from sqlalchemy.pool import StaticPool

# Use an in-memory SQLite database for tests with a StaticPool to maintain a single connection
TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

def override_get_session():
    with Session(test_engine) as session:
        yield session

# Override the database session dependency
app.dependency_overrides[get_session] = override_get_session

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create all tables on the in-memory database
        SQLModel.metadata.create_all(test_engine)

    def setUp(self):
        self.client = TestClient(app)
        
    def test_create_and_patch_task(self):
        # Test registering a task (POST /tasks)
        payload = {
            "user_id": 123456789,
            "message_id": 98765,
            "file_name": "test_video.mp4",
            "file_size_bytes": 1048576
        }
        response = self.client.post("/tasks", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["message"], "Task registered successfully")
        
        task_id = data["task_id"]
        
        # Test patching the progress of the task (PATCH /tasks/{task_id})
        patch_payload = {
            "status": "DOWNLOADING",
            "progress": 0.45,
            "downloaded_bytes": 471859
        }
        patch_response = self.client.patch(f"/tasks/{task_id}", json=patch_payload)
        self.assertEqual(patch_response.status_code, 200)
        patched_data = patch_response.json()
        self.assertEqual(patched_data["task_id"], task_id)
        self.assertEqual(patched_data["status"], "DOWNLOADING")
        self.assertEqual(patched_data["progress"], 0.45)
        self.assertEqual(patched_data["downloaded_bytes"], 471859)
        self.assertIsNotNone(patched_data["updated_at"])
        
        # Test patching with invalid UUID
        invalid_uuid = "00000000-0000-0000-0000-000000000000"
        bad_response = self.client.patch(f"/tasks/{invalid_uuid}", json=patch_payload)
        self.assertEqual(bad_response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
