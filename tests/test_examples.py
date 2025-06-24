# tests/test_examples.py
import pytest
import subprocess
import sys
import os
from pathlib import Path

# Get the root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent

# List of example scripts to be tested
# We can add to this list as more examples are created.
EXAMPLE_SCRIPTS = [
    "examples/01_create_agent_and_issue_credential.py",
    "examples/02_sdk_secret_fetch.py",
    "examples.03_crewai_secure_tools.py", # This will be skipped if dependencies are not met
    "examples/04_multi_agent_communication.py",
    "examples/05_langchain_secure_tools.py",
]

# Helper to check if an example script exists
def script_path(script_name):
    path = PROJECT_ROOT / script_name
    return path if path.exists() else None

@pytest.fixture(scope="module")
def e2e_environment_is_ready():
    """
    A fixture to check if the necessary environment for E2E tests is set up.
    Skips all tests in this module if the environment is not ready.
    """
    if not os.environ.get("DEEPSECURE_CREDSERVICE_URL"):
        pytest.skip("E2E tests require DEEPSECURE_CREDSERVICE_URL to be set.")
    if not os.environ.get("DEEPSECURE_CREDSERVICE_API_TOKEN"):
        pytest.skip("E2E tests require DEEPSECURE_CREDSERVICE_API_TOKEN to be set.")
    # Here, you could add logic to pre-seed the vault with secrets
    # For now, we assume the user has run the necessary `deepsecure vault store` commands.

@pytest.mark.e2e
@pytest.mark.parametrize("script_name", EXAMPLE_SCRIPTS)
def test_example_script(script_name, e2e_environment_is_ready):
    """
    A parameterized test that executes each example script and checks for success.
    
    This test uses the `subprocess` module to run each example script as a separate process,
    simulating how a user would execute it. It checks that the script finishes
    with an exit code of 0.
    """
    path = script_path(script_name)
    if not path:
        pytest.skip(f"Example script not found: {script_name}")

    try:
        # We use sys.executable to ensure we're using the same Python interpreter
        # that's running pytest.
        result = subprocess.run(
            [sys.executable, str(path)],
            check=True,          # Raises CalledProcessError if the script fails (non-zero exit code)
            capture_output=True, # Captures stdout and stderr
            text=True,           # Decodes stdout/stderr as text
            timeout=60           # Add a timeout to prevent hanging tests
        )
        
        print(f"--- Output from {script_name} ---")
        print(result.stdout)
        if result.stderr:
            print("--- Stderr ---")
            print(result.stderr)

        # A basic success check is that the process completed without error.
        # More specific checks could be added here if needed, e.g.,
        # assert "Successfully" in result.stdout
        
    except FileNotFoundError:
        pytest.fail(f"Could not find the Python interpreter: {sys.executable}")
    except subprocess.CalledProcessError as e:
        # If the script returns a non-zero exit code, this exception is raised.
        # We fail the test and print the output for debugging.
        pytest.fail(
            f"Example script '{script_name}' failed with exit code {e.returncode}.\n"
            f"--- STDOUT ---\n{e.stdout}\n"
            f"--- STDERR ---\n{e.stderr}"
        )
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            f"Example script '{script_name}' timed out after {e.timeout} seconds.\n"
            f"--- STDOUT ---\n{e.stdout}\n"
            f"--- STDERR --- \n{e.stderr}"
        ) 