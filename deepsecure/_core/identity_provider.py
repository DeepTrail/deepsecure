# deepsecure/_core/identity_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

import keyring
from keyring.errors import NoKeyringError
import os

from .crypto.key_manager import key_manager
from .. import utils


@dataclass
class AgentIdentity:
    """A dataclass to hold the complete identity of an agent."""
    agent_id: str
    private_key_b64: str
    public_key_b64: str
    provider_name: str # The name of the provider that sourced this identity


def _get_keyring_service_name_for_agent(agent_id: str) -> str:
    """Helper to generate the dynamic service name for an agent's private key in the keyring."""
    if not agent_id.startswith("agent-"):
        raise ValueError(f"Agent ID '{agent_id}' does not follow the expected 'agent-<uuid>' format.")
    parts = agent_id.split('-')
    if len(parts) < 2:
        raise ValueError(f"Agent ID '{agent_id}' does not contain a UUID part after 'agent-'.")
    prefix = parts[1]
    return f"deepsecure_agent-{prefix}_private_key"


class IdentityProvider(ABC):
    """Abstract base class for all identity providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The user-friendly name of the provider (e.g., 'keyring', 'kubernetes')."""
        pass

    @abstractmethod
    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Attempt to retrieve the identity for a given agent_id.
        Returns an AgentIdentity object if successful, otherwise None.
        """
        pass


class KeyringIdentityProvider(IdentityProvider):
    """
    An identity provider that retrieves agent private keys from the local system keyring.
    """
    def __init__(self, silent_mode: bool = False):
        self.silent_mode = silent_mode

    @property
    def name(self) -> str:
        return "keyring"

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Retrieves the private key for an agent from the keychain and derives the public key.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            private_key_b64 = keyring.get_password(keyring_service_name, agent_id)
            if not private_key_b64:
                if not self.silent_mode:
                    # This is an expected "miss" in the chain, so keep it dim
                    utils.console.print(f"[{self.name}] No identity found for agent [yellow]{agent_id}[/yellow] in system keyring.", style="dim")
                return None

            # If we found a private key, derive the public key
            public_key_b64 = key_manager.derive_public_key(private_key_b64)

            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Successfully loaded identity for agent [cyan]{agent_id}[/cyan] from system keyring.", style="green")
            
            return AgentIdentity(
                agent_id=agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64,
                provider_name=self.name
            )
        except NoKeyringError:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] WARNING: No system keyring backend found for agent [yellow]{agent_id}[/yellow].", style="bold yellow")
            return None
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] WARNING: An unexpected error occurred while loading identity for agent [yellow]{agent_id}[/yellow]: {e}", style="bold yellow")
            return None


class KubernetesIdentityProvider(IdentityProvider):
    """
    An identity provider that bootstraps an agent's identity using a
    Kubernetes Service Account Token.
    Enhanced to work with the new backend implementation.
    """
    K8S_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    K8S_NAMESPACE_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

    def __init__(self, client: Any, silent_mode: bool = False):
        self.client = client # The API client to communicate with deeptrail-control
        self.silent_mode = silent_mode

    @property
    def name(self) -> str:
        return "kubernetes"

    def _is_in_kubernetes(self) -> bool:
        """Check if running inside a Kubernetes pod."""
        return os.path.exists(self.K8S_TOKEN_PATH)

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Performs attestation against the deeptrail-control backend using the K8s SAT.
        Enhanced with proper error handling and response validation.
        """
        if not self._is_in_kubernetes():
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Not running in a Kubernetes environment (token path not found). Skipping.", style="dim")
            return None

        if not self.silent_mode:
            utils.console.print(f"[{self.name}] Kubernetes environment detected. Attempting identity bootstrap for agent [cyan]{agent_id}[/cyan]...", style="dim")

        try:
            with open(self.K8S_TOKEN_PATH, 'r') as f:
                k8s_token = f.read().strip()

            # Use the enhanced AgentClient bootstrap method
            response = self.client.bootstrap_kubernetes(k8s_token, agent_id)
            
            # The enhanced method returns a validated dictionary
            new_agent_id = response.get("agent_id")
            
            if not new_agent_id:
                raise ValueError("Bootstrap response missing agent_id")

            # Get the stored private key from keyring (already stored by AgentClient)
            keyring_service_name = _get_keyring_service_name_for_agent(new_agent_id)
            try:
                private_key_b64 = keyring.get_password(keyring_service_name, new_agent_id)
                if not private_key_b64:
                    raise ValueError("Private key not found in keyring after bootstrap")
            except Exception as e:
                raise ValueError(f"Failed to retrieve private key from keyring: {e}")

            public_key_b64 = response.get("public_key")
            if not public_key_b64:
                raise ValueError("Bootstrap response missing public_key")

            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Successfully bootstrapped and stored identity for agent [cyan]{new_agent_id}[/cyan].", style="green")

            return AgentIdentity(
                agent_id=new_agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64,
                provider_name=self.name
            )

        except FileNotFoundError:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] ERROR: Kubernetes token file not found at {self.K8S_TOKEN_PATH}.", style="bold red")
            return None
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] ERROR: Failed to bootstrap Kubernetes identity for agent {agent_id}: {e}", style="bold red")
            return None


class AwsIdentityProvider(IdentityProvider):
    """
    An identity provider that bootstraps an agent's identity using an
    AWS IAM role or instance identity document.
    Enhanced to work with the new backend implementation.
    """
    def __init__(self, client: Any, silent_mode: bool = False):
        self.client = client
        self.silent_mode = silent_mode

    @property
    def name(self) -> str:
        return "aws"

    def _is_in_aws(self) -> bool:
        """Check for common AWS environment variables."""
        return "AWS_REGION" in os.environ or "AWS_EXECUTION_ENV" in os.environ

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Performs attestation against the deeptrail-control backend using AWS identity.
        Enhanced with proper error handling and response validation.
        """
        if not self._is_in_aws():
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Not running in an AWS environment (AWS env vars not found). Skipping.", style="dim")
            return None

        if not self.silent_mode:
            utils.console.print(f"[{self.name}] AWS environment detected. Attempting identity bootstrap for agent [cyan]{agent_id}[/cyan]...", style="dim")

        try:
            # NOTE: This requires the 'boto3' package to be installed.
            import boto3
            
            # Get AWS caller identity as the token
            sts_client = boto3.client("sts")
            caller_identity = sts_client.get_caller_identity()
            iam_token = caller_identity['Arn']

            # Use the enhanced AgentClient bootstrap method
            response = self.client.bootstrap_aws(iam_token, agent_id)
            
            # The enhanced method returns a validated dictionary
            new_agent_id = response.get("agent_id")
            
            if not new_agent_id:
                raise ValueError("Bootstrap response missing agent_id")

            # Get the stored private key from keyring (already stored by AgentClient)
            keyring_service_name = _get_keyring_service_name_for_agent(new_agent_id)
            try:
                private_key_b64 = keyring.get_password(keyring_service_name, new_agent_id)
                if not private_key_b64:
                    raise ValueError("Private key not found in keyring after bootstrap")
            except Exception as e:
                raise ValueError(f"Failed to retrieve private key from keyring: {e}")

            public_key_b64 = response.get("public_key")
            if not public_key_b64:
                raise ValueError("Bootstrap response missing public_key")

            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Successfully bootstrapped and stored identity for agent [cyan]{new_agent_id}[/cyan].", style="green")
                
            return AgentIdentity(
                agent_id=new_agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64,
                provider_name=self.name
            )
            
        except ImportError:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] WARNING: 'boto3' package not installed. Skipping AWS identity provider.", style="yellow")
            return None
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] ERROR: Failed to bootstrap AWS identity for agent {agent_id}: {e}", style="bold red")
            return None


class AzureIdentityProvider(IdentityProvider):
    """
    An identity provider that bootstraps an agent's identity using an
    Azure Managed Identity token from the Instance Metadata Service (IMDS).
    """
    IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"
    
    def __init__(self, client: Any, silent_mode: bool = False):
        self.client = client
        self.silent_mode = silent_mode

    @property
    def name(self) -> str:
        return "azure"

    def _is_in_azure(self) -> bool:
        """Check if running in Azure by trying to access IMDS."""
        try:
            import requests
            # Quick check for IMDS availability
            response = requests.get(
                "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                headers={"Metadata": "true"},
                timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def _get_azure_imds_token(self) -> str:
        """Get an Azure IMDS token for the managed identity."""
        import requests
        
        params = {
            "api-version": "2018-02-01",
            "resource": "https://management.azure.com/"
        }
        
        headers = {"Metadata": "true"}
        
        response = requests.get(self.IMDS_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        return token_data["access_token"]

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Performs attestation against the deeptrail-control backend using Azure IMDS token.
        """
        if not self._is_in_azure():
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Not running in an Azure environment (IMDS not accessible). Skipping.", style="dim")
            return None

        if not self.silent_mode:
            utils.console.print(f"[{self.name}] Azure environment detected. Attempting identity bootstrap for agent [cyan]{agent_id}[/cyan]...", style="dim")

        try:
            # Get Azure IMDS token
            imds_token = self._get_azure_imds_token()

            # Use the enhanced AgentClient bootstrap method
            response = self.client.bootstrap_azure(imds_token, agent_id)
            
            # The enhanced method returns a validated dictionary
            new_agent_id = response.get("agent_id")
            
            if not new_agent_id:
                raise ValueError("Bootstrap response missing agent_id")

            # Get the stored private key from keyring (already stored by AgentClient)
            keyring_service_name = _get_keyring_service_name_for_agent(new_agent_id)
            try:
                private_key_b64 = keyring.get_password(keyring_service_name, new_agent_id)
                if not private_key_b64:
                    raise ValueError("Private key not found in keyring after bootstrap")
            except Exception as e:
                raise ValueError(f"Failed to retrieve private key from keyring: {e}")

            public_key_b64 = response.get("public_key")
            if not public_key_b64:
                raise ValueError("Bootstrap response missing public_key")

            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Successfully bootstrapped and stored identity for agent [cyan]{new_agent_id}[/cyan].", style="green")
                
            return AgentIdentity(
                agent_id=new_agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64,
                provider_name=self.name
            )
            
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] ERROR: Failed to bootstrap Azure identity for agent {agent_id}: {e}", style="bold red")
            return None


