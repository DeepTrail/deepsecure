'''Vault command implementations for the DeepSecure CLI.

Provides subcommands for issuing, revoking, and rotating credentials.
'''

import typer
from typing import Optional
from pathlib import Path

from .. import utils
from ..core import vault_client

app = typer.Typer(
    name="vault",
    help="Manage secure credentials for AI agents.",
    # Add rich help panels for better clarity
    rich_markup_mode="markdown"
)

@app.command("issue")
def issue(
    scope: str = typer.Option(
        ..., 
        help="Scope for the issued credential (e.g., `db:readonly`, `api:full`). **Required**."
    ),
    ttl: str = typer.Option(
        "5m", 
        help="Time-to-live for the credential (e.g., `5m`, `1h`, `7d`). Suffixes: s, m, h, d, w."
    ),
    agent_id: Optional[str] = typer.Option(
        None, 
        help="Agent identifier. If not provided, a new identity will be generated and stored locally."
    ),
    origin_binding: bool = typer.Option(
        True, 
        help="Enforce origin binding. Binds the credential to the context (hostname, user, etc.) where it was issued."
    ),
    output: str = typer.Option(
        "text", 
        help="Output format (`text` or `json`)."
    )
):
    """Generate ephemeral credentials for AI agents and tools.

    This command interfaces with the VaultClient to:
    1. Obtain or create an agent identity.
    2. Generate an ephemeral X25519 key pair.
    3. Sign the ephemeral public key with the agent's long-term Ed25519 key.
    4. Capture origin context if `origin_binding` is enabled.
    5. Assemble and return the credential token.

    The ephemeral private key is included in the output for immediate use
    but should **not** be stored long-term.
    """
    try:
        # Issue the credential using the core client
        credential = vault_client.client.issue_credential(
            scope=scope,
            ttl=ttl,
            agent_id=agent_id,
            origin_binding=origin_binding
        )
        
        # Format the output based on user preference
        if output.lower() == "json":
            # TODO: Consider filtering the ephemeral_private_key from JSON output by default?
            utils.print_json(data=credential)
        else:
            utils.console.print(f"[bold green]Credential issued successfully![/]")
            utils.console.print(f"[bold]ID:[/] {credential['id']}")
            utils.console.print(f"[bold]Agent ID:[/] {credential['agent_id']}")
            utils.console.print(f"[bold]Scope:[/] {credential['scope']}")
            utils.console.print(f"[bold]Expires:[/] {utils.format_timestamp(credential['expires_at'])}")
            
            # Show origin binding info if enabled
            if origin_binding and credential.get('origin_context'):
                utils.console.print("\n[bold cyan]Origin Binding:[/]")
                context = credential.get('origin_context', {})
                for key, value in context.items():
                    # Handle potential non-string values safely
                    utils.console.print(f"  [bold]{key}:[/] {str(value)}") 
            
            # Print the public key
            utils.console.print("\n[bold yellow]Ephemeral Public Key:[/]")
            utils.console.print(credential['ephemeral_public_key'])
            
            # Print the private key - WARNING about sensitivity
            utils.console.print("\n[bold red]Ephemeral Private Key (sensitive - handle with care):[/]")
            utils.console.print(credential['ephemeral_private_key'])
            
    except Exception as e:
        # TODO: Catch more specific exceptions (VaultError, ValueError) for tailored messages.
        utils.print_error(f"Error issuing credential: {str(e)}")
        raise typer.Exit(code=1)
    
@app.command("revoke")
def revoke(
    id: str = typer.Option(
        ..., 
        help="ID of the credential to revoke. **Required**."
    )
):
    """Revoke a credential issued to an agent/tool.

    **(Placeholder)** This command currently only logs the revocation attempt.
    A backend system is required to track and manage credential validity.
    """
    try:
        # Call the core client to revoke the credential
        # TODO: Implement real revocation call to a backend.
        result = vault_client.client.revoke_credential(id)
        
        if result:
            utils.print_success(f"Revoked credential: {id}")
        else:
            # TODO: Improve error message if revocation fails in a real implementation.
            utils.print_error(f"Failed to revoke credential: {id}")
            raise typer.Exit(code=1)
    except Exception as e:
        # TODO: Catch more specific exceptions.
        utils.print_error(f"Error revoking credential: {str(e)}")
        raise typer.Exit(code=1)

@app.command("rotate")
def rotate(
    type: str = typer.Option(
        ..., 
        help="Type of credential to rotate (e.g., `api-key`). **Required**."
        # TODO: Clarify what types are supported, likely agent long-term keys.
    ),
    path: Optional[Path] = typer.Option(
        None, 
        help="Path to the config file containing the credential (if applicable)."
        # TODO: Define how path is used in rotation.
    )
):
    """Rotate a long-lived credential securely.

    **(Placeholder)** This command simulates rotation but doesn't perform
    actual key rotation yet. Primarily intended for rotating agent long-term keys.
    """
    try:
        # Call the core client to rotate the credential
        # TODO: Implement real rotation logic, likely for agent identity keys.
        result = vault_client.client.rotate_credential(
            credential_type=type,
            config_path=str(path) if path else None
        )
        
        # TODO: Provide more meaningful output upon successful rotation.
        utils.console.print(f"Rotated [bold]{type}[/] credential (Placeholder)")
        utils.console.print(f"[bold]New ID/Reference:[/] {result['id']}")
        utils.console.print(f"[bold]Rotated at:[/] {utils.format_timestamp(result['rotated_at'])}")
    except Exception as e:
        # TODO: Catch more specific exceptions.
        utils.print_error(f"Error rotating credential: {str(e)}")
        raise typer.Exit(code=1) 