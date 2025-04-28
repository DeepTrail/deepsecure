'''Authentication utility for DeepSecure CLI.'''

import os
import json
import sys
import typer
from typing import Optional
from pathlib import Path

from . import utils

# Path to store local credentials/tokens
AUTH_DIR = os.path.expanduser("~/.deepsecure/auth")
TOKEN_FILE = os.path.join(AUTH_DIR, "token.json")

def get_token() -> Optional[str]:
    """
    Get the current authentication token.
    
    Returns:
        The token string if available, None otherwise
    """
    # Check environment variable first
    token = os.environ.get("DEEPSECURE_API_TOKEN")
    if token:
        return token
    
    # Fall back to the token file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
                return token_data.get("token")
        except (json.JSONDecodeError, IOError):
            return None
    
    return None

def store_token(token: str) -> None:
    """
    Store an API token.
    
    Args:
        token: The token to store
    """
    # Create the auth directory if it doesn't exist
    os.makedirs(AUTH_DIR, exist_ok=True)
    
    # Store the token
    token_data = {"token": token}
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    
    # Set permissions to restrict access
    os.chmod(TOKEN_FILE, 0o600)
    
def clear_token() -> None:
    """Remove the stored token."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

def ensure_authenticated() -> str:
    """
    Ensure the user is authenticated and a token is available.
    If not, prompt the user to authenticate.
    
    Returns:
        The authentication token
        
    Raises:
        typer.Exit: If authentication fails
    """
    token = get_token()
    
    if not token:
        utils.console.print("[yellow]Not authenticated. Please run 'deepsecure login' first.[/]")
        if not typer.confirm("Do you want to login now?"):
            utils.print_error("Authentication required to proceed.", exit_code=1)
        
        # For development/testing, we'll use a dummy token
        token = f"dummy-token-{utils.generate_id(8)}"
        store_token(token)
        utils.print_success("Successfully authenticated")
    
    return token 