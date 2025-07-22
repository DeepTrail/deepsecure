# deepsecure/commands/agent.py
import typer
from typing import Optional, List
import logging
from typer.core import TyperGroup
from pathlib import Path

from .. import utils
from ..utils import get_client
import deepsecure
from .._core.agent_client import AgentClient
from .._core.identity_manager import IdentityManager
from ..resources.agent import Agent
from deepsecure.exceptions import ApiError, DeepSecureError, DeepSecureClientError

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="agent",
    help="Manage DeepSecure agent identities and lifecycle.",
    rich_markup_mode="markdown"
)

# Placeholder for agent_id argument type
AgentID = typer.Argument(..., help="The unique identifier of the agent.")

# --- Create Command (replaces Register) ---
@app.command("create")
def create_agent(
    name: str = typer.Option(..., "--name", "-n", help="A human-readable name for the agent."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="A description for the agent."), # Description is not used by SDK agent creation yet, but kept for future use
    output: str = typer.Option("text", "--output", "-o", help="Output format (text, json)"),
):
    """
    Creates a new agent, generating a new cryptographic keypair and storing it in the local keyring.
    """
    is_json_output = output.lower() == "json"

    if not is_json_output:
        utils.console.print(f"Creating new agent named [green]'{name}'[/green][yellow]...[/yellow]")

    try:
        # Get a properly configured client instance.
        client = deepsecure.Client(silent_mode=is_json_output)

        # The public API for creating an agent handles key generation and storage.
        # This returns a resource object which is easier to work with.
        agent = client.agents.create(name=name, description=description)

        if is_json_output:
            # The agent object has enough info for json output
            agent_dict = agent.to_dict()
            # We need to retrieve the private key from the identity manager to return it
            private_key = client._identity_manager.get_private_key(agent.id)
            agent_dict["private_key"] = private_key
            utils.print_json(agent_dict)
        else:
            utils.print_success(f"Agent '{agent.name}' created successfully.")
            utils.console.print(f"  [bold]Agent ID:[/bold] {agent.id}")
            # Do not print the private key in normal output
            utils.console.print(f"  [bold]Public Key:[/bold] {agent.public_key}")
            utils.console.print("[yellow]The agent's private key has been stored securely in your OS keyring.[/yellow]")

    except Exception as e:
        utils.print_error(f"Failed to create agent: {e}")
        raise typer.Exit(code=1)

# --- List Command ---
@app.command("list")
def list_agents(
    output: str = typer.Option("table", "--output", "-o", help="Output format (`table`, `json`, `text`).", case_sensitive=False)
):
    """Lists all agents registered with the DeepSecure backend."""
    try:
        client = deepsecure.Client()
        
        utils.console.print("Fetching agents from the backend...")
        # client.agents is an AgentClient instance that has list_agents() method
        agent_response = client.agents.list_agents()
        # Extract the agents list from the response dictionary
        agents = agent_response.get("agents", [])

        if not agents:
            utils.console.print("No agents found.")
            return

        if output.lower() == "json":
            utils.print_json(agents)
        elif output.lower() == "table":
            from rich.table import Table
            table = Table(title="DeepSecure Agents", show_lines=True)
            table.add_column("Agent ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Created At", style="dim", overflow="fold")
            
            for agent in agents:
                table.add_row(
                    agent.get("agent_id"),
                    agent.get("name"),
                    agent.get("status"),
                    agent.get("created_at")
                )
            utils.console.print(table)
        else: # text output
            for agent in agents:
                utils.console.print(f"Agent ID: [bold]{agent.get('agent_id')}[/bold]")
                utils.console.print(f"  Name: {agent.get('name')}")
                utils.console.print(f"  Status: {agent.get('status')}")
                utils.console.print(f"  Created At: {agent.get('created_at')}")
                utils.console.print("-" * 20)

    except deepsecure.DeepSecureError as e:
        utils.print_error(f"Failed to list agents: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)

# --- Describe Command ---
@app.command("describe")
def describe_agent(
    agent_id: str = AgentID,
    output: str = typer.Option("text", "--output", "-o", help="Output format (`text` or `json`).", case_sensitive=False)
):
    """Describes a specific agent by its ID."""
    try:
        client = deepsecure.Client()
        utils.console.print(f"Fetching details for agent [bold]{agent_id}[/bold]...")
        agent = client.agents.describe_agent(agent_id=agent_id)

        if not agent:
            utils.print_error(f"Agent with ID '{agent_id}' not found.")
            raise typer.Exit(1)

        if output.lower() == "json":
            utils.print_json(agent)
        else:
            utils.console.print(f"Agent ID: [bold]{agent.get('agent_id')}[/bold]")
            utils.console.print(f"  Name: {agent.get('name')}")
            if agent.get('description'):
                utils.console.print(f"  Description: {agent.get('description')}")
            utils.console.print(f"  Status: {agent.get('status')}")
            utils.console.print(f"  Public Key: {agent.get('public_key') or agent.get('publicKey', 'N/A')}")
            utils.console.print(f"  Created At: {agent.get('created_at')}")

    except deepsecure.DeepSecureError as e:
        utils.print_error(f"Failed to describe agent: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)

# --- Delete Command ---
@app.command("delete")
def delete_agent(
    agent_id: str = AgentID,
    force: bool = typer.Option(False, "--force", "-f", help="Suppress confirmation prompts.")
):
    """
    Deactivates an agent from the backend and purges its local identity.
    """
    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete agent {agent_id}? "
            "This will deactivate the agent on the backend and permanently delete its local keys."
        )
        if not confirm:
            utils.console.print("Deletion cancelled.")
            raise typer.Exit()

    try:
        client = deepsecure.Client()
        utils.console.print(f"Deleting agent [bold]{agent_id}[/bold]...")
        
        client.agents.delete_agent(agent_id=agent_id)
        
        utils.print_success(f"Agent {agent_id} has been deleted successfully.")

    except deepsecure.DeepSecureError as e:
        utils.print_error(f"Failed to delete agent: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred during deletion: {e}")
        raise typer.Exit(code=1)

# --- Cleanup Command ---
@app.command("cleanup")
def cleanup_agents():
    """Show agent status and provide guidance for keychain cleanup.
    
    This command displays all backend agents and their corresponding private keys,
    then provides manual guidance for cleaning up orphaned keychain entries.
    
    Note: Due to macOS security restrictions, automated keychain cleanup is not
    possible. Manual cleanup through Keychain Access is required.
    """
    try:
        client = get_client()
        
        # Get all agents from backend
        agents = client.agents.list_agents()
        
        if not agents:
            utils.console.print("No agents found in backend.")
            return
        
        # We can get the identity_manager from the client
        identity_mgr = client._identity_manager
        
        # Build agent status table
        table_data = []
        agents_with_keys = 0
        
        for agent in agents:
            agent_id = agent.get('agent_id', agent.get('id', 'unknown'))
            agent_name = agent.get('name', 'Unknown')
            
            # Extract prefix from agent_id (e.g., agent-558ad262-... => 558ad262)
            if agent_id.startswith('agent-') and len(agent_id) > 6:
                prefix = agent_id.split('-')[1][:8]  # First 8 chars after 'agent-'
            else:
                prefix = 'unknown'
            
            # Check if private key exists in keychain
            try:
                private_key = identity_mgr.get_identity(agent_id) # Use get_identity which is the public method
                if private_key:
                    key_status = "✓ Present"
                    agents_with_keys += 1
                else:
                    key_status = "✗ Missing"
            except Exception:
                key_status = "✗ Missing"
            
            table_data.append([
                agent_id,
                agent_name,
                prefix, 
                key_status
            ])
        
        # Display summary
        utils.console.print(f"\n📊 Agent Status Summary")
        utils.console.print(f"Backend agents: {len(agents)}")
        utils.console.print(f"Agents with private keys: {agents_with_keys}")
        utils.console.print(f"Agents missing private keys: {len(agents) - agents_with_keys}")
        
        # Display table
        utils.console.print(f"\n📋 Agent-to-Key Relationship")
        utils.console.print("=" * 100)
        utils.console.print(f"{'Agent ID':<36} {'Agent Name':<20} {'Prefix':<12} {'Private Key Status'}")
        utils.console.print("-" * 100)
        
        for row in table_data:
            # Truncate agent name if too long
            agent_name = row[1][:19] + "…" if len(row[1]) > 20 else row[1]
            utils.console.print(f"{row[0]:<36} {agent_name:<20} {row[2]:<12} {row[3]}")
        
        # Provide manual cleanup guidance
        utils.console.print(f"\n🧹 Manual Keychain Cleanup")
        utils.console.print("=" * 50)
        utils.console.print("Due to macOS security restrictions, keychain cleanup must be done manually.")
        utils.console.print("")
        utils.console.print("To clean up orphaned keychain entries:")
        utils.console.print("1. Open 'Keychain Access' application")
        utils.console.print("2. Search for 'deepsecure_agent'")
        utils.console.print("3. Review the entries against the table above")
        utils.console.print("4. Delete any entries that don't match current backend agents")
        utils.console.print("")
        utils.console.print("Expected keychain entry format:")
        utils.console.print("  Account: deepsecure_agent-{prefix}_private_key")
        utils.console.print("  Where: deepsecure_agent-{prefix}_private_key")
        utils.console.print("")
        utils.console.print("💡 Tip: Keep entries that match the 'Prefix' column above")
        
    except Exception as e:
        utils.console.print(f"Error during cleanup: {e}", err=True)
        raise typer.Exit(code=1) 