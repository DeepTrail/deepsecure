
# deepsecure/commands/auth.py
import typer
from .. import utils
from ..auth import get_token

app = typer.Typer(
    name="auth",
    help="Manage CLI authentication state.",
    rich_markup_mode="markdown"
)

@app.command("status")
def auth_status(
    ctx: typer.Context,
):
    """
    Checks the current authentication status and validates the stored token.
    """
    token = get_token()
    if not token:
        utils.console.print("[yellow]You are not logged in.[/yellow]")
        utils.console.print("Run `deepsecure login` to authenticate.")
        return

    utils.console.print("Checking token status...")
    try:
        client = utils.get_authenticated_client(ctx)
        # A simple, authenticated API call is a good way to validate the token.
        # We can use the agent list endpoint as it's lightweight.
        client.list_agents()
        utils.print_success("Authentication token is valid.")
        # TODO: Add details like which user/agent is authenticated and when the token expires.
    except Exception as e:
        utils.print_error(f"Authentication token is invalid or expired: {e}")
        utils.console.print("Please run `deepsecure login` again.")