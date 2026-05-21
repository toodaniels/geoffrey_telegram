from contextlib import asynccontextmanager
from datetime import datetime
import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import Session
from api.database import create_db_and_tables, get_session
from api.models import DownloadTask, DownloadStatus
from api.schemas import DownloadTaskCreate, DownloadTaskCreateResponse, DownloadTaskUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan event handler to initialize database tables on startup.
    """
    create_db_and_tables()
    yield

app = FastAPI(
    title="Geoffrey Centralized Download API",
    description="API for tracking and updating download tasks in Geoffrey Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)

@app.post(
    "/tasks",
    response_model=DownloadTaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new download task",
    description="Creates a database entry for a new download task with status PENDING."
)
def create_task(task_in: DownloadTaskCreate, session: Session = Depends(get_session)):
    """
    Creates a new DownloadTask in SQLite.
    
    FastAPI automatically executes normal 'def' endpoints in a separate thread pool,
    preventing the event loop from blocking while interacting with the synchronous SQLite engine.
    """
    db_task = DownloadTask(
        user_id=task_in.user_id,
        message_id=task_in.message_id,
        file_name=task_in.file_name,
        file_size_bytes=task_in.file_size_bytes,
        status=DownloadStatus.PENDING
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    return DownloadTaskCreateResponse(
        task_id=db_task.task_id,
        status=db_task.status,
        message="Task registered successfully"
    )

@app.patch(
    "/tasks/{task_id}",
    response_model=DownloadTask,
    summary="Partially update a download task",
    description="Updates progress, status, and/or error messages for a task. Automatically updates updated_at."
)
def update_task(task_id: uuid.UUID, task_in: DownloadTaskUpdate, session: Session = Depends(get_session)):
    """
    Locates task by task_id UUID and updates any fields passed in the request body.
    """
    db_task = session.get(DownloadTask, task_id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    # Extract only the fields explicitly passed in the PATCH request
    update_data = task_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    # Update the updated_at timestamp as required
    db_task.updated_at = datetime.utcnow()
    
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    return db_task
