'''Utility functions for DeepSecure CLI.'''

import typer
import uuid
import json
import string
import random
from rich.console import Console
from rich.syntax import Syntax
from typing import Any, Dict, Optional
from datetime import datetime

# Central console objects for consistent output
console = Console()
error_console = Console(stderr=True, style="bold red")

def print_success(message: str):
    """Prints a formatted success message to the console."""
    console.print(f":white_check_mark: [bold green]Success:[/] {message}")

def print_error(message: str, exit_code: int | None = 1):
    """Prints a formatted error message to stderr and optionally exits.
    
    Args:
        message: The error message to display.
        exit_code: The exit code to use if exiting. If None, does not exit.
    """
    error_console.print(f":x: [bold red]Error:[/] {message}")
    if exit_code is not None:
        raise typer.Exit(code=exit_code)

def print_json(data: Dict[str, Any], pretty: bool = True):
    """
    Prints dictionary data as formatted JSON.
    
    Args:
        data: The dictionary data to print.
        pretty: If True (default), indent the JSON for readability.
    """
    indent = 2 if pretty else None
    try:
        json_str = json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False)
        # Use standard Python print for JSON output to avoid any Rich formatting
        print(json_str)
    except (TypeError, ValueError) as e:
        # Fallback if JSON serialization fails
        print_error(f"Failed to format data as JSON: {e}", exit_code=None)
        console.print(data) # Print raw data as fallback

def generate_id(length: int = 8) -> str:
    """
    Generate a short, random, lowercase alphanumeric ID string.

    Useful for creating simple identifiers for temporary resources.
    
    Args:
        length: The desired length of the ID string (default: 8).
        
    Returns:
        A random lowercase alphanumeric string of the specified length.
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def format_timestamp(timestamp: Optional[int], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a Unix timestamp as a human-readable date/time string.

    Handles None input gracefully by returning a placeholder.
    
    Args:
        timestamp: The Unix timestamp (integer seconds since epoch), or None.
        format_str: The format string compatible with `strftime`.
        
    Returns:
        The formatted date/time string, or "N/A" if timestamp is None.
    """
    if timestamp is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError, TypeError):
        # Handle potential errors with invalid timestamps
        return f"Invalid timestamp ({timestamp})"

# TODO: Add more utility functions as needed (e.g., table rendering, file handling). 