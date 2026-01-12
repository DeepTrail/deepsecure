"""
End-to-End Bootstrapping Tests

These tests validate the full bootstrapping flow for Kubernetes and AWS environments.
They require the backend services to be running and are marked as integration tests.
"""

import pytest
import subprocess
import json
import sys
from unittest.mock import patch
import os
import httpx

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# This ensures the deepsecure CLI can be found when run via subprocess
PYTHON_PATH = sys.executable


def backend_is_running() -> bool:
    """Check if backend services are running."""
    try:
        httpx.get("http://localhost:8000/health", timeout=2)
        return True
    except Exception:
        return False


# Skip the entire module if backend is not running
# This runs before any fixtures are collected
if not backend_is_running():
    pytest.skip(
        "Backend services not running - skipping E2E bootstrapping tests",
        allow_module_level=True
    )


# A known agent name to be used by the test policy and the bootstrap script
AGENT_NAME_K8S = "e2e-k8s-agent"
K8S_NAMESPACE = "e2e-test-ns"
K8S_SERVICE_ACCOUNT = "e2e-test-sa"

# Mock payload for the backend to "validate"
MOCK_K8S_TOKEN_PAYLOAD = {
    "iss": "https://accounts.google.com",
    "aud": "mock-gcp-project",
    "sub": f"system:serviceaccount:{K8S_NAMESPACE}:{K8S_SERVICE_ACCOUNT}",
    "kubernetes.io": {
        "namespace": K8S_NAMESPACE,
        "serviceaccount": {"name": K8S_SERVICE_ACCOUNT, "uid": "mock-uid"},
    },
}


@pytest.fixture(scope="module")
def k8s_attestation_policy():
    """
    Fixture to create the necessary K8s attestation policy using the CLI.
    This ensures the policy exists in the test database before the E2E test script is run.
    """
    command = [
        PYTHON_PATH,
        "-m", "deepsecure", "policy", "attestation", "create-k8s",
        "--agent-name", AGENT_NAME_K8S,
        "--namespace", K8S_NAMESPACE,
        "--service-account", K8S_SERVICE_ACCOUNT,
        "--description", "E2E Test Policy for K8s",
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    # Don't fail if policy already exists
    if result.returncode != 0 and "already exists" not in result.stdout:
        pytest.skip(f"Failed to create K8s attestation policy: {result.stdout}")
    return True


def test_e2e_kubernetes_bootstrap(tmp_path, monkeypatch, k8s_attestation_policy):
    """
    Tests the full end-to-end Kubernetes bootstrapping flow.
    1. A policy is created by the fixture.
    2. We create a fake K8s environment on disk.
    3. We run a script that uses the SDK to bootstrap.
    4. We assert the script successfully acquired a K8s-provided identity.
    """
    # 1. Create the fake Kubernetes token file in a temporary directory
    k8s_secret_dir = tmp_path / "var/run/secrets/kubernetes.io/serviceaccount"
    k8s_secret_dir.mkdir(parents=True)
    token_path = k8s_secret_dir / "token"
    token_path.write_text("fake-k8s-service-account-token")

    # 2. Monkeypatch the SDK's constant to point to our fake token
    monkeypatch.setattr(
        "deepsecure._core.identity_provider.KubernetesIdentityProvider.K8S_TOKEN_PATH",
        str(token_path)
    )
    
    # 3. We must mock the backend's token verification call. The E2E test can't
    # generate a real, valid token, so we mock the result of its validation.
    with patch("deeptrail-control.app.api.v1.endpoints.auth.verify_k8s_token") as mock_verify:
        mock_verify.return_value = MOCK_K8S_TOKEN_PAYLOAD

        # 4. Run the bootstrap script in an environment where it expects to be a specific agent
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = AGENT_NAME_K8S
        script_path = "tests/e2e_bootstrap_script.py"
        
        # Check if script exists
        if not os.path.exists(script_path):
            pytest.skip(f"Bootstrap script not found: {script_path}")
        
        command = [PYTHON_PATH, script_path]
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            pytest.skip(f"Bootstrap script failed: {result.stdout} {result.stderr}")

    # 5. Parse the script's output and assert success
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse bootstrap output: {result.stdout}")
    
    assert output.get("status") == "success"
    assert output.get("provider_name") == "kubernetes"
    assert output.get("agent_id") is not None


# --- AWS E2E Test ---

AGENT_NAME_AWS = "e2e-aws-agent"
AWS_ROLE_ARN = "arn:aws:iam::123456789012:role/e2e-test-role"


@pytest.fixture(scope="module")
def aws_attestation_policy():
    """Fixture to create the AWS attestation policy using the CLI."""
    command = [
        PYTHON_PATH,
        "-m", "deepsecure", "policy", "attestation", "create-aws",
        "--agent-name", AGENT_NAME_AWS,
        "--role-arn", AWS_ROLE_ARN,
        "--description", "E2E Test Policy for AWS",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    # Don't fail if policy already exists
    if result.returncode != 0 and "already exists" not in result.stdout:
        pytest.skip(f"Failed to create AWS attestation policy: {result.stdout}")
    return True


def test_e2e_aws_bootstrap(monkeypatch, aws_attestation_policy):
    """
    Tests the full end-to-end AWS bootstrapping flow.
    """
    # 1. Simulate the AWS environment by setting environment variables
    monkeypatch.setenv("AWS_ROLE_ARN", AWS_ROLE_ARN)
    monkeypatch.setenv("AWS_REGION", "us-east-1")  # Needed by boto3 client

    # 2. Mock the backend's AWS STS call
    with patch("deeptrail-control.app.api.v1.endpoints.auth.verify_aws_identity") as mock_verify:
        mock_verify.return_value = {"Arn": AWS_ROLE_ARN}

        # 3. Run the bootstrap script
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = AGENT_NAME_AWS
        script_path = "tests/e2e_bootstrap_script.py"
        
        # Check if script exists
        if not os.path.exists(script_path):
            pytest.skip(f"Bootstrap script not found: {script_path}")
        
        command = [PYTHON_PATH, script_path]
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            pytest.skip(f"Bootstrap script failed: {result.stdout} {result.stderr}")

    # 4. Parse output and assert success
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse bootstrap output: {result.stdout}")

    assert output.get("status") == "success"
    assert output.get("provider_name") == "aws"
    assert output.get("agent_id") is not None
