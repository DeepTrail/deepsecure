# deepsecure/commands/agent.py
import typer
from typing import Optional, List, Dict, Any
from pathlib import Path
import time # For created_at timestamp
import logging # <--- Added import for logging
import base64 # For validating public key from file if needed
from typer.core import TyperGroup

from .. import utils
from ..core.agent_client import client as agent_service_client # Correct import name
from ..core.identity_manager import identity_manager # Import constant for keyring direct use
from ..exceptions import ApiError, IdentityManagerError # Corrected import
from ..core import schemas as client_schemas # For request/response models if needed by CLI
import keyring # Import keyring for direct use if needed for set_password

logger = logging.getLogger(__name__) # <--- Added logger instance

app = typer.Typer(
    name="agent",
    help="Manage DeepSecure agent identities and lifecycle.",
    rich_markup_mode="markdown"
)

# Placeholder for agent_id argument type
AgentID = typer.Argument(..., help="The unique identifier of the agent.")

# --- Register Command ---
@app.command("register")
def register(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="A human-readable name for the agent."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="A description for the agent."),
    public_key_path: Optional[Path] = typer.Option(
        None,
        "--public-key",
        "-pk",
        help="Path to a file containing the agent's Ed25519 public key (base64-encoded raw bytes). If not provided, a new key pair will be generated.",
        exists=True, # typer will check if file exists if path is given
        file_okay=True,
        dir_okay=False,
        readable=True
    ),
    output: str = typer.Option("text", "--output", "-o", help="Output format (`text` or `json`). Case-insensitive.", case_sensitive=False)
):
    """Explicitly register a new agent with the DeepSecure credential service.

    If a public key path is provided, that key is registered. The private key is assumed
    to be managed externally.
    If no public key path is provided, a new Ed25519 key pair is generated. The private
    key is stored in the system keyring, and public metadata (including the public key)
    is stored in a local JSON file. The public key is then registered with the backend.
    The agent ID is always assigned by the backend service.
    """
    try:
        service_public_key_b64: Optional[str] = None
        generated_keys_locally: Optional[Dict[str,str]] = None # To hold new_keys if generated

        if public_key_path:
            try:
                service_public_key_b64 = public_key_path.read_text().strip()
                if not service_public_key_b64:
                    utils.print_error("Public key file is empty.")
                    raise typer.Exit(code=1)
                try: # Basic validation of the provided public key
                    pk_bytes = base64.b64decode(service_public_key_b64, validate=True)
                    if len(pk_bytes) != 32:
                        utils.print_error("Provided public key (decoded) must be 32 bytes.")
                        raise typer.Exit(code=1)
                except Exception as e:
                    utils.print_error(f"Public key file content is not valid base64 or not 32 bytes once decoded: {e}")
                    raise typer.Exit(code=1)
                utils.console.print(f"Using public key from file: {public_key_path}")
            except IOError as e:
                utils.print_error(f"Error reading public key file {public_key_path}: {e}")
                raise typer.Exit(code=1)
        else:
            utils.console.print("No public key file provided. Generating new key pair locally...")
            generated_keys_locally = identity_manager.generate_ed25519_keypair_raw_b64()
            service_public_key_b64 = generated_keys_locally["public_key"]
            utils.console.print("New key pair generated.")

        if not service_public_key_b64:
            utils.print_error("Critical error: Failed to obtain a public key for registration.")
            raise typer.Exit(code=1)

        utils.console.print("Registering public key with the backend service...")
        backend_response = agent_service_client.register_agent(
            public_key=service_public_key_b64,
            name=name,
            description=description
        )
        
        credservice_agent_id = backend_response.get("agent_id")
        if not credservice_agent_id:
            utils.print_error("Backend registration succeeded but did not return an agent ID.")
            raise typer.Exit(code=1)

        final_name = backend_response.get("name", name)
        final_description = backend_response.get("description", description)
        # Backend's 'publicKey' is base64 of raw bytes, same as service_public_key_b64 we sent/generated.
        # The fingerprint from backend might be different if it uses a different method.
        # We'll use our CLI's method for consistency in display.
        fingerprint = identity_manager.get_public_key_fingerprint(service_public_key_b64)
        backend_created_at_str = backend_response.get("created_at") # This is likely an ISO string

        local_keys_persisted = False
        if generated_keys_locally:
            try:
                # Persist the generated identity: private key to keyring, public metadata to file,
                # using the agent_id obtained from the backend.
                identity_manager.persist_generated_identity(
                    agent_id=credservice_agent_id,
                    public_key_b64=generated_keys_locally["public_key"],
                    private_key_b64=generated_keys_locally["private_key"],
                    name=final_name,
                    created_at_timestamp=int(time.time()) # Using local time for metadata file for now
                )
                local_keys_persisted = True
                # Message about keyring storage is printed by IdentityManager
            except Exception as e:
                utils.print_error(f"Backend registration succeeded for {credservice_agent_id}, but failed to persist local keys/keyring entry: {e}")
                # Continue to show backend success, but warn about local state.
        
        output_data = {
            "agent_id": credservice_agent_id,
            "name": final_name,
            "description": final_description,
            "public_key_fingerprint": fingerprint,
            "backend_created_at": backend_created_at_str,
            "local_keys_persisted_successfully": local_keys_persisted,
            "local_identity_metadata_file": str(identity_manager.identity_store_path / f"{credservice_agent_id}.json") if generated_keys_locally else None,
            "message": f"Agent '{final_name if final_name else credservice_agent_id}' registered with backend."
        }

        if output.lower() == "json":
            utils.print_json(output_data)
        else:
            utils.print_success(output_data["message"])
            utils.console.print(f"  Agent ID: [bold]{output_data['agent_id']}[/bold]")
            if output_data['name']:
                utils.console.print(f"  Name: {output_data['name']}")
            if output_data['description']:
                utils.console.print(f"  Description: {output_data['description']}")
            if output_data['public_key_fingerprint']:
                utils.console.print(f"  Public Key Fingerprint: {output_data['public_key_fingerprint']}")
            if output_data['backend_created_at']:
                utils.console.print(f"  Backend Registered At: {output_data['backend_created_at']}")
            
            if generated_keys_locally:
                if local_keys_persisted:
                    utils.console.print(f"  [green]Local private key stored in system keyring.[/green]")
                    utils.console.print(f"  [green]Local public metadata at: {output_data['local_identity_metadata_file']}[/green]")
                else:
                    utils.console.print(f"  [bold red]Failed to store local private key in system keyring or save metadata file.[/bold red]")
            elif public_key_path:
                 utils.console.print(f"  [yellow]Note: Public key was provided from file. Private key is managed externally.[/yellow]")

    except IdentityManagerError as e:
        utils.print_error(f"Local identity management error: {e}")
        raise typer.Exit(code=1)
    except ApiError as e: 
        utils.print_error(f"Backend API error during registration: {e.message} (Status: {e.status_code}) Details: {e.error_details}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred during agent registration: {type(e).__name__} - {e}")
        raise typer.Exit(code=1)

