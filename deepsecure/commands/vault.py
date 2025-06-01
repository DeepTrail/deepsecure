'''Vault command implementations for the DeepSecure CLI.

Provides subcommands for issuing, revoking, and rotating credentials.
'''

import typer
from typing import Optional
from pathlib import Path
from datetime import datetime
import time

from .. import utils as cli_utils # Alias to avoid conflict if utils is used locally
from ..client import client as actual_vault_client # NEW IMPORT for the new client instance
from ..exceptions import ApiError, VaultError, DeepSecureClientError, IdentityManagerError # Import specific exceptions
from ..core.identity_manager import identity_manager as id_manager_instance # Import instance

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
    output: str = typer.Option(
        "text", 
        help="Output format (`text` or `json`)."
    )
):
    """Generate ephemeral credentials for AI agents and tools.

    If no agent_id is provided, a new agent identity will be generated and stored locally.
    The ephemeral private key is included in the output for immediate use
    but should **not** be stored long-term.
    """
    if scope is None:
        cli_utils.print_error("Option --scope is required.")
        raise typer.Exit(code=1)

    try:
        # Ensure consistent TTL parsing to seconds as expected by vault_client.issue
        try:
            ttl_seconds = cli_utils.parse_ttl_to_seconds(ttl)
        except ValueError as e:
            cli_utils.print_error(str(e))
            raise typer.Exit(code=1)

        current_agent_id = agent_id
        if not current_agent_id:
            cli_utils.console.print("No agent ID provided. Generating new local identity...")
            try:
                # Explicitly import the instance here for debugging
                from ..core.identity_manager import identity_manager as id_manager_instance_local
                new_identity = id_manager_instance_local.create_identity(name=f"agent-generated-{int(time.time())}")
                current_agent_id = new_identity["id"]
                cli_utils.console.print(f"New local identity generated: {current_agent_id}", style="green")
            except Exception as e: # Catch broader errors from identity_manager
                cli_utils.print_error(f"Failed to generate new local identity: {e}")
                raise typer.Exit(code=1)
        
        if not current_agent_id: # Should not happen if logic above is correct
            cli_utils.print_error("Critical: Agent ID is still None after attempting generation.")
            raise typer.Exit(code=1)

        # The vault_client.client.issue now expects agent_id and ttl (as int seconds)
        # It does not use origin_binding or local from CLI directly anymore, that logic is internal or part of a different client.
        credential = actual_vault_client.issue(
            scope=scope,
            ttl=ttl_seconds,
            agent_id=current_agent_id
        )
        
        backend_issued = True # Current client.issue always interacts or tries to interact with backend
                               # and doesn't have a pure local_only path like the old vault_client.issue_credential
        origin_msg = "(Backend Flow)" # Reflecting new client behavior
        
        if output.lower() == "json":
            # Pass the Pydantic model directly to print_json
            cli_utils.print_json(credential) 
        else:
            cli_utils.print_success(f"Credential issued successfully! {origin_msg}")
            cli_utils.console.print("\nCredential details:")
            cli_utils.console.print(f"[bold]Credential ID:[/] {credential.credential_id}")
            cli_utils.console.print(f"[bold]Agent ID:[/] {credential.agent_id}")
            cli_utils.console.print(f"[bold]Scope:[/] {credential.scope}")
            cli_utils.console.print(f"[bold]Issued At:[/] {credential.issued_at.isoformat()}")
            cli_utils.console.print(f"[bold]Expires At:[/] {credential.expires_at.isoformat()}")
            
            if credential.origin_context:
                cli_utils.console.print("\nOrigin Binding:")
                for key, value in credential.origin_context.items():
                    cli_utils.console.print(f"  {key}: {value}")

            if credential.ephemeral_public_key_b64:
                cli_utils.console.print(f"  Ephemeral Public Key (b64): {credential.ephemeral_public_key_b64}")
            
            # DO NOT PRINT THE EPHEMERAL PRIVATE KEY TO THE CONSOLE
            # if credential.ephemeral_private_key_b64:
            #     cli_utils.console.print(f"  [yellow]Ephemeral Private Key (b64): {credential.ephemeral_private_key_b64}[/yellow]")
            # Always print the warning if an ephemeral private key was part of the response, even if not shown
            if hasattr(credential, 'ephemeral_private_key_b64') and credential.ephemeral_private_key_b64:
                cli_utils.console.print("  [bold red]Warning: An ephemeral private key was generated. Handle it securely if obtained programmatically. It will not be displayed here.[/bold red]")

    except VaultError as e:
        cli_utils.print_error(f"Vault operation error: {str(e)}")
        raise typer.Exit(code=1)
    except DeepSecureClientError as e: # Catching the error from client.py
        cli_utils.print_error(f"Client error: {str(e)}")
        raise typer.Exit(code=1)
    except ApiError as e:
        cli_utils.print_error(f"API error: {str(e)}")
        raise typer.Exit(code=1)
    except ValueError as e: # Catch TTL parsing or other value errors
        cli_utils.print_error(f"Input error: {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e: # Generic catch-all for unexpected issues
        cli_utils.print_error(f"An unexpected error occurred in 'vault issue': {type(e).__name__} - {str(e)}")
        raise typer.Exit(code=1)

@app.command("revoke")
def revoke(
    credential_id: str = typer.Option(..., "--credential-id", "--id", help="ID of the credential to revoke. **Required**."),
):
    """Revoke a credential via the backend service."""
    try:
        # The client method revoke() in deepsecure.client.VaultClientService expects credential_id
        revoke_response_model = actual_vault_client.revoke(credential_id=credential_id)
        if revoke_response_model and revoke_response_model.status == "revoked":
            cli_utils.print_success(f"Successfully revoked credential {credential_id}. Status: {revoke_response_model.status}")
        elif revoke_response_model:
            cli_utils.print_warning(f"Credential {credential_id} revocation status: {revoke_response_model.status}")
        else:
            cli_utils.print_error(f"Failed to revoke credential {credential_id}. No response from client.", exit_code=1)
            
    except DeepSecureClientError as e:
        cli_utils.print_error(f"Client error during revocation: {str(e)}")
        raise typer.Exit(code=1)
    except ApiError as e:
        cli_utils.print_error(f"API error during revocation: {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        cli_utils.print_error(f"Error during revocation: {str(e)}")
        raise typer.Exit(code=1)

@app.command("rotate")
def rotate(
    agent_id: str = typer.Option(..., help="Identifier of the agent whose identity key should be rotated. **Required**.")
):
    """Rotate the long-lived identity key for a specified agent via the backend service.

    This command will generate a new Ed25519 key pair locally for the agent,
    then notify the backend service of the new public key. If successful,
    the new local keys (private key in keyring, public metadata in file) are updated.
    """
    cli_utils.console.print(f"Initiating key rotation for agent: {agent_id}")
    try:
        cli_utils.console.print("Generating new local Ed25519 key pair...")
        new_keys = id_manager_instance.generate_ed25519_keypair_raw_b64()
        new_public_key_b64 = new_keys["public_key"]
        new_private_key_b64 = new_keys["private_key"]
        cli_utils.console.print(f"New key pair generated. Public key starts: {new_public_key_b64[:20]}...")

        cli_utils.console.print(f"Notifying backend of new public key for agent {agent_id}...")
        rotation_response = actual_vault_client.rotate(agent_id=agent_id, new_public_key_b64=new_public_key_b64)

        if rotation_response and rotation_response.status == "success_on_client_for_204":
            cli_utils.print_success(f"Backend successfully notified of key rotation for agent {agent_id}.")
            
            cli_utils.console.print(f"Updating local identity store for agent {agent_id} with new keys...")
            try:
                existing_identity_metadata = id_manager_instance.load_identity(agent_id)
                original_name = existing_identity_metadata.get("name") if existing_identity_metadata else None
                original_created_at = int(existing_identity_metadata.get("created_at", int(time.time()))) if existing_identity_metadata else int(time.time())

                id_manager_instance.persist_generated_identity(
                    agent_id=agent_id,
                    public_key_b64=new_public_key_b64,
                    private_key_b64=new_private_key_b64,
                    name=original_name,
                    created_at_timestamp=original_created_at
                )
                cli_utils.print_success(f"Local identity for agent {agent_id} updated successfully.")
            except IdentityManagerError as e_persist:
                cli_utils.print_error(f"Backend key rotation successful, BUT FAILED to update local identity store for agent {agent_id}: {e_persist}")
                cli_utils.print_warning("CRITICAL: Your local keys are now out of sync with the backend. This may lead to signing issues. Consider re-registering or manual intervention.")
        elif rotation_response:
            cli_utils.print_error(f"Backend rotation notification for agent {agent_id} returned status: {rotation_response.status}. Local keys NOT updated.")
            raise typer.Exit(code=1)
        else:
            cli_utils.print_error(f"Key rotation for agent {agent_id} failed to get successful confirmation from backend. Local keys NOT updated.")
            raise typer.Exit(code=1)

    except IdentityManagerError as e_id:
         cli_utils.print_error(f"Identity management error during rotation for agent {agent_id}: {e_id}")
         raise typer.Exit(code=1)
    except DeepSecureClientError as e_client:
         cli_utils.print_error(f"Client error during rotation for agent {agent_id}: {e_client}")
         raise typer.Exit(code=1)
    except ApiError as e_api:
         cli_utils.print_error(f"Backend API error during rotation for agent {agent_id}: {e_api}. Local keys NOT updated.")
         raise typer.Exit(code=1)
    except Exception as e_exc:
        cli_utils.print_error(f"Unexpected error rotating key for agent {agent_id}: {type(e_exc).__name__} - {e_exc}. Local keys NOT updated.")
        raise typer.Exit(code=1)