'''Utility functions for DeepSecure CLI.'''

import typer
import uuid
import json
import string
import random
from rich.console import Console
from rich.syntax import Syntax
from typing import Any, Dict, Optional, Union
from datetime import datetime
from pydantic import BaseModel

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

def print_warning(message: str):
    """Prints a formatted warning message to the console."""
    console.print(f":warning: [bold yellow]Warning:[/] {message}")

def print_json(data: Union[Dict[str, Any], BaseModel], pretty: bool = True):
    """
    Prints dictionary or Pydantic model data as formatted JSON.
    
    Args:
        data: The dictionary or Pydantic model to print.
        pretty: If True (default), indent the JSON for readability.
    """
    indent = 2 if pretty else None
    json_str = ""
    try:
        if isinstance(data, BaseModel):
            json_str = data.model_dump_json(indent=indent)
        elif isinstance(data, dict):
            # Ensure datetime objects in dicts are handled if any slip through somehow
            # though Pydantic model_dump() should ideally handle this.
            # A truly robust dict handler would iterate and convert datetimes.
            # For now, assume if it's a dict, it's already JSON-serializable by json.dumps.
            json_str = json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False, default=str)
        else:
            json_str = json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False, default=str)

        print(json_str)
    except (TypeError, ValueError) as e:
        error_console.print(f":x: [bold red]Error:[/] Failed to format data as JSON: {e}")
        console.print(str(data))

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

def parse_ttl_to_seconds(ttl_str: str) -> int:
    """Parses a TTL string (e.g., '5m', '1h', '7d') into seconds.

    Supported suffixes: s (seconds), m (minutes), h (hours), d (days), w (weeks).
    If no suffix, assumes seconds.

    Args:
        ttl_str: The TTL string to parse.

    Returns:
        The TTL in seconds as an integer.

    Raises:
        ValueError: If the TTL format is invalid or suffix is unsupported.
    """
    ttl_str = ttl_str.strip().lower()
    if not ttl_str:
        raise ValueError("TTL string cannot be empty.")

    num_part = ''
    unit_part = ''

    for char in ttl_str:
        if char.isdigit() or (char == '.' and '.' not in num_part):
            num_part += char
        else:
            unit_part += char
            
    if not num_part:
        raise ValueError(f"Invalid TTL format: '{ttl_str}'. No numeric part found.")

    try:
        value = float(num_part) # Use float to allow for e.g. 0.5h
    except ValueError:
        raise ValueError(f"Invalid TTL numeric value: '{num_part}' in '{ttl_str}'.")

    if not unit_part or unit_part == 's':
        multiplier = 1
    elif unit_part == 'm':
        multiplier = 60
    elif unit_part == 'h':
        multiplier = 3600
    elif unit_part == 'd':
        multiplier = 86400
    elif unit_part == 'w':
        multiplier = 604800
    else:
        raise ValueError(f"Invalid TTL unit: '{unit_part}' in '{ttl_str}'. Supported units: s, m, h, d, w.")
    
    total_seconds = value * multiplier
    if total_seconds <= 0:
        raise ValueError(f"TTL must be positive. Calculated {total_seconds}s from '{ttl_str}'.")
    
    return int(total_seconds)

# TODO: Add more utility functions as needed (e.g., table rendering, file handling). 