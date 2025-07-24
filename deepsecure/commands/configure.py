import typer
from rich import print_json
from typing_extensions import Annotated
from typing import Optional

from deepsecure._core import config
from .. import utils as cli_utils

app = typer.Typer(
    name="configure",
    help="Manage DeepSecure CLI configuration.",
    no_args_is_help=True,
)

@app.command("set-url", help="Set the DeepSecure Deeptrail Control URL.")
def set_url(
    url: Annotated[str, typer.Argument(help="The URL for the Deeptrail Control service (e.g., http://localhost:8000).")]
):
    """
    Sets and stores the DeepSecure Deeptrail Control URL.
    """
    config.set_deeptrail_control_url(url)

@app.command("get-url", help="Get the currently configured DeepSecure Deeptrail Control URL.")
def get_url():
    """
    Retrieves and displays the DeepSecure Deeptrail Control URL.
    It checks environment variables first, then the local configuration.
    """
    url = config.get_effective_deeptrail_control_url()
    if url:
        print(f"DeepSecure Deeptrail Control URL: {url}")
    else:
        print("DeepSecure Deeptrail Control URL is not set. Use 'deepsecure configure set-url <URL>'.")

@app.command("set-gateway-url", help="Set the DeepSecure Gateway URL.")
def set_gateway_url(
    url: Annotated[str, typer.Argument(help="The URL for the DeepSecure Gateway service (e.g., http://localhost:8002).")]
):
    """
    Sets and stores the DeepSecure Gateway URL.
    """
    config.set_deeptrail_gateway_url(url)

@app.command("get-gateway-url", help="Get the currently configured DeepSecure Gateway URL.")
def get_gateway_url():
    """
    Retrieves and displays the DeepSecure Gateway URL.
    It checks environment variables first, then the local configuration.
    """
    url = config.get_effective_deeptrail_gateway_url()
    if url:
        print(f"DeepSecure Gateway URL: {url}")
    else:
        print("DeepSecure Gateway URL is not set. Use 'deepsecure configure set-gateway-url <URL>'.")

@app.command("set-token", help="Set and securely store the DeepSecure Deeptrail Control API token.")
def set_token(
    token_arg: Annotated[Optional[str], typer.Argument(metavar="TOKEN", help="The API token for authenticating with Deeptrail Control. If omitted, you will be prompted.")] = None
):
    """
    Sets and securely stores the DeepSecure Deeptrail Control API token using the system keyring.
    """
    actual_token = token_arg
    if actual_token is None:
        actual_token = typer.prompt("Enter API Token", hide_input=True)
    
    if not actual_token: # Catches empty string from prompt or if "" was passed as argument
        print("[bold red]Error: API token cannot be empty.[/bold red]")
        raise typer.Exit(code=1)
        
    config.set_api_token(actual_token)

@app.command("get-token", help="Get the DeepSecure Deeptrail Control API token (displays if found).")
def get_token_command():
    """
    Retrieves the DeepSecure Deeptrail Control API token from the system keyring.
    It checks environment variables first, then the keyring.
    Note: This command will display the token if found, use with caution.
    """
    token = config.get_effective_api_token()
    if token:
        # Mask token for display? For now, showing it as it's a 'get' command.
        # Consider if this is too risky. A 'check-token' might be better.
        print(f"DeepSecure Deeptrail Control API Token (effective): {token}")
        print("[yellow]Warning: Displaying API token. Ensure this is in a secure environment.[/yellow]")
    else:
        print("DeepSecure Deeptrail Control API token is not set. Use 'deepsecure configure set-token'.")

@app.command("delete-token", help="Delete the stored DeepSecure Deeptrail Control API token from the keyring.")
def delete_token_command():
    """
    Deletes the DeepSecure Deeptrail Control API token from the system keyring.
    """
    config.delete_api_token()
    cli_utils.print_success(f"API token deleted from keyring for service '{config.APP_NAME}' and username '{config.API_TOKEN_KEY}'.")

@app.command("set-log-level", help="Set the CLI logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).")
def set_log_level_command(level: str = typer.Argument(..., help="The log level to set.")):
    config.set_cli_log_level(level)

@app.command("show", help="Show all current configuration settings.")
def show_config():
    """Displays current configuration settings including Deeptrail Control URL, Gateway URL, and if an API token is stored."""
    control_url = config.get_effective_deeptrail_control_url()
    gateway_url = config.get_effective_deeptrail_gateway_url()
    token_stored = "Yes (keyring or env var)" if config.get_effective_api_token() else "No"
    current_log_level = config.get_cli_log_level()
    
    settings_display = {
        "deeptrail_control_url": control_url if control_url else "Not set",
        "deeptrail_gateway_url": gateway_url if gateway_url else "Not set",
        "api_token_stored": token_stored,
        "cli_log_level": current_log_level,
        "config_file_path": str(config.CONFIG_FILE_PATH) if config.CONFIG_FILE_PATH.exists() else "Not created yet"
    }
    cli_utils.print_json(settings_display)
    if not control_url:
        print("\\n[yellow]Hint: Set Deeptrail Control URL using 'deepsecure configure set-url <URL>'[/yellow]")
    if not gateway_url:
        print("[yellow]Hint: Set Gateway URL using 'deepsecure configure set-gateway-url <URL>'[/yellow]")
    if not token_stored:
        print("[yellow]Hint: Set API token using 'deepsecure configure set-token'[/yellow]") 