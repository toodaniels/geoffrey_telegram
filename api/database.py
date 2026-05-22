import os
import logging
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect, text

# Configure database file path (geoffrey.db)
DATABASE_FILE = "geoffrey.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite concurrency
    echo=True  # Enable SQL logging for development
)

logger = logging.getLogger(__name__)

def _migrate_schema():
    """Add new columns introduced in newer versions without losing data."""
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("download_tasks")}
    migrations = {
        "chat_id": "ALTER TABLE download_tasks ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0",
        "retry_count": "ALTER TABLE download_tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as conn:
        for col, stmt in migrations.items():
            if col not in columns:
                logger.info("Migrating schema: adding column %s", col)
                conn.execute(text(stmt))

def create_db_and_tables():
    # Import models here to register them with SQLModel metadata
    from api.models import DownloadTask  # noqa: F401
    SQLModel.metadata.create_all(engine)
    _migrate_schema()

def get_session():
    with Session(engine) as session:
        yield session