# --- List Command ---
@app.command("list")
def list_agents( # Renamed from 'list' to avoid conflict with Python's list
    local: bool = typer.Option(False, "--local", help="Display only agents with locally stored identities."),
    remote: bool = typer.Option(False, "--remote", help="Display only agents registered with the remote credservice. (Default if no flags)"),
    skip: int = typer.Option(0, "--skip", help="Number of records to skip for pagination when fetching remote agents."),
    limit: int = typer.Option(100, "--limit", help="Maximum number of records to return when fetching remote agents."),
    output: str = typer.Option("table", "--output", "-o", help="Output format (`table`, `json`, `text`). Case-insensitive.", case_sensitive=False)
):
    """List agents known to DeepSecure (locally and/or remotely)."""
    agents_to_display = []
    fetch_local = local
    fetch_remote = remote

    if not local and not remote:
        fetch_remote = True
    
    try:
        if fetch_local:
            utils.console.print("Fetching locally stored agent identities...")
            local_identities_raw = identity_manager.list_identities()
            for ident in local_identities_raw:
                agents_to_display.append({
                    "agent_id": ident.get("id", "N/A"),
                    "name": ident.get("name", "N/A"),
                    "status": "local_only", 
                    "source": "local",
                    "public_key_fingerprint": ident.get("public_key_fingerprint", "N/A"),
                    "created_at": utils.format_timestamp(ident.get("created_at")) if ident.get("created_at") else "N/A"
                })
            utils.console.print(f"Found {len(local_identities_raw)} local identity/identities.")

        if fetch_remote:
            utils.console.print(f"Fetching agent identities from the backend service (skip={skip}, limit={limit})...")
            remote_response = agent_service_client.list_agents(skip=skip, limit=limit)
            remote_identities_raw = remote_response.get("agents", [])
            total_remote = remote_response.get("total", len(remote_identities_raw))

            for ident_data in remote_identities_raw: # Renamed loop var to avoid conflict if ident is a type
                fingerprint = "N/A"
                public_key_b64 = ident_data.get("publicKey") # Corrected to use "publicKey" from backend schema
                if public_key_b64:
                    try:
                        fingerprint = identity_manager.get_public_key_fingerprint(public_key_b64)
                    except IdentityManagerError as e:
                        logger.warning(f"Could not generate fingerprint for remote agent {ident_data.get('agent_id')}: {e}")
                        fingerprint = "Error/Invalid"
                
                agents_to_display.append({
                    "agent_id": ident_data.get("agent_id", "N/A"),
                    "name": ident_data.get("name", "N/A"),
                    "status": ident_data.get("status", "unknown"), 
                    "source": "remote", 
                    "public_key_fingerprint": fingerprint,
                    "created_at": ident_data.get("created_at", "N/A") 
                })
            utils.console.print(f"Found {len(remote_identities_raw)} remote agent(s) from backend (total available: {total_remote}).")

        if not agents_to_display:
            utils.console.print("No agents found.")
            return # Explicit return to ensure no other code in the try block runs.

        # Simple de-duplication based on agent_id, preferring remote entries if IDs match
        # More sophisticated merging could be done if necessary
        unique_agents = {}
        for agent in agents_to_display:
            agent_id = agent["agent_id"]
            if agent_id not in unique_agents or agent["source"] == "remote":
                unique_agents[agent_id] = agent
        final_agents_list = list(unique_agents.values())


        if output.lower() == "json":
            utils.print_json(final_agents_list)
        elif output.lower() == "table":
            from rich.table import Table # Dynamic import for rich
            table = Table(title="DeepSecure Agents", show_lines=True)
            table.add_column("Agent ID", style="cyan", no_wrap=True, overflow="fold")
            table.add_column("Name", style="magenta", overflow="fold")
            table.add_column("Status", style="green")
            table.add_column("Source", style="blue")
            table.add_column("PK Fingerprint", style="yellow", overflow="fold")
            table.add_column("Created At", style="dim", overflow="fold")

            for agent in final_agents_list:
                table.add_row(
                    agent.get("agent_id", "N/A"),
                    agent.get("name", "N/A"),
                    agent.get("status", "N/A"),
                    agent.get("source", "N/A"),
                    agent.get("public_key_fingerprint", "N/A"),
                    str(agent.get("created_at", "N/A")) # Ensure it's a string for table
                )
            utils.console.print(table)
        else: # Default to text output
            for agent in final_agents_list:
                utils.console.print(f"Agent ID: {agent.get('agent_id', 'N/A')}")
                utils.console.print(f"  Name: {agent.get('name', 'N/A')}")
                utils.console.print(f"  Status: {agent.get('status', 'N/A')}")
                utils.console.print(f"  Source: {agent.get('source', 'N/A')}")
                utils.console.print(f"  PK Fingerprint: {agent.get('public_key_fingerprint', 'N/A')}")
                utils.console.print(f"  Created At: {str(agent.get('created_at', 'N/A'))}")
                utils.console.print("---")

    except IdentityManagerError as e:
        utils.print_error(f"Local identity management error: {e}")
        raise typer.Exit(code=1)
    except ApiError as e:
        utils.print_error(f"Backend API error while listing agents: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        # Print the type of exception and its arguments for better debugging
        utils.print_error(f"An unexpected error occurred in list_agents: {type(e).__name__} - {str(e)}")
        # import traceback # For more detailed trace if needed
        # traceback.print_exc()
        raise typer.Exit(code=1)

# --- Describe Command ---
@app.command("describe")
def describe(
    agent_id: str = AgentID,
    output: str = typer.Option("text", "--output", "-o", help="Output format (`text` or `json`). Case-insensitive.", case_sensitive=False)
):
    """Get detailed information about a specific agent from backend and/or local store."""
    try:
        utils.console.print(f"Attempting to fetch details for agent ID: {agent_id}")
        
        # Attempt to fetch from backend first
        backend_details: Optional[Dict[str, Any]] = None
        try:
            backend_details = agent_service_client.describe_agent(agent_id=agent_id)
            if backend_details:
                 utils.console.print(f"Successfully fetched details for agent {agent_id} from backend.")
            else:
                utils.console.print(f"Agent {agent_id} not found on backend service. Checking locally...")
        except ApiError as e:
            utils.console.print(f"[yellow]API error fetching agent {agent_id} from backend: {e}. Checking locally...[/yellow]")
        except Exception as e: # Catch other potential client errors
            utils.console.print(f"[yellow]Unexpected error fetching agent {agent_id} from backend: {e}. Checking locally...[/yellow]")

        # Attempt to fetch from local identity store
        local_details: Optional[Dict[str, Any]] = None
        try:
            local_details = identity_manager.load_identity(agent_id=agent_id)
            if local_details:
                utils.console.print(f"Found local identity information for agent ID: {agent_id}")
        except IdentityManagerError as e:
             utils.console.print(f"[yellow]Error loading local identity for agent {agent_id}: {e}[/yellow]")

        if not backend_details and not local_details:
            utils.print_error(f"Agent with ID '{agent_id}' not found either remotely or locally.")
            raise typer.Exit(code=1)

        # Combine details: backend takes precedence, augment with local specifics
        combined_details = {}
        if backend_details:
            combined_details.update(backend_details)
        
        if local_details:
            # Add fields from local_details that are not in combined_details or are specific to local store
            for key, value in local_details.items():
                if key not in combined_details or key in ["private_key"]: # Always show if private key exists locally
                    combined_details[key] = value
            # Ensure some core fields from local are present if backend didn't provide them
            if "id" not in combined_details and "id" in local_details:
                 combined_details["id"] = local_details["id"]
            if "name" not in combined_details and "name" in local_details:
                 combined_details["name"] = local_details["name"]
            if "public_key" not in combined_details and "public_key" in local_details:
                 combined_details["public_key"] = local_details["public_key"]
                 # Regenerate fingerprint if we just got the public key from local
                 if "public_key_fingerprint" not in combined_details and combined_details["public_key"]:
                     try:
                        combined_details["public_key_fingerprint"] = identity_manager.get_public_key_fingerprint(combined_details["public_key"])
                     except IdentityManagerError as fp_error:
                        combined_details["public_key_fingerprint"] = f"Error generating: {fp_error}"

            # Add path to local identity file if it exists
            local_file_path = identity_manager.identity_store_path / f"{agent_id}.json"
            if local_file_path.exists():
                combined_details["local_identity_file"] = str(local_file_path)
                combined_details["local_private_key_present"] = "private_key" in local_details # More explicit
            else:
                # If backend_details existed but local didn't, ensure no stale local info
                combined_details.pop("local_identity_file", None)
                combined_details.pop("local_private_key_present", None)
                combined_details.pop("private_key", None) # Remove private key if no local file
        
        # Ensure agent_id is present in the final output, prefer backend's if available
        if "agent_id" not in combined_details and "id" in combined_details: # common key from local is 'id'
            combined_details["agent_id"] = combined_details["id"]
        elif "id" not in combined_details and "agent_id" in combined_details:
            combined_details["id"] = combined_details["agent_id"]

        # Remove raw private key from general display for security, unless specifically asked for in future.
        # The 'local_private_key_present' flag indicates its existence.
        displayed_details = combined_details.copy()
        if "private_key" in displayed_details:
            displayed_details["private_key"] = "[present_locally_not_shown]"

        if output.lower() == "json":
            # For JSON, we might want to show the full combined_details (including actual private_key if loaded)
            # For now, sticking to displayed_details for consistency with text output regarding private key.
            utils.print_json(displayed_details) 
        else: # Text output
            utils.console.print(f"\nDetails for Agent ID: [bold cyan]{displayed_details.get('agent_id', agent_id)}[/bold cyan]")
            utils.console.print("-----------------------------------")
            for key, value in displayed_details.items():
                if key == "private_key" and value == "[present_locally_not_shown]":
                     utils.console.print(f"  [bold dim]{key.replace('_', ' ').capitalize()}:[/bold dim] [yellow]{value}[/yellow]")
                elif value is not None:
                    utils.console.print(f"  [bold dim]{key.replace('_', ' ').capitalize()}:[/bold dim] {value}")
            utils.console.print("-----------------------------------")

    except IdentityManagerError as e:
        utils.print_error(f"Local identity management error for agent {agent_id}: {e}")
        raise typer.Exit(code=1)
    # ApiError already handled inside if block for backend_details or can be re-raised by client
    except Exception as e:
        utils.print_error(f"An unexpected error occurred while describing agent {agent_id}: {e}")
        raise typer.Exit(code=1)

# --- Delete Command ---
@app.command("delete")
def delete(
    agent_id: str = AgentID,
    revoke_credentials: bool = typer.Option(True, "--revoke-credentials/--no-revoke-credentials", help="(Future use) Revoke all active credentials for this agent on deletion."),
    purge_local_keys: bool = typer.Option(False, "--purge-local-keys", help="Delete local private keys associated with this agent. Requires confirmation."),
    force: bool = typer.Option(False, "--force", "-f", help="Suppress confirmation prompts for destructive actions.")
):
    """Deactivate an agent in the backend (soft delete) and/or purge local keys."""
    backend_deactivated_successfully = False
    local_keys_purged_successfully = False
    local_keys_existed = False

    local_identity_file = identity_manager.identity_store_path / f"{agent_id}.json"
    if local_identity_file.exists():
        local_keys_existed = True

    # Unified confirmation prompt
    if not force:
        action_items = []
        action_items.append("deactivate the agent on the backend (soft delete)")
        
        if purge_local_keys and local_keys_existed:
            action_items.append("PERMANENTLY delete local private key and metadata file")
        elif purge_local_keys and not local_keys_existed:
            action_items.append("attempt to purge local keys/metadata (none found)")
        elif not purge_local_keys and local_keys_existed:
            action_items.append("leave local keys/metadata intact")
        # If not purging and no local keys, no need to state anything extra about local keys

        action_description = " AND ".join(action_items)
        
        utils.console.print(f"[yellow]Warning: You are about to {action_description} for agent ID: {agent_id}.[/yellow]")
        if not typer.confirm("Are you sure you want to proceed? This action might be irreversible for local data.", abort=True):
            # This path should not be reached due to abort=True
            return # Defensive exit
        else:
            utils.console.print("Proceeding as confirmed by user.")
    
    try:
        utils.console.print(f"Attempting to deactivate agent (soft delete) {agent_id} via backend service...")
        try:
            deactivated_agent_data = agent_service_client.delete_agent(agent_id=agent_id)
            # If delete_agent succeeds, it returns the (now inactive) agent dict
            if deactivated_agent_data and deactivated_agent_data.get("status") == "inactive":
                backend_deactivated_successfully = True
                utils.print_success(f"Agent {agent_id} successfully deactivated. New status: inactive")
            else:
                # This else might be hit if client returns something unexpected but not an ApiError
                utils.print_error(f"Backend reported deactivation but response was unexpected for {agent_id}. Data: {deactivated_agent_data}", exit_code=None)

        except ApiError as e:
            if e.status_code == 404:
                utils.print_warning(f"Agent {agent_id} not found on backend. Cannot deactivate.")
            else:
                utils.print_error(f"API error during agent deactivation for {agent_id}: {e}", exit_code=None)
        except Exception as e:
            utils.print_error(f"Unexpected error during agent deactivation for {agent_id}: {e}", exit_code=None)

        if purge_local_keys and local_keys_existed: # Only attempt if requested and they existed
            utils.console.print(f"Attempting to purge local keys for agent ID: {agent_id}...")
            try:
                if identity_manager.delete_identity(agent_id=agent_id):
                    local_keys_purged_successfully = True
                    utils.print_success(f"Local keys for agent ID {agent_id} purged successfully.")
                # else: # identity_manager.delete_identity raises error on failure now
                    # utils.print_error(f"Failed to purge local keys for agent ID {agent_id}. `identity_manager.delete_identity` returned False.", exit_code=None)
            except IdentityManagerError as e:
                utils.print_error(f"Error purging local keys for agent {agent_id}: {e}", exit_code=None)
        
        # Final status reporting
        if backend_deactivated_successfully:
            if purge_local_keys and local_keys_existed and not local_keys_purged_successfully:
                utils.print_warning(f"Agent {agent_id} deactivated on backend, but failed to purge associated local keys.")
            # Other success cases are covered by individual success messages.
        elif purge_local_keys and local_keys_purged_successfully: # Backend failed, but local purge was successful
            utils.print_warning(f"Local keys for agent {agent_id} purged, but backend deactivation failed or agent was not found.")
        elif not backend_deactivated_successfully and not (purge_local_keys and local_keys_existed and local_keys_purged_successfully):
            # This condition means backend failed AND (either purge wasn't requested OR local keys didn't exist OR purge failed)
            # It's a bit complex, simplify: if backend failed and local wasn't successfully purged (if attempted for existing keys)
            if not (purge_local_keys and not local_keys_existed): # Avoid error if no local keys and purge wasn't really an option
                 utils.print_error(f"Agent {agent_id} deactivation failed. Please check messages above.", exit_code=1)

    except typer.Abort:
        utils.console.print("[yellow]Operation aborted by user.[/yellow]")
        # No explicit exit here; typer.Abort should handle it.
    except Exception as e:
        utils.print_error(f"An unexpected error occurred during the delete operation for {agent_id}: {e}", exit_code=True)
        # Re-raise typer.Exit if needed, or let it be based on print_error default. 