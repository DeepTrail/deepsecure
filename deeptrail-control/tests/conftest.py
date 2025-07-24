import pytest
from typing import Generator, Any
import os
import sys # Import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add the project root directory (deeptrail-control) to the Python path
# This allows imports like 'from app.main import app' to work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Set environment variable before importing app components
os.environ["RUNNING_TESTS"] = "true"

from app.main import app # Import your FastAPI app
from app.core.config import settings
from app.db.base import Base # Import Base from where your models inherit
from app.api.deps import get_db # Import the original dependency

# Explicitly import models to ensure they are registered with Base metadata
from app.models import agent, credential

# Create a new engine and session for testing
# Add connect_args for SQLite
engine = create_engine(
    settings.TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    """Create database tables before tests run and drop them after."""
    print("Creating test database tables...")
    Base.metadata.create_all(bind=engine)
    yield
    print("Dropping test database tables...")
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Fixture to get a test database session (simpler version)."""
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close() # Close the session

@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Fixture to get a TestClient instance with overridden DB dependency."""

    def override_get_db():
        try:
            yield db
        finally:
            pass # Let the 'db' fixture handle closing

    # Apply the override for the get_db dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # Clean up the override after the test
    del app.dependency_overrides[get_db] 