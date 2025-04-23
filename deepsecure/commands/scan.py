'''Credential scanning command implementations.'''

import typer
from pathlib import Path
from typing import List, Optional

from .. import utils
from ..core import scanner

app = typer.Typer(
    name="scan",
    help="Scan for exposed secrets or credentials in code, configs, or memory."
)

@app.callback(invoke_without_command=True)
def main(
    path: List[Path] = typer.Argument(None, help="Paths to scan (files or directories)"),
    live: bool = typer.Option(False, help="Scan running processes for secrets in memory"),
    pid: Optional[int] = typer.Option(None, help="Process ID to scan (requires --live)"),
    exclude: Optional[List[str]] = typer.Option(None, help="Patterns to exclude"),
    ci: bool = typer.Option(False, help="Run in CI mode (non-interactive, exit code on findings)"),
    severity: str = typer.Option("medium", help="Minimum severity to report (low, medium, high, critical)")
):
    """Scan code, configs, logs, or running processes for exposed secrets."""
    # We only proceed if called directly (not via a subcommand)
    if typer.Context.get_current().invoked_subcommand is not None:
        return
    
    if live:
        # If live scanning, ensure we have a PID or scan all processes
        if pid:
            utils.console.print(f"Scanning live process with PID: [bold]{pid}[/]")
            _scan_live_process(pid)
        else:
            utils.console.print("Scanning all running processes...")
            _scan_all_processes()
    elif path:
        # If paths provided, scan those
        for p in path:
            if p.is_dir():
                utils.console.print(f"Scanning directory: [bold]{p}[/]")
                _scan_directory(p, exclude, severity)
            elif p.is_file():
                utils.console.print(f"Scanning file: [bold]{p}[/]")
                _scan_file(p, severity)
            else:
                utils.print_error(f"Path not found: {p}", exit_code=None)
    else:
        # No paths provided, scan current directory
        utils.console.print("No paths provided, scanning current directory")
        _scan_directory(Path("."), exclude, severity)


@app.command("live")
def live(
    pid: Optional[int] = typer.Option(None, help="Process ID to scan")
):
    """Scan running processes or environment for secrets in memory."""
    if pid:
        utils.console.print(f"Scanning live process with PID: [bold]{pid}[/]")
        _scan_live_process(pid)
    else:
        utils.console.print("Scanning all running processes...")
        _scan_all_processes()


# Helper functions for different scan types

def _scan_directory(path: Path, exclude: Optional[List[str]], severity: str):
    """Internal function to scan a directory."""
    # Placeholder - would call scanner.scan_directory() in real implementation
    utils.console.print("[yellow]Scanning files...[/]")
    
    # Simulate finding some secrets
    utils.console.print("[bold red]Found potential secrets:[/]")
    utils.console.print(f"[red]HIGH[/]: AWS key in [bold]{path}/config.json[/] on line 42")
    utils.console.print(f"[yellow]MEDIUM[/]: Password in [bold]{path}/setup.py[/] on line 15")
    
    utils.print_success("Scan complete")


def _scan_file(path: Path, severity: str):
    """Internal function to scan a single file."""
    # Placeholder - would call scanner.scan_file() in real implementation
    utils.console.print("[yellow]Scanning file...[/]")
    
    # Simulate finding a secret
    utils.console.print("[bold yellow]Found potential secret:[/]")
    utils.console.print(f"[yellow]MEDIUM[/]: API token in [bold]{path}[/] on line 23")
    
    utils.print_success("Scan complete")


def _scan_live_process(pid: int):
    """Internal function to scan a running process."""
    # Placeholder - would call scanner.scan_process() in real implementation
    utils.console.print("[yellow]Scanning process memory...[/]")
    
    # Simulate finding a secret in memory
    utils.console.print("[bold red]Found secrets in memory:[/]")
    utils.console.print(f"[red]HIGH[/]: Database password in process {pid}")
    
    utils.print_success("Memory scan complete")


def _scan_all_processes():
    """Internal function to scan all running processes."""
    # Placeholder - would call scanner.scan_all_processes() in real implementation
    utils.console.print("[yellow]Scanning all processes...[/]")
    
    # Simulate finding secrets
    utils.console.print("[bold red]Found secrets in memory:[/]")
    utils.console.print("[red]HIGH[/]: Database password in process 1234")
    utils.console.print("[yellow]MEDIUM[/]: Auth token in process 5678")
    
    utils.print_success("Memory scan complete") 