# tests/test_examples.py
import pytest
import subprocess
import sys
import os
from pathlib import Path

# Get the root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent

# List of example scripts to be tested
# All 12 examples from the examples/ directory
EXAMPLE_SCRIPTS = [
    "examples/01_create_agent_and_issue_credential.py",
    "examples/02_sdk_secret_fetch.py",
    "examples/03_crewai_secure_tools.py",
    "examples/04_crewai_secure_tools_without_finegrain_control.py",
    "examples/05_langchain_secure_tools.py",
    "examples/06_langchain_secure_tools_without_finegrain_control.py",
    "examples/07_multi_agent_communication.py",
    "examples/08_gateway_secret_injection_demo.py",
    "examples/09_langchain_delegation_workflow.py",
    "examples/10_crewai_delegation_workflow.py",
    "examples/11_advanced_delegation_patterns.py",
    "examples/12_platform_expansion_bootstrap.py",
]

# Helper to check if an example script exists
def script_path(script_name):
    path = PROJECT_ROOT / script_name
    return path if path.exists() else None

@pytest.fixture(scope="module")
def e2e_environment_is_ready():
    """
    A fixture to set up the necessary environment for E2E tests.
    Automatically configures the environment variables for testing.
    """
    # Set default test environment variables if not already set
    if not os.environ.get("DEEPSECURE_DEEPTRAIL_CONTROL_URL"):
        os.environ["DEEPSECURE_DEEPTRAIL_CONTROL_URL"] = "http://127.0.0.1:8000"
    
    if not os.environ.get("DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN"):
        os.environ["DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN"] = "DEFAULT_QUICKSTART_TOKEN"
    
    # Check if the backend service is running
    import requests
    try:
        response = requests.get(f"{os.environ['DEEPSECURE_DEEPTRAIL_CONTROL_URL']}/health", timeout=5)
        if response.status_code != 200:
            pytest.skip(f"Backend service not healthy at {os.environ['DEEPSECURE_DEEPTRAIL_CONTROL_URL']}/health")
    except requests.exceptions.RequestException:
        pytest.skip(f"Backend service not reachable at {os.environ['DEEPSECURE_DEEPTRAIL_CONTROL_URL']}. Please start the deeptrail-control backend.")
    
    # Set up test secrets that the examples need
    _setup_test_secrets()
    
    # Environment is ready for testing
    return True

def _setup_test_secrets():
    """Set up the test secrets that examples require."""
    import subprocess
    import sys
    
    # List of secrets that examples need
    test_secrets = [
        ("example-api-key", "demo-api-key-12345"),
        ("openai-api-key", "sk-demo-openai-key"),
        ("notion-api-key", "secret_demo-notion-key"),
        ("tavily-api-key", "tvly-demo-tavily-key"),
    ]
    
    for secret_name, secret_value in test_secrets:
        try:
            # Use the deepsecure CLI to store the secret
            result = subprocess.run(
                [sys.executable, "-m", "deepsecure", "vault", "store", secret_name, "--value", secret_value],
                capture_output=True,
                text=True,
                timeout=10
            )
            # We don't fail if secret already exists or if there are minor issues
            # The examples will handle missing secrets gracefully
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # Continue even if secret setup fails - examples should handle this gracefully
            pass

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
            timeout=60,          # Add a timeout to prevent hanging tests
            env=os.environ.copy()  # Pass the current environment variables to the subprocess
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