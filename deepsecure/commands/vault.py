'''Vault command implementations for the DeepSecure CLI.

Provides subcommands for issuing, revoking, and rotating credentials.
'''

import typer
from typing import Optional
from pathlib import Path

from .. import utils
from ..core import vault_client
from ..exceptions import ApiError, VaultError # Import specific exceptions

app = typer.Typer(
    name="vault",
    help="Manage secure credentials for AI agents.",
    # Add rich help panels for better clarity
    rich_markup_mode="markdown"
)

@app.command("issue")
def issue(
    scope: Optional[str] = typer.Option(
        None, 
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
    local: bool = typer.Option(
        False, 
        "--local", 
        help="Force credential generation locally, even if a backend is configured."
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
    # Explicitly check for required scope
    if scope is None:
        utils.print_error("Option --scope is required.")
        # print_error raises typer.Exit(1), but typer might have exited with 2 already
        # Let's raise explicitly for clarity in testing
        raise typer.Exit(code=1)

    try:
        # Pass the local flag to the core client
        credential = vault_client.client.issue_credential(
            scope=scope,
            ttl=ttl,
            agent_id=agent_id,
            origin_binding=origin_binding,
            local_only=local # Pass the flag
        )
        
        # Format the output based on user preference
        if output.lower() == "json":
            # TODO: Consider filtering the ephemeral_private_key from JSON output by default?
            utils.print_json(data=credential)
        else:
            utils.console.print(f"[bold green]Credential issued successfully! ({'Local' if local else 'Backend (Placeholder)'})[/]")
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
    ),
    local: bool = typer.Option(
        False, 
        help="Only perform revocation in the local list, do not attempt backend revocation."
    )
):
    """Revoke a credential.

    By default, attempts backend revocation (placeholder) AND updates the
    local revocation list (`~/.deepsecure/revoked_creds.json`).
    Use `--local` to only update the local list.
    """
    try:
        # Pass the local flag to the core client method
        result = vault_client.client.revoke_credential(id, local_only=local)
        
        if result:
            if local:
                utils.print_success(f"Added credential {id} to local revocation list.")
            else:
                # TODO: Update this message when backend is implemented
                utils.print_success(f"Revocation initiated for credential {id} (backend placeholder + local update). ")
        else:
            # VaultClient prints specific warnings/errors
            utils.print_error(f"Failed to revoke credential {id}. Check logs for details.", exit_code=1)
            
    except Exception as e:
        utils.print_error(f"Error during revocation: {str(e)}")
        raise typer.Exit(code=1)

@app.command("rotate")
def rotate(
    agent_id: str = typer.Option(
        ...,
        help="Identifier of the agent whose identity key should be rotated. **Required**."
    ),
    type: str = typer.Option(
        "agent-identity",
        help="Type of credential to rotate. Currently only `agent-identity` is supported."
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Force rotation locally, do not attempt backend notification."
    )
):
    """Rotate the long-lived identity key for a specified agent.

    Updates the local identity file (`~/.deepsecure/identities/`) first.
    If `--local` is not used, attempts to notify the backend service.
    """
    if type != "agent-identity":
         utils.print_error(f"Error: Unsupported rotation type '{type}'. Currently only 'agent-identity' is supported.")
         raise typer.Exit(code=1)

    try:
        result = vault_client.client.rotate_credential(
            agent_id=agent_id,
            credential_type=type,
            local_only=local
        )

        status_msg = result.get("status", "Unknown status")
        backend_msg = f"Backend Notified: {result.get('backend_notified', 'N/A')}"
        utils.print_success(f"{status_msg} for agent {agent_id}. {backend_msg}")

    # Catch specific errors first
    except VaultError as e:
         utils.print_error(f"Vault error during rotation for agent {agent_id}: {e}")
         raise typer.Exit(code=1)
    except ApiError as e:
         # This should now catch the detailed ApiError from the client
         utils.print_error(f"Backend API error during rotation notification for agent {agent_id}: {e}")
         raise typer.Exit(code=1)
    # Catch generic/unexpected errors last
    except Exception as e:
        utils.print_error(f"Unexpected error rotating credential for agent {agent_id}: {e}")
        raise typer.Exit(code=1)