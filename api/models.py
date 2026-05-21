from enum import Enum
import uuid as uuid_pkg
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Column, String

class DownloadStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class DownloadTask(SQLModel, table=True):
    __tablename__ = "download_tasks"

    task_id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    user_id: int = Field(index=True)
    message_id: int
    file_name: str
    file_size_bytes: Optional[int] = Field(default=None, nullable=True)
    status: DownloadStatus = Field(default=DownloadStatus.PENDING)
    progress: float = Field(default=0.0)
    downloaded_bytes: int = Field(default=0)
    error_message: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )
