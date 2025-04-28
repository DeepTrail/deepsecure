'''Vault command implementations.'''

import typer
from typing import Optional
from pathlib import Path

from .. import utils
from ..core import vault_client

app = typer.Typer(
    name="vault",
    help="Manage secure credentials for AI agents."
)

@app.command("issue")
def issue(
    scope: str = typer.Option(..., help="Scope for the issued credential (e.g., db:readonly)"),
    ttl: str = typer.Option("5m", help="Time-to-live for the credential (e.g., 5m, 1h)"),
    agent_id: Optional[str] = typer.Option(None, help="Agent identifier (generated if not provided)"),
    origin_binding: bool = typer.Option(True, help="Enforce origin binding for the credential"),
    output: str = typer.Option("text", help="Output format (text, json)")
):
    """Generate ephemeral credentials for AI agents and tools."""
    try:
        # Issue the credential
        credential = vault_client.client.issue_credential(
            scope=scope,
            ttl=ttl,
            agent_id=agent_id,
            origin_binding=origin_binding
        )
        
        # Format the output based on user preference
        if output.lower() == "json":
            utils.print_json(data=credential)
        else:
            utils.console.print(f"[bold green]Credential issued successfully![/]")
            utils.console.print(f"[bold]ID:[/] {credential['id']}")
            utils.console.print(f"[bold]Agent ID:[/] {credential['agent_id']}")
            utils.console.print(f"[bold]Scope:[/] {credential['scope']}")
            utils.console.print(f"[bold]Expires:[/] {utils.format_timestamp(credential['expires_at'])}")
            
            # Show origin binding info if enabled
            if origin_binding:
                utils.console.print("\n[bold cyan]Origin Binding:[/]")
                context = credential.get('origin_context', {})
                for key, value in context.items():
                    utils.console.print(f"  [bold]{key}:[/] {value}")
            
            # Print the credential secret in a secure way
            utils.console.print("\n[bold yellow]Ephemeral Public Key:[/]")
            utils.console.print(credential['ephemeral_public_key'])
            
            utils.console.print("\n[bold yellow]Ephemeral Private Key (sensitive):[/]")
            utils.console.print(credential['ephemeral_private_key'])
            
    except Exception as e:
        utils.print_error(f"Error issuing credential: {str(e)}")
        raise typer.Exit(code=1)
    
@app.command("revoke")
def revoke(
    id: str = typer.Option(..., help="ID of the credential to revoke")
):
    """Revoke a credential issued to an agent/tool."""
    try:
        # Revoke the credential
        result = vault_client.client.revoke_credential(id)
        
        if result:
            utils.print_success(f"Revoked credential: {id}")
        else:
            utils.print_error(f"Failed to revoke credential: {id}")
            raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"Error revoking credential: {str(e)}")
        raise typer.Exit(code=1)

@app.command("rotate")
def rotate(
    type: str = typer.Option(..., help="Type of credential to rotate (e.g., api-key)"),
    path: Optional[Path] = typer.Option(None, help="Path to the config file containing the credential")
):
    """Rotate a long-lived credential securely."""
    try:
        # Rotate the credential
        result = vault_client.client.rotate_credential(
            credential_type=type,
            config_path=str(path) if path else None
        )
        
        utils.console.print(f"Rotated [bold]{type}[/] credential")
        utils.console.print(f"[bold]ID:[/] {result['id']}")
        utils.console.print(f"[bold]Rotated at:[/] {utils.format_timestamp(result['rotated_at'])}")
    except Exception as e:
        utils.print_error(f"Error rotating credential: {str(e)}")
        raise typer.Exit(code=1) 