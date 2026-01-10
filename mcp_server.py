from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sys
import contextlib
import datetime

# Import our desktop automation functions
from desktop_automation import list_granola_notes, read_granola_note

@contextlib.contextmanager
def log_to_file(filepath):
    """A context manager to redirect stdout and stderr to a file."""
    with open(filepath, 'a') as f:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = f
        sys.stderr = f
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

app = FastAPI(
    title="Granola Desktop MCP Server",
    description="An MCP server to control the Granola desktop application.",
    version="0.1.0",
)

TOOLS = {
    "list_notes": {
        "description": "Lists the titles of all notes currently visible in the Granola application.",
        "arguments": {},
        "handler": "list_granola_notes",
    },
    "read_note": {
        "description": "Reads the full content of a specific note, given its title.",
        "arguments": {
            "note_title": {
                "type": "string",
                "description": "The exact title of the note to read.",
                "required": True,
            }
        },
        "handler": "read_granola_note",
    },
}

@app.post("/")
async def mcp_endpoint(request: Request):
    """
    This endpoint will handle JSON-RPC 2.0 requests for the MCP tools.
    """
    body = await request.json()
    # Basic JSON-RPC 2.0 structure validation
    if not all(k in body for k in ["jsonrpc", "method", "id"]):
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": None,
            },
        )
    
    method = body.get("method")
    
    if method == "mcp_getTools":
        return {
            "jsonrpc": "2.0",
            "result": {"tools": list(TOOLS.keys())},
            "id": body.get("id"),
        }
    
    if method == "mcp_getTool":
        tool_name = body.get("params", {}).get("name")
        if tool_name in TOOLS:
            return {
                "jsonrpc": "2.0",
                "result": TOOLS[tool_name],
                "id": body.get("id"),
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": "Method not found"},
                    "id": body.get("id"),
                },
            )

    # If the requested method is a defined tool, execute it.
    if method in TOOLS:
        handler_name = TOOLS[method]["handler"]
        handler = globals().get(handler_name)
        params = body.get("params", {})

        with log_to_file("mcp_server.log"):
            print(f"--- Running tool: {method} at {datetime.datetime.now()} ---")
            try:
                # Execute the handler with the provided parameters
                if method == "read_note":
                    note_title = params.get("note_title")
                    if not note_title:
                         return JSONResponse(
                            status_code=400,
                            content={
                                "jsonrpc": "2.0",
                                "error": {"code": -32602, "message": "Invalid params: 'note_title' is required."},
                                "id": body.get("id"),
                            },
                        )
                    result = handler(note_title)
                else:
                    result = handler()

                print(f"--- Tool finished successfully ---")
                return {"jsonrpc": "2.0", "result": result, "id": body.get("id")}
            except Exception as e:
                print(f"--- Tool failed with exception: {e} ---")
                # Handle any exceptions during tool execution
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": f"Server error: {e}"},
                        "id": body.get("id"),
                    },
                )

    return JSONResponse(
        status_code=404,
        content={
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": body.get("id"),
        },
    )

@app.get("/health")
async def health_check():
    """
    A simple health check endpoint.
    """
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
