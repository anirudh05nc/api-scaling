import logging
import os
from datetime import datetime
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)

# Default connection string pointing to PostgreSQL
# Can be overridden using the DATABASE_URL environment variable
DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/api_scaling_db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


# Normalize URL for SQLAlchemy and ensure psycopg2 driver dialect is specified
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


# Configure SQLAlchemy engine with connection pooling optimized for API scaling
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_pre_ping=True,  # Discards stale connections automatically
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base model for all SQLAlchemy entities."""
    pass


class Item(Base):
    """Item model representing the items table in PostgreSQL."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency yield for FastAPI endpoints with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """
    Test connectivity to the PostgreSQL database.
    Returns a tuple of (is_healthy: bool, message: str).
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection is operational"
    except SQLAlchemyError as exc:
        logger.error(f"PostgreSQL health check failed: {exc}")
        return False, str(exc)
    except Exception as exc:
        logger.error(f"Unexpected database connection error: {exc}")
        return False, str(exc)


def init_db() -> bool:
    """
    Create tables if they don't already exist.
    Fails gracefully so the application can start even if DB is coming up.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        return True
    except Exception as exc:
        logger.warning(f"Could not initialize database tables immediately: {exc}")
        return False
