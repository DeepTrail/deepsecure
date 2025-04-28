'''Utility functions for DeepSecure CLI.'''

import typer
import uuid
import json
import string
import random
from rich.console import Console
from rich.syntax import Syntax
from typing import Any, Dict

console = Console()
error_console = Console(stderr=True, style="bold red")

def print_success(message: str):
    """Prints a success message."""
    console.print(f":white_check_mark: [bold green]Success:[/] {message}")

def print_error(message: str, exit_code: int | None = 1):
    """Prints an error message and optionally exits."""
    error_console.print(f":x: [bold red]Error:[/] {message}")
    if exit_code is not None:
        raise typer.Exit(code=exit_code)

def print_json(data: Dict[str, Any], pretty: bool = True):
    """
    Print data as JSON.
    
    Args:
        data: Dictionary to print as JSON
        pretty: Whether to pretty-print the JSON
    """
    indent = 2 if pretty else None
    json_str = json.dumps(data, indent=indent, sort_keys=True)
    
    # Use rich's syntax highlighting for JSON
    syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
    console.print(syntax)

def generate_id(length: int = 8) -> str:
    """
    Generate a random ID string suitable for naming resources.
    
    Args:
        length: Length of the ID to generate (default: 8)
        
    Returns:
        A lowercase alphanumeric string
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def format_timestamp(timestamp: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a Unix timestamp as a human-readable date/time.
    
    Args:
        timestamp: Unix timestamp
        format_str: Format string for strftime
        
    Returns:
        Formatted date/time string
    """
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(format_str)

# Add more utility functions as needed (e.g., JSON formatting, table rendering) 