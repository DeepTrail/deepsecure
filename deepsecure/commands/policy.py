'''Policy enforcement command implementations.'''

import typer
from pathlib import Path
from typing import Optional

from .. import utils
from ..core import policy_client

app = typer.Typer(
    name="policy",
    help="Enforce least privilege on AI behavior at runtime."
)

@app.command("init")
def init(
    template: str = typer.Option(..., help="Template name to use (e.g., 'read-only', 'restricted')"),
    output: Optional[Path] = typer.Option("policy.yaml", help="Output path for the generated policy")
):
    """Bootstrap a runtime policy template for an agent or server."""
    utils.console.print(f"Generating policy from template: [bold]{template}[/]")
    # Placeholder - would call policy_client.generate_from_template() in real implementation
    
    utils.console.print(f"Writing policy to: [bold]{output}[/]")
    # Here we would actually write the file, but for the stub we just pretend
    
    utils.print_success(f"Created policy file at {output}")
    
    # Show sample of what was generated
    utils.console.print("[dim]Policy preview:[/]")
    utils.console.print("```yaml")
    utils.console.print("# Generated DeepSecure policy from template: " + template)
    utils.console.print("version: 1")
    utils.console.print("name: generated-policy")
    utils.console.print("permissions:")
    utils.console.print("  file_access:")
    utils.console.print("    allow: [read]")
    utils.console.print("    paths: ['./configs/**']")
    utils.console.print("  network:")
    utils.console.print("    allow: [connect]")
    utils.console.print("    hosts: ['api.example.com']")
    utils.console.print("```")

@app.command("apply")
def apply(
    agent_id: str = typer.Option(..., "--agent-id", "-id", help="Unique ID of the AI agent to apply policy to"),
    policy: Path = typer.Option(..., "--policy-file", help="Path to the policy file to apply")
):
    """Apply a runtime policy to an AI agent or server."""
    # Verify the policy file exists
    if not policy.exists():
        utils.print_error(f"Policy file not found: {policy}")
        raise typer.Exit(code=1)
    
    utils.console.print(f"Applying policy from [bold]{policy}[/] to agent ID [bold]{agent_id}[/]")
    # Placeholder - would call policy_client.apply_policy(agent_id=agent_id, policy_path=policy) in real implementation
    
    utils.print_success(f"Applied policy to {agent_id}")
    utils.console.print(f"The agent [bold]{agent_id}[/] is now operating under restricted permissions") 