"""Application configuration settings."""

from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv
import toml
from pathlib import Path

# Load .env file from the credservice directory if it exists
load_dotenv()

def get_project_version() -> str:
    """Reads the project version from environment variable or pyproject.toml file."""
    # First try to get version from environment variable (for Docker)
    env_version = os.getenv("DEEPSECURE_VERSION")
    if env_version:
        return env_version
    
    # Fallback to reading from pyproject.toml (for local development)
    pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return "0.0.0-dev"  # Fallback for when run in isolation
    
    pyproject_data = toml.load(pyproject_path)
    return pyproject_data.get("project", {}).get("version", "0.0.0-unknown")

class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""
    PROJECT_NAME: str = "DeepSecure CredService"
    PROJECT_VERSION: str = get_project_version()
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/deepsecure_db")
    TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db") # In-memory for tests

    # JWT settings (Keep for potential future use, but not used by current auth)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_insecure_default_secret_key_replace_me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Static API Key for backend access
    # Load from environment variable, provide a default for local dev/testing ONLY
    # !!! CHANGE THIS IN PRODUCTION !!!
    BACKEND_API_TOKEN: str = os.getenv("BACKEND_API_TOKEN", "insecure_default_api_token_for_dev")

    # Add other settings like secret keys, etc.
    # SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret")

    class Config:
        """Pydantic settings configuration."""
        case_sensitive = True
        env_file = ".env"

settings = Settings() 