import os
import toml
import keyring
from pathlib import Path
from typing import Optional, Dict, Any

APP_NAME = "deepsecure-cli"
CONFIG_DIR = Path.home() / ".deepsecure"
CONFIG_FILE_PATH = CONFIG_DIR / "config.toml"

# Service names for keyring
CREDSERVICE_URL_KEY = "credservice_url"
API_TOKEN_KEY = "api_token"

def ensure_config_dir_exists():
    """Ensures the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> Dict[str, Any]:
    """Loads the configuration from the TOML file."""
    ensure_config_dir_exists()
    if CONFIG_FILE_PATH.exists():
        return toml.load(CONFIG_FILE_PATH)
    return {}

def save_config(config_data: Dict[str, Any]):
    """Saves the configuration to the TOML file."""
    ensure_config_dir_exists()
    with open(CONFIG_FILE_PATH, "w") as f:
        toml.dump(config_data, f)

def get_credservice_url() -> Optional[str]:
    """Gets the CredService URL from the config file."""
    config = load_config()
    return config.get(CREDSERVICE_URL_KEY)

def set_credservice_url(url: str):
    """Sets the CredService URL in the config file."""
    config = load_config()
    config[CREDSERVICE_URL_KEY] = url
    save_config(config)
    print(f"CredService URL set to: {url}")

def get_api_token() -> Optional[str]:
    """Gets the API token from the keyring."""
    try:
        token = keyring.get_password(APP_NAME, API_TOKEN_KEY)
        return token
    except keyring.errors.NoKeyringError:
        print("No keyring backend found. API token cannot be securely stored or retrieved.")
        # Fallback to environment variable or config file if desired,
        # but for now, we'll just indicate it's not available.
        return None


def set_api_token(token: str):
    """Sets the API token in the keyring."""
    try:
        keyring.set_password(APP_NAME, API_TOKEN_KEY, token)
        print(f"API token stored securely in keyring for service '{APP_NAME}' and username '{API_TOKEN_KEY}'.")
    except keyring.errors.NoKeyringError:
        print("No keyring backend found. API token cannot be securely stored.")
        # Fallback or error handling
        # For now, we'll just print the message. Users might need to install a backend.
        print("Consider installing a keyring backend (e.g., 'keyrings.alt', 'keyring-macos').")


def delete_api_token():
    """Deletes the API token from the keyring."""
    try:
        keyring.delete_password(APP_NAME, API_TOKEN_KEY)
        print(f"API token deleted from keyring for service '{APP_NAME}' and username '{API_TOKEN_KEY}'.")
    except keyring.errors.PasswordNotFoundError:
        print("No API token found in keyring to delete.")
    except keyring.errors.NoKeyringError:
        print("No keyring backend found. API token cannot be managed.")

# For CLI usage, we might want to retrieve these combined or with fallbacks
def get_effective_credservice_url() -> Optional[str]:
    """
    Gets the CredService URL, preferring environment variable, then config file.
    """
    url = os.getenv("DEEPSECURE_CREDSERVICE_URL")
    if url:
        return url
    return get_credservice_url()

def get_effective_api_token() -> Optional[str]:
    """
    Gets the API Token, preferring environment variable, then keyring.
    """
    token = os.getenv("DEEPSECURE_CREDSERVICE_API_TOKEN")
    if token:
        return token
    return get_api_token() 