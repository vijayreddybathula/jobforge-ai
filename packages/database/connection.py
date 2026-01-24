"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from packages.database.models import Base
from packages.common.logging import get_logger

logger = get_logger(__name__)

# Global engine and session factory
engine = None
SessionLocal = None


def init_database(database_url: str, echo: bool = False) -> None:
    """Initialize database connection."""
    global engine, SessionLocal
    
    engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    logger.info("Database connection initialized")


def create_tables() -> None:
    """Create all database tables."""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
