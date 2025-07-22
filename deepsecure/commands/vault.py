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
    agent_id: Optional[str] = typer.Option(None, "--agent-id", help="The ID of the agent to associate the secret with."),
    value: str = typer.Option(
        None,  # Default to None to trigger prompt if not provided
        "--value",
        "-v",
        help="The secret value to store. Can also be set via DEEPSECURE_SECRET_VALUE env var.",
        envvar="DEEPSECURE_SECRET_VALUE",
        prompt="Secret Value",
        hide_input=True,
        confirmation_prompt=True,
    ),
):
    """Stores a secret in the DeepSecure vault."""
    if value is None:
        cli_utils.print_error("Secret value cannot be empty.")
        raise typer.Exit(code=1)
    try:
        client = deepsecure.Client()
        if agent_id:
            client.store_secret(agent_id=agent_id, name=name, secret_value=value)
            cli_utils.print_success(f"Secret '{name}' stored successfully for agent '{agent_id}'.")
        else:
            # We need to decide on a direct storage path.
            # For now, let's assume direct storage requires a target_base_url for the gateway.
            # This part of the CLI needs further design.
            # For this test, we will always provide an agent_id.
            cli_utils.print_error("Storing a global secret via the CLI is not yet fully supported.")
            cli_utils.print_error("Please provide an --agent-id.")
            raise typer.Exit(code=1)

    except DeepSecureError as e:
        cli_utils.print_error(f"Failed to store secret: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        cli_utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)

@app.command("get-secret")
def get_secret(
    name: str = typer.Argument(..., help="The name of the secret to retrieve (e.g., 'DATABASE_URL')."),
    output: str = typer.Option("table", "--output", "-o", help="Output format (`table` or `json`).", case_sensitive=False),
):
    """
    Retrieves a secret from the vault.
    
    This command provides direct access to stored secrets for administrative and CLI use.
    The secret value is retrieved without requiring an agent identity.
    """
    try:
        is_json_output = output.lower() == "json"
        
        client = deepsecure.Client()
        if not is_json_output:
            cli_utils.console.print(f"Retrieving secret '{name}'...")
        
        secret_data = client.get_secret_direct(name)
        
        if is_json_output:
            cli_utils.print_json(secret_data)
        else:
            # Display using Rich table (same as agent list command)
            from datetime import datetime
            from rich.table import Table
            
            # Parse the created_at timestamp for better display
            created_at = secret_data.get("created_at", "")
            if created_at:
                try:
                    # Parse ISO format timestamp and make it more readable
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    formatted_date = created_at
            else:
                formatted_date = "Unknown"
            
            # Create Rich table (same style as agent list)
            table = Table(title="Secret Information", show_lines=True)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Value", style="magenta")
            table.add_column("Created At", style="dim", overflow="fold")
            
            # Add the secret data as a row
            table.add_row(
                secret_data.get('name', 'N/A'),
                secret_data.get('value', 'N/A'),
                formatted_date
            )
            
            cli_utils.console.print(table)
            
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