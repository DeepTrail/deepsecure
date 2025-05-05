"""Application configuration settings."""

from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""
    PROJECT_NAME: str = "DeepSecure Backend"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/deepsecure_db")
    TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db") # In-memory for tests

    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_insecure_default_secret_key_replace_me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Add other settings like secret keys, etc.
    # SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret")

    class Config:
        """Pydantic settings configuration."""
        case_sensitive = True
        env_file = ".env"

settings = Settings() 