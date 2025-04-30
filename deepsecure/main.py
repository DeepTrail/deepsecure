'''Main CLI application entry point.'''
import typer
import importlib.metadata

from .commands import (
    vault
    # invoke removed
)

# Import other commands as they're implemented
# from .commands import (
#    audit,
#    risk,
#    policy,
#    sandbox,
#    scan,
#    harden,
#    deploy,
#    scorecard,
#    inventory,
#    ide
# )

app = typer.Typer(
    name="deepsecure",
    help="DeepSecure CLI: Secure AI Development Control Plane."
)

# Register command modules
app.add_typer(vault.app, name="vault")
# app.add_typer(invoke.app, name="invoke") # Removed invoke command group

# Register other commands as they're implemented
# app.add_typer(audit.app, name="audit")
# app.add_typer(risk.app, name="risk")
# app.add_typer(policy.app, name="policy")
# app.add_typer(sandbox.app, name="sandbox")
# app.add_typer(scan.app, name="scan")
# app.add_typer(harden.app, name="harden")
# app.add_typer(deploy.app, name="deploy")
# app.add_typer(scorecard.app, name="scorecard")
# app.add_typer(inventory.app, name="inventory")
# app.add_typer(ide.app, name="ide")

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
        # Ensure authenticated (will use placeholder flow if needed)
        auth.ensure_authenticated()
    else:
        # Non-interactive might rely on env vars or existing token
        token = auth.get_token()
        if not token:
            utils.print_error("Authentication required. Use interactive login or set DEEPSECURE_API_TOKEN.")
            # Exit handled by print_error
        else:
             utils.print_success("Using existing authentication.")

if __name__ == "__main__":
    app() 