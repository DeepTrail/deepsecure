'''Utility functions for DeepSecure CLI.'''

import typer
import uuid
import string
import random
from rich.console import Console

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

def generate_id(length: int = 8) -> str:
    """Generate a random ID string suitable for naming resources.
    
    Args:
        length: Length of the ID to generate (default: 8)
        
    Returns:
        A lowercase alphanumeric string
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Add more utility functions as needed (e.g., JSON formatting, table rendering) 