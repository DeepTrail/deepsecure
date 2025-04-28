'''Authentication utility for DeepSecure CLI.

Handles retrieving, storing, and clearing API tokens, primarily using
a local file (`~/.deepsecure/auth/token.json`) for persistence.
Also provides a helper to ensure a token exists, prompting for login if needed.
'''

import os
import json
import sys
import typer # Used for confirmation prompts
from typing import Optional
from pathlib import Path

from . import utils

# TODO: Consider using the `keyring` library for more secure storage 
#       instead of a plain JSON file, although it adds external dependencies.
# Path to store local credentials/tokens
AUTH_DIR = Path(os.path.expanduser("~/.deepsecure/auth"))
TOKEN_FILE = AUTH_DIR / "token.json"

def get_token() -> Optional[str]:
    """
    Get the current authentication token, checking environment variables first.

    Priority:
    1. `DEEPSECURE_API_TOKEN` environment variable.
    2. Token stored in the local `token.json` file.

    Returns:
        The token string if found, None otherwise.
    """
    # Check environment variable first
    token = os.environ.get("DEEPSECURE_API_TOKEN")
    if token:
        return token
    
    # Fall back to the token file
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
                # TODO: Add validation for token format/expiry if structure becomes complex.
                return token_data.get("token")
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or unreadable, treat as no token found
            # TODO: Log this error condition?
            return None
    
    # No token found
    return None

def store_token(token: str) -> None:
    """
    Store an API token securely in the local token file.

    Creates the auth directory if it doesn't exist and sets file
    permissions to be readable/writable only by the current user (600).

    Args:
        token: The API token string to store.
    """
    try:
        # Create the auth directory if it doesn't exist
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        
        # Store the token in a simple JSON structure
        token_data = {"token": token}
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
        
        # Set permissions to restrict access (owner read/write only)
        TOKEN_FILE.chmod(0o600)
    except OSError as e:
        # Handle potential file system errors
        utils.print_error(f"Failed to store token file at {TOKEN_FILE}: {e}", exit_code=None)
        # Depending on severity, might want to raise or exit.

def clear_token() -> None:
    """Remove the locally stored token file.
    
    Handles potential errors if the file doesn't exist or cannot be removed.
    """
    if TOKEN_FILE.exists():
        try:
            TOKEN_FILE.unlink()
        except OSError as e:
            utils.print_error(f"Failed to remove token file {TOKEN_FILE}: {e}", exit_code=None)

def ensure_authenticated() -> str:
    """
    Ensure the user is authenticated (i.e., a token is available).
    
    If no token is found (via environment or file), it prompts the user
    to run the `deepsecure login` command or confirm immediate (placeholder) login.
    
    Returns:
        The authentication token string.
        
    Raises:
        typer.Exit: If authentication is required but the user declines to log in,
                    or if the placeholder login fails.
    """
    token = get_token()
    
    if not token:
        utils.console.print("[yellow]Authentication required.[/] Please run `deepsecure login` or authenticate now.")
        # TODO: Replace this confirm + dummy token with a call to the actual login flow.
        if not typer.confirm("Do you want to authenticate now (using placeholder)?", default=True):
            utils.print_error("Authentication required to proceed.", exit_code=1)
        
        # --- Placeholder Login Flow --- #
        utils.console.print("Performing placeholder authentication...")
        # In a real app, this would involve prompting for credentials or opening a browser.
        try:
            token = f"dummy-token-{utils.generate_id(16)}" # Generate a dummy token
            store_token(token)
            utils.print_success("Successfully authenticated (placeholder). Token stored.")
        except Exception as e:
            utils.print_error(f"Placeholder authentication failed: {e}") # Raise Exit
        # --- End Placeholder --- #

    # Should have a token at this point (either existing or from placeholder login)
    if not token:
        # This case should ideally not be reached if the above logic is sound
        utils.print_error("Authentication failed unexpectedly.", exit_code=1)
        
    return token 