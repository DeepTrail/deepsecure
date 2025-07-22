import os
import toml
import keyring
from pathlib import Path
from typing import Optional, Dict, Any

APP_NAME = "deepsecure"
CONFIG_DIR = Path.home() / ".deepsecure"
CONFIG_FILE_PATH = CONFIG_DIR / "config.toml"

# Service names for keyring
DEEPTRAIL_CONTROL_URL_KEY = "deeptrail_control_url"
DEEPTRAIL_GATEWAY_URL_KEY = "deeptrail_gateway_url"
API_TOKEN_KEY = "api_token"
LOG_LEVEL_KEY = "cli_log_level"

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

def get_deeptrail_control_url() -> Optional[str]:
    """Gets the Deeptrail Control URL from the config file."""
    config = load_config()
    return config.get(DEEPTRAIL_CONTROL_URL_KEY)

def set_deeptrail_control_url(url: str):
    """Sets the Deeptrail Control URL in the config file."""
    config = load_config()
    config[DEEPTRAIL_CONTROL_URL_KEY] = url
    save_config(config)
    print(f"Deeptrail Control URL set to: {url}")

def get_deeptrail_gateway_url() -> Optional[str]:
    """Gets the Deeptrail Gateway URL from the config file."""
    config = load_config()
    return config.get(DEEPTRAIL_GATEWAY_URL_KEY)

def set_deeptrail_gateway_url(url: str):
    """Sets the Deeptrail Gateway URL in the config file."""
    config = load_config()
    config[DEEPTRAIL_GATEWAY_URL_KEY] = url
    save_config(config)
    print(f"Deeptrail Gateway URL set to: {url}")

def get_cli_log_level() -> str:
    """Gets the CLI log level from the config file, defaults to WARNING."""
    config = load_config()
    return config.get(LOG_LEVEL_KEY, "WARNING").upper()

def set_cli_log_level(level: str):
    """Sets the CLI log level in the config file."""
    # Basic validation for common log levels
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level_upper = level.upper()
    if level_upper not in valid_levels:
        print(f"Invalid log level '{level}'. Must be one of {valid_levels}. Level not changed.")
        return
    
    config = load_config()
    config[LOG_LEVEL_KEY] = level_upper
    save_config(config)
    print(f"CLI log level set to: {level_upper}")
    print("Note: You may need to restart the CLI or current shell session for this to take full effect on all modules if they cache logging settings.")

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
    except keyring.errors.PasswordDeleteError:
        print(f"No API token found in keyring for service '{APP_NAME}' and username '{API_TOKEN_KEY}', or it could not be deleted.")
    except keyring.errors.NoKeyringError:
        print("No keyring backend found. API token cannot be managed.")
    except Exception as e:
        print(f"An unexpected error occurred while deleting the API token: {e}")

# For CLI usage, we might want to retrieve these combined or with fallbacks
def get_effective_deeptrail_control_url() -> str | None:
    """
    Returns the effective Deeptrail Control URL, checking env vars first, then config file.
    
    Phase 1 Note: This is the primary URL for all CLI and SDK operations.
    Returns None if no configuration is found.
    """
    url = os.environ.get("DEEPSECURE_DEEPTRAIL_CONTROL_URL")
    if not url:
        # Check config file
        url = get_deeptrail_control_url()
    return url

def get_effective_deeptrail_gateway_url() -> str | None:
    """
    Returns the effective Deeptrail Gateway URL, checking env vars.
    
    Phase 1 Note: CLI and SDK operations route directly to deeptrail-control.
    Gateway URL is only used for configuration storage and future Phase 2 implementation.
    """
    gateway_url = os.environ.get("DEEPSECURE_DEEPTRAIL_GATEWAY_URL")
    if not gateway_url:
        # Check config file
        gateway_url = get_deeptrail_gateway_url()
    return gateway_url

def get_effective_api_token() -> Optional[str]:
    """
    Gets the API Token, preferring environment variable, then keyring.
    """
    token = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN")
    if token:
        return token
    return get_api_token() 