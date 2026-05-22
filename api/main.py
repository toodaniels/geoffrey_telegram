from contextlib import asynccontextmanager
from datetime import datetime
import uuid
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from api.database import create_db_and_tables, get_session
from api.models import DownloadTask, DownloadStatus
from api.schemas import DownloadTaskCreate, DownloadTaskCreateResponse, DownloadTaskUpdate
from api.websocket_manager import ConnectionManager

manager = ConnectionManager()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="Geoffrey Centralized Download API",
    description="API for tracking and updating download tasks in Geoffrey Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard template not found")
    return index_path.read_text(encoding="utf-8")


@app.post(
    "/tasks",
    response_model=DownloadTaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new download task",
)
def create_task(task_in: DownloadTaskCreate, session: Session = Depends(get_session)):
    db_task = DownloadTask(
        user_id=task_in.user_id,
        message_id=task_in.message_id,
        chat_id=task_in.chat_id,
        file_name=task_in.file_name,
        file_size_bytes=task_in.file_size_bytes,
        status=DownloadStatus.PENDING,
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    return DownloadTaskCreateResponse(
        task_id=db_task.task_id,
        status=db_task.status,
        message="Task registered successfully",
    )


@app.get(
    "/tasks/active",
    response_model=list[DownloadTask],
    summary="List active download tasks",
    description="Returns all tasks that are not in a terminal state (COMPLETED, FAILED, CANCELLED).",
)
def list_active_tasks(session: Session = Depends(get_session)):
    terminal = (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)
    statement = select(DownloadTask).where(DownloadTask.status.not_in(terminal))
    tasks = session.exec(statement).all()
    return tasks


@app.post(
    "/tasks/reconcile",
    response_model=list[DownloadTask],
    summary="Reconcile orphaned tasks after bot restart",
    description="Resets DOWNLOADING/UPLOADING tasks to PENDING so they can be re-queued. "
                "Tasks with retry_count > 3 are marked as FAILED.",
)
def reconcile_tasks(session: Session = Depends(get_session)):
    active_statuses = (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, DownloadStatus.UPLOADING)
    statement = select(DownloadTask).where(DownloadTask.status.in_(active_statuses))
    tasks = session.exec(statement).all()
    reconciled = []
    for task in tasks:
        if task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.UPLOADING):
            if task.retry_count >= 3:
                task.status = DownloadStatus.FAILED
                task.error_message = "Reintentos agotados después de reinicio del bot"
            else:
                task.status = DownloadStatus.PENDING
                task.retry_count += 1
                task.progress = 0.0
                task.downloaded_bytes = 0
            task.updated_at = datetime.utcnow()
            session.add(task)
            reconciled.append(task)
    session.commit()
    for task in reconciled:
        session.refresh(task)
    return reconciled


@app.patch(
    "/tasks/{task_id}",
    response_model=DownloadTask,
    summary="Partially update a download task",
)
async def update_task(
    task_id: uuid.UUID,
    task_in: DownloadTaskUpdate,
    session: Session = Depends(get_session),
):
    db_task = session.get(DownloadTask, task_id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )

    update_data = task_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db_task.updated_at = datetime.utcnow()

    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    await manager.broadcast(db_task.model_dump())

    return db_task


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
