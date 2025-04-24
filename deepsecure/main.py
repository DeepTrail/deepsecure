'''Main CLI application entry point.'''
import typer
import importlib.metadata

from .commands import (
    vault,
    audit,
    risk,
    policy,
    sandbox,
    scan,
    harden,
    deploy,
    scorecard,
    inventory,
    ide
)

app = typer.Typer(
    name="deepsecure",
    help="DeepSecure CLI: Secure AI Development Control Plane."
)

# Register command modules
app.add_typer(vault.app, name="vault")
app.add_typer(audit.app, name="audit")
app.add_typer(risk.app, name="risk")
app.add_typer(policy.app, name="policy")
app.add_typer(sandbox.app, name="sandbox")
app.add_typer(scan.app, name="scan")
app.add_typer(harden.app, name="harden")
app.add_typer(deploy.app, name="deploy")
app.add_typer(scorecard.app, name="scorecard")
app.add_typer(inventory.app, name="inventory")
app.add_typer(ide.app, name="ide")

@app.command("version")
def version():
    """Show CLI version."""
    try:
        version = importlib.metadata.version("deepsecure-cli")
        print(f"DeepSecure CLI version: {version}")
    except importlib.metadata.PackageNotFoundError:
        print("DeepSecure CLI version: 0.0.2 (development)")

@app.command("login")
def login(
    endpoint: str = typer.Option(None, help="API endpoint to authenticate with"),
    interactive: bool = typer.Option(True, help="Use interactive login flow")
):
    """Authenticate with DeepSecure backend."""
    from . import auth, utils
    
    if endpoint:
        utils.console.print(f"Authenticating with endpoint: [bold]{endpoint}[/]")
    else:
        utils.console.print("Authenticating with default endpoint")
    
    # Placeholder for actual login logic
    if interactive:
        utils.console.print("Please enter your credentials:")
        # In a real implementation, would prompt for username/password
        # or open a browser for OAuth flow
        token = "dummy-token-abc123"
    else:
        # In a non-interactive flow, might use environment variables
        token = "dummy-token-xyz789"
    
    # Store the token
    auth.store_token(token)
    utils.print_success("Successfully authenticated")

if __name__ == "__main__":
    app() 