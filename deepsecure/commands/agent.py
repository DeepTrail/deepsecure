# deepsecure/commands/agent.py
import typer
from typing import Optional
import logging
from typer.core import TyperGroup

from .. import utils
import deepsecure

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
    output: str = typer.Option("text", "--output", "-o", help="Output format (`text` or `json`).", case_sensitive=False)
):
    """
    Creates a new agent identity locally and registers it with the backend.
    """
    try:
        utils.console.print(f"Creating new agent named '{name}'...")
        
        client = deepsecure.Client()
        # The agent method with auto_create=True handles the entire workflow.
        agent = client.agent(name, auto_create=True)

        if output.lower() == "json":
            # We need to fetch the full agent details for a complete JSON output
            # The agent handle itself is minimal.
            agent_details = client._agent_client.describe_agent(agent.id)
            utils.print_json(agent_details)
        else:
            utils.print_success(f"Agent '{agent.name}' created successfully.")
            utils.console.print(f"  Agent ID: [bold]{agent.id}[/bold]")
            utils.console.print(f"  Name: {agent.name}")
            utils.console.print("[green]Identity created and private key stored securely in system keyring.[/green]")

    except deepsecure.DeepSecureError as e:
        utils.print_error(f"Failed to create agent: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred: {e}")
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
        agents = client.list_agents()

        if not agents:
            utils.console.print("No agents found.")
            raise typer.Exit()

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
        agent = client.describe_agent(agent_id=agent_id)

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
            utils.console.print(f"  Public Key: {agent.get('public_key')}")
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
        
        client.delete_agent(agent_id=agent_id)
        
        utils.print_success(f"Agent {agent_id} has been deleted successfully.")

    except deepsecure.DeepSecureError as e:
        utils.print_error(f"Failed to delete agent: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        utils.print_error(f"An unexpected error occurred during deletion: {e}")
        raise typer.Exit(code=1) 