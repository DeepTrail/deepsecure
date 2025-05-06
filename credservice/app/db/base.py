"""SQLAlchemy base model definition and model imports."""

from sqlalchemy.orm import declarative_base

# Base class for all SQLAlchemy models in the application.
Base = declarative_base()

# Import all models here to ensure they are registered with Base.metadata
from app.models.agent import Agent  # noqa
from app.models.credential import Credential  # noqa 