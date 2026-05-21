from pydantic import BaseModel
from typing import Optional
import uuid
from api.models import DownloadStatus

class DownloadTaskCreate(BaseModel):
    user_id: int
    message_id: int
    file_name: str
    file_size_bytes: Optional[int] = None

class DownloadTaskCreateResponse(BaseModel):
    task_id: uuid.UUID
    status: DownloadStatus
    message: str

class DownloadTaskUpdate(BaseModel):
    status: Optional[DownloadStatus] = None
    progress: Optional[float] = None
    downloaded_bytes: Optional[int] = None
    error_message: Optional[str] = None
