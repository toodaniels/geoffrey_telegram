import os
from sqlmodel import SQLModel, create_engine, Session

# Configure database file path (geoffrey.db)
DATABASE_FILE = "geoffrey.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite concurrency
    echo=True  # Enable SQL logging for development
)

def create_db_and_tables():
    # Import models here to register them with SQLModel metadata
    from api.models import DownloadTask  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