class DockerIdentityProvider(IdentityProvider):
    """
    An identity provider that bootstraps an agent's identity using
    Docker container runtime metadata and a verification token.
    """
    def __init__(self, client: Any, silent_mode: bool = False):
        self.client = client
        self.silent_mode = silent_mode

    @property
    def name(self) -> str:
        return "docker"

    def _is_in_docker(self) -> bool:
        """Check if running inside a Docker container."""
        # Check for .dockerenv file (most common indicator)
        if os.path.exists("/.dockerenv"):
            return True
        
        # Check cgroup for docker indicators
        try:
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                return "docker" in content or "containerd" in content
        except:
            return False

    def _generate_runtime_token(self) -> str:
        """
        Generate a runtime verification token using container metadata.
        This is a simplified implementation - in production this would be more robust.
        """
        import hashlib
        import time
        
        # Gather container runtime information
        container_info = {
            "hostname": os.environ.get("HOSTNAME", "unknown"),
            "timestamp": int(time.time()),
            "pid": os.getpid()
        }
        
        # Create a runtime token (simplified - production would use proper secrets)
        token_data = f"{container_info['hostname']}:{container_info['timestamp']}:{container_info['pid']}"
        runtime_token = hashlib.sha256(token_data.encode()).hexdigest()
        
        return runtime_token

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Performs attestation against the deeptrail-control backend using Docker runtime token.
        """
        if not self._is_in_docker():
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Not running in a Docker environment. Skipping.", style="dim")
            return None

        if not self.silent_mode:
            utils.console.print(f"[{self.name}] Docker environment detected. Attempting identity bootstrap for agent [cyan]{agent_id}[/cyan]...", style="dim")

        try:
            # Generate runtime verification token
            runtime_token = self._generate_runtime_token()

            # Use the enhanced AgentClient bootstrap method
            response = self.client.bootstrap_docker(runtime_token, agent_id)
            
            # The enhanced method returns a validated dictionary
            new_agent_id = response.get("agent_id")
            
            if not new_agent_id:
                raise ValueError("Bootstrap response missing agent_id")

            # Get the stored private key from keyring (already stored by AgentClient)
            keyring_service_name = _get_keyring_service_name_for_agent(new_agent_id)
            try:
                private_key_b64 = keyring.get_password(keyring_service_name, new_agent_id)
                if not private_key_b64:
                    raise ValueError("Private key not found in keyring after bootstrap")
            except Exception as e:
                raise ValueError(f"Failed to retrieve private key from keyring: {e}")

            public_key_b64 = response.get("public_key")
            if not public_key_b64:
                raise ValueError("Bootstrap response missing public_key")

            if not self.silent_mode:
                utils.console.print(f"[{self.name}] Successfully bootstrapped and stored identity for agent [cyan]{new_agent_id}[/cyan].", style="green")
                
            return AgentIdentity(
                agent_id=new_agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64,
                provider_name=self.name
            )
            
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[{self.name}] ERROR: Failed to bootstrap Docker identity for agent {agent_id}: {e}", style="bold red")
            return None 