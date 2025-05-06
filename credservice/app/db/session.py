"""Database session management setup."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os # Import os

from app.core.config import settings

# Determine DB URL based on environment (simple check for now)
DATABASE_URL_TO_USE = settings.DATABASE_URL
if os.getenv("RUNNING_TESTS") == "true":
    print("--- Using Test Database --- ")
    DATABASE_URL_TO_USE = settings.TEST_DATABASE_URL

# Create the SQLAlchemy engine using the database URL from settings
engine = create_engine(DATABASE_URL_TO_USE, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 