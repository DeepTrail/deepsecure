'''Vault command implementations for the DeepSecure CLI.

Provides subcommands for issuing, revoking, and rotating credentials.
'''

import typer
from typing import Optional
import deepsecure
from .. import utils as cli_utils
from ..exceptions import DeepSecureError

app = typer.Typer(
    name="vault",
    help="Manage secrets and credentials.",
    rich_markup_mode="markdown",
)

@app.command()
def store(
    name: str = typer.Argument(..., help="The name of the secret to store."),
    value: str = typer.Option(..., "--value", "-v", help="The secret value to store."),
):
    """Stores a secret in the DeepSecure vault."""
    try:
        client = deepsecure.Client()
        client.store_secret(name=name, value=value)
        cli_utils.print_success(f"Secret '{name}' stored successfully.")
    except DeepSecureError as e:
        cli_utils.print_error(f"Failed to store secret: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        cli_utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)

@app.command("get-secret")
def get_secret(
    name: str = typer.Argument(..., help="The name of the secret to retrieve (e.g., 'DATABASE_URL')."),
    agent_name: str = typer.Option(..., "--agent-name", "-a", help="The name of the agent identity to use for the request."),
    output: str = typer.Option("text", "--output", "-o", help="Output format (`text` or `json`).", case_sensitive=False),
):
    """
    Fetches a secret from the vault for a specific agent.
    
    This command uses the specified agent's identity to securely retrieve the
    secret's value. The value is printed to standard output.
    """
    try:
        is_json_output = output.lower() == "json"
        
        client = deepsecure.Client()
        if not is_json_output:
            cli_utils.console.print(f"Fetching secret '{name}' for agent '{agent_name}'...")
        
        secret = client.get_secret(name=name, agent_name=agent_name)
        
        if is_json_output:
            output_data = {
                "name": secret.name,
                "value": secret.value,
                "expires_at": secret.expires_at.isoformat(),
            }
            cli_utils.print_json(output_data)
        else:
            # By default, just print the value for easy use in scripts
            print(secret.value)
            
    except DeepSecureError as e:
        cli_utils.print_error(f"Failed to get secret: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        cli_utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)

# The 'revoke' and 'rotate' commands from the old file are being removed for now.
# The new SDK design prioritizes the high-level `get_secret` flow.
# Low-level credential and key management commands can be added back later
# if they are deemed necessary for the CLI's purpose. This simplifies the
# command surface to align with the primary SDK use case.