import typer
from rich import print_json
from typing_extensions import Annotated
from typing import Optional

from deepsecure.core import config
from .. import utils as cli_utils

app = typer.Typer(
    name="configure",
    help="Manage DeepSecure CLI configuration.",
    no_args_is_help=True,
)

@app.command("set-url", help="Set the DeepSecure CredService URL.")
def set_url(
    url: Annotated[str, typer.Argument(help="The URL for the CredService (e.g., http://localhost:8000).")]
):
    """
    Sets and stores the DeepSecure CredService URL.
    """
    config.set_credservice_url(url)

@app.command("get-url", help="Get the currently configured DeepSecure CredService URL.")
def get_url():
    """
    Retrieves and displays the DeepSecure CredService URL.
    It checks environment variables first, then the local configuration.
    """
    url = config.get_effective_credservice_url()
    if url:
        print(f"DeepSecure CredService URL: {url}")
    else:
        print("DeepSecure CredService URL is not set. Use 'deepsecure configure set-url <URL>'.")

@app.command("set-token", help="Set and securely store the DeepSecure CredService API token.")
def set_token(
    token_arg: Annotated[Optional[str], typer.Argument(metavar="TOKEN", help="The API token for authenticating with CredService. If omitted, you will be prompted.")] = None
):
    """
    Sets and securely stores the DeepSecure CredService API token using the system keyring.
    """
    actual_token = token_arg
    if actual_token is None:
        actual_token = typer.prompt("Enter API Token", hide_input=True)
    
    if not actual_token: # Catches empty string from prompt or if "" was passed as argument
        print("[bold red]Error: API token cannot be empty.[/bold red]")
        raise typer.Exit(code=1)
        
    config.set_api_token(actual_token)

@app.command("get-token", help="Get the DeepSecure CredService API token (displays if found).")
def get_token_command():
    """
    Retrieves the DeepSecure CredService API token from the system keyring.
    It checks environment variables first, then the keyring.
    Note: This command will display the token if found, use with caution.
    """
    token = config.get_effective_api_token()
    if token:
        # Mask token for display? For now, showing it as it's a 'get' command.
        # Consider if this is too risky. A 'check-token' might be better.
        print(f"DeepSecure CredService API Token (effective): {token}")
        print("[yellow]Warning: Displaying API token. Ensure this is in a secure environment.[/yellow]")
    else:
        print("DeepSecure CredService API token is not set. Use 'deepsecure configure set-token'.")

@app.command("delete-token", help="Delete the stored DeepSecure CredService API token from the keyring.")
def delete_token_command():
    """
    Deletes the DeepSecure CredService API token from the system keyring.
    """
    config.delete_api_token()
    cli_utils.print_success(f"API token deleted from keyring for service '{config.APP_NAME}' and username '{config.API_TOKEN_KEY}'.")

@app.command("set-log-level", help="Set the CLI logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).")
def set_log_level_command(level: str = typer.Argument(..., help="The log level to set.")):
    config.set_cli_log_level(level)

@app.command("show", help="Show all current configuration settings.")
def show_config():
    """Displays current configuration settings including CredService URL and if an API token is stored."""
    url = config.get_effective_credservice_url()
    token_stored = "Yes (keyring or env var)" if config.get_effective_api_token() else "No"
    current_log_level = config.get_cli_log_level()
    
    settings_display = {
        "credservice_url": url if url else "Not set",
        "api_token_stored": token_stored,
        "cli_log_level": current_log_level,
        "config_file_path": str(config.CONFIG_FILE_PATH) if config.CONFIG_FILE_PATH.exists() else "Not created yet"
    }
    cli_utils.print_json(settings_display)
    if not url:
        print("\\n[yellow]Hint: Set CredService URL using 'deepsecure configure set-url <URL>'[/yellow]")
    if not token_stored:
        print("[yellow]Hint: Set API token using 'deepsecure configure set-token'[/yellow]") 