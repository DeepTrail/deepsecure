'''Vault command implementations for the DeepSecure CLI.

Provides subcommands for issuing, revoking, and rotating credentials.
'''

import typer
from typing import Optional
import httpx
import deepsecure
from .. import utils as cli_utils
from ..exceptions import DeepSecureError


def _is_not_found_error(error: Exception) -> bool:
    """Check if the error is a 404 Not Found error."""
    error_str = str(error)
    return "404" in error_str and "Not Found" in error_str


def _mask_secret_value(value: str) -> str:
    """
    Masks a secret value for display, showing only first and last 4 characters.
    
    Examples:
        - "sk-proj-abc...xyz" -> "sk-p****************xyz"
        - "short" -> "s***t"
        - "tiny" -> "****"
    """
    if not value or value == "N/A":
        return value
    
    length = len(value)
    
    if length <= 4:
        # Too short to partially reveal - mask entirely
        return "*" * length
    elif length <= 8:
        # Show first and last character only
        return f"{value[0]}{'*' * (length - 2)}{value[-1]}"
    else:
        # Show first 4 and last 4 characters
        return f"{value[:4]}{'*' * (length - 8)}{value[-4:]}"


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
    target_base_url: Optional[str] = typer.Option(
        None,
        "--target-base-url",
        help="The target base URL for the secret (required for direct storage, optional for agent storage)."
    ),
    labels: Optional[str] = typer.Option(
        None,
        "--labels",
        help="Comma-separated list of labels (key=value) to attach to the secret."
    ),
):
    """Stores a secret in the DeepSecure vault."""
    if value is None:
        cli_utils.print_error("Secret value cannot be empty.")
        raise typer.Exit(code=1)

    # Parse labels if provided
    metadata = {}
    if labels:
        try:
            for label in labels.split(','):
                if '=' in label:
                    key, val = label.split('=', 1)
                    metadata[key.strip()] = val.strip()
                else:
                    # Handle case where label might just be a tag (key only)
                    metadata[label.strip()] = "true" 
        except Exception:
             cli_utils.print_error("Invalid labels format. Expected format: key=value,key2=value2")
             raise typer.Exit(code=1)

    try:
        client = deepsecure.Client(silent_mode=True)
        
        if agent_id:
            # If target_base_url is provided, add it to metadata for agent secrets too
            # This allows the gateway to know where to route requests using this secret
            if target_base_url:
                metadata["target_base_url"] = target_base_url
                
            client.store_secret(agent_id=agent_id, name=name, secret_value=value, metadata=metadata)
            cli_utils.print_success(f"Secret '{name}' stored successfully for agent '{agent_id}'.")
        else:
            # Direct storage (Admin/Global mode)
            if not target_base_url:
                cli_utils.print_error("When storing a secret without an agent ID, --target-base-url is required.")
                raise typer.Exit(code=1)
                
            client.store_secret_direct(
                name=name, 
                value=value, 
                target_base_url=target_base_url, 
                metadata=metadata
            )
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
    output: str = typer.Option("table", "--output", "-o", help="Output format (`table` or `json`).", case_sensitive=False),
    reveal: bool = typer.Option(False, "--reveal", "-r", help="Show the full secret value (default: masked for security)."),
):
    """
    Retrieves a secret from the vault.
    
    This command reassembles the secret from split shares stored across
    the control plane and gateway (split-key architecture).
    
    By default, the secret value is masked for security. Use --reveal to 
    show the full value.
    
    Examples:
        # Retrieve with masked value (default)
        deepsecure vault get-secret openai-api-key
        
        # Retrieve with full value revealed
        deepsecure vault get-secret openai-api-key --reveal
        
        # Output as JSON (always includes full value)
        deepsecure vault get-secret openai-api-key --output json
    """
    try:
        is_json_output = output.lower() == "json"
        
        client = deepsecure.Client(silent_mode=True)
        if not is_json_output:
            cli_utils.console.print(f"Retrieving secret '{name}'...")
        
        secret_data = client.get_secret_direct(name)
        
        if is_json_output:
            # JSON output always includes the full value
            cli_utils.print_json(secret_data)
        else:
            # Display using Rich table
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
            
            # Get the secret value and optionally mask it
            value = secret_data.get('value', 'N/A')
            display_value = value if reveal else _mask_secret_value(value)
            
            # Create Rich table (same style as agent list)
            table = Table(title="Secret Information", show_lines=True)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Value", style="magenta")
            table.add_column("Created At", style="dim", overflow="fold")
            
            # Add the secret data as a row
            table.add_row(
                secret_data.get('name', 'N/A'),
                display_value,
                formatted_date
            )
            
            cli_utils.console.print(table)
            
            # Show hint about --reveal if value was masked
            if not reveal and value and value != "N/A":
                cli_utils.console.print(
                    "\n[dim]💡 Tip: Use --reveal to show the full secret value[/dim]"
                )
            
    except DeepSecureError as e:
        if _is_not_found_error(e):
            cli_utils.console.print(f"[yellow]⚠️  Secret '{name}' not found in vault.[/yellow]")
            cli_utils.console.print(
                f"\n[dim]💡 Tip: Use 'deepsecure vault store {name}' to create it.[/dim]"
            )
        else:
            cli_utils.print_error(f"Failed to get secret: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        if _is_not_found_error(e):
            cli_utils.console.print(f"[yellow]⚠️  Secret '{name}' not found in vault.[/yellow]")
            cli_utils.console.print(
                f"\n[dim]💡 Tip: Use 'deepsecure vault store {name}' to create it.[/dim]"
            )
        else:
            cli_utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)


@app.command("delete")
def delete_secret(
    name: str = typer.Argument(..., help="The name of the secret to delete."),
    force: bool = typer.Option(
        False, 
        "--force", "-f", 
        help="Skip confirmation prompt and delete immediately."
    ),
):
    """
    Deletes a secret from the vault.
    
    This permanently removes the secret by deleting both shares:
    - share_1 from Control Plane database
    - share_2 from Gateway Redis cache
    
    By default, you will be prompted for confirmation. Use --force to skip.
    
    Examples:
        # Delete with confirmation prompt
        deepsecure vault delete openai-api-key
        
        # Delete without confirmation (use with caution)
        deepsecure vault delete openai-api-key --force
    """
    # Confirmation prompt unless --force is used
    if not force:
        confirm = typer.confirm(
            f"⚠️  Are you sure you want to delete secret '{name}'? This cannot be undone"
        )
        if not confirm:
            cli_utils.console.print("[yellow]Deletion cancelled.[/yellow]")
            raise typer.Exit(code=0)
    
    try:
        client = deepsecure.Client(silent_mode=True)
        result = client.delete_secret_direct(name)
        
        if result.get("status") == "deleted":
            cli_utils.print_success(f"Secret '{name}' deleted successfully.")
            
            # Show additional info about gateway share if it was already expired
            if result.get("gateway_share_deleted") is False:
                cli_utils.console.print(
                    "[dim]Note: Gateway share was already expired or missing (Redis TTL).[/dim]"
                )
        else:
            cli_utils.print_error(f"Unexpected response: {result}")
            raise typer.Exit(code=1)
            
    except DeepSecureError as e:
        if _is_not_found_error(e):
            cli_utils.console.print(f"[yellow]⚠️  Secret '{name}' not found in vault.[/yellow]")
        else:
            cli_utils.print_error(f"Failed to delete secret: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        if _is_not_found_error(e):
            cli_utils.console.print(f"[yellow]⚠️  Secret '{name}' not found in vault.[/yellow]")
        else:
            cli_utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_secrets(
    output: str = typer.Option("table", "--output", "-o", help="Output format (table or json)."),
):
    """
    Lists all secrets stored in the vault.
    
    Shows secret names, target URLs, labels, and creation dates.
    Secret values are never displayed for security.
    
    Examples:
        # List all secrets in table format
        deepsecure vault list
        
        # List all secrets as JSON
        deepsecure vault list --output json
    """
    try:
        client = deepsecure.Client(silent_mode=True)
        result = client.list_secrets_direct()
        
        if output.lower() == "json":
            cli_utils.print_json(result)
        else:
            from datetime import datetime
            from rich.table import Table
            
            secrets = result.get("secrets", [])
            count = result.get("count", 0)
            
            if count == 0:
                cli_utils.console.print("[yellow]No secrets found in vault.[/yellow]")
                cli_utils.console.print(
                    "\n[dim]💡 Tip: Use 'deepsecure vault store <name>' to add a secret.[/dim]"
                )
                raise typer.Exit(code=0)
            
            table = Table(title="Secrets in Vault", show_lines=True)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Target URL", style="blue")
            table.add_column("Labels", style="dim")
            table.add_column("Created At", style="dim")
            
            for secret in secrets:
                metadata = secret.get("metadata", {})
                target_url = metadata.get("target_base_url", "-")
                
                # Format labels (exclude target_base_url)
                labels_str = ", ".join(
                    f"{k}={v}" for k, v in metadata.items() 
                    if k != "target_base_url"
                ) or "-"
                
                # Format date
                created_at = secret.get("created_at", "")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_date = dt.strftime("%Y-%m-%d %H:%M UTC")
                    except:
                        formatted_date = created_at
                else:
                    formatted_date = "Unknown"
                
                table.add_row(
                    secret.get("name", "N/A"),
                    target_url,
                    labels_str,
                    formatted_date
                )
            
            cli_utils.console.print(table)
            cli_utils.console.print(f"\n[dim]Found {count} secret(s) in vault.[/dim]")
            
    except DeepSecureError as e:
        cli_utils.print_error(f"Failed to list secrets: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        if not isinstance(e, typer.Exit):
            cli_utils.print_error(f"An unexpected error occurred: {e}")
            raise typer.Exit(code=1)
        raise


# The 'revoke' and 'rotate' commands from the old file are being removed for now.
# The new SDK design prioritizes the high-level `get_secret` flow.
# Low-level credential and key management commands can be added back later
# if they are deemed necessary for the CLI's purpose. This simplifies the
# command surface to align with the primary SDK use case.
