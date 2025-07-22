# deepsecure/core/identity_manager.py
import os
import json
import time
import uuid
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import sys

import keyring # Import the keyring library
# Make sure to handle potential import errors for keyring itself if it's optional
# For now, assume it's a hard dependency for secure storage.
from keyring.errors import NoKeyringError, PasswordDeleteError, PasswordSetError

# Import the key_manager instance directly
from .crypto.key_manager import key_manager
from .. import utils
from ..exceptions import DeepSecureClientError, IdentityManagerError
from cryptography.hazmat.primitives.asymmetric import ed25519

# Import the new identity provider abstractions
from .identity_provider import AgentIdentity, IdentityProvider, KeyringIdentityProvider, _get_keyring_service_name_for_agent


class IdentityManager:
    """
    Manages agent identities, coordinating between multiple sources (providers)
    and handling the secure storage of private keys in the system keyring.
    
    This class orchestrates a chain of IdentityProviders to find an agent's
    identity, while also remaining the central point for creating, storing,
    and deleting the cryptographic keys that underpin those identities.
    """
    
    def __init__(self, api_client: 'BaseClient', providers: Optional[List[IdentityProvider]] = None, silent_mode: bool = False):
        self.silent_mode = silent_mode
        self.key_manager = key_manager
        self.api_client = api_client
        
        # Initialize environment detector for intelligent provider selection
        from .environment_detector import environment_detector
        self.environment_detector = environment_detector
        
        if providers is None:
            # Use intelligent provider selection based on environment detection
            self.providers = self._create_intelligent_provider_chain()
        else:
            self.providers = providers
        
        if not self.silent_mode:
            provider_names = ", ".join(f"[bold cyan]{p.name}[/bold cyan]" for p in self.providers)
            utils.console.print(f"[IdentityManager] Initialized with identity providers: {provider_names}", style="dim")
            
            # Log environment detection results
            env_summary = self.environment_detector.get_environment_summary()
            utils.console.print(
                f"[IdentityManager] Environment: {env_summary['detected_environment']} "
                f"(confidence: {env_summary['confidence']:.2f})", 
                style="dim"
            )
            
    def _create_intelligent_provider_chain(self) -> List[IdentityProvider]:
        """
        Create an intelligent provider chain based on environment detection.
        Orders providers by likelihood of success in the current environment.
        """
        from .identity_provider import (
            KubernetesIdentityProvider,
            AwsIdentityProvider, 
            AzureIdentityProvider,
            DockerIdentityProvider,
            KeyringIdentityProvider
        )
        
        providers = []
        
        # Get environment detection results
        recommended_method, env_info = self.environment_detector.get_recommended_bootstrap_method()
        
        if not self.silent_mode:
            utils.console.print(
                f"[IdentityManager] Recommended bootstrap method: {recommended_method or 'none (local)'}", 
                style="dim"
            )
        
        # Create all available providers
        all_providers = {
            "kubernetes": KubernetesIdentityProvider(client=self.api_client, silent_mode=self.silent_mode),
            "aws": AwsIdentityProvider(client=self.api_client, silent_mode=self.silent_mode),
            "azure": AzureIdentityProvider(client=self.api_client, silent_mode=self.silent_mode),
            "docker": DockerIdentityProvider(client=self.api_client, silent_mode=self.silent_mode)
        }
        
        # Add the recommended provider first (highest priority)
        if recommended_method and recommended_method in all_providers:
            providers.append(all_providers[recommended_method])
            del all_providers[recommended_method]  # Remove to avoid duplicates
        
        # Add remaining providers in order of general likelihood
        provider_order = ["kubernetes", "aws", "azure", "docker"]
        for provider_name in provider_order:
            if provider_name in all_providers:
                providers.append(all_providers[provider_name])
        
        # Always add the keyring provider as fallback
        providers.append(KeyringIdentityProvider(silent_mode=self.silent_mode))
        
        return providers
    
    def get_identity_with_auto_bootstrap(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Get agent identity with automatic bootstrap if supported by environment.
        This is an enhanced version that tries bootstrap automatically in suitable environments.
        
        Args:
            agent_id: Agent ID to get identity for
            
        Returns:
            AgentIdentity if found or successfully bootstrapped
        """
        # First try the standard provider chain
        identity = self.get_identity(agent_id)
        if identity:
            return identity
        
        # If no identity found, check if we can auto-bootstrap
        recommended_method, env_info = self.environment_detector.get_recommended_bootstrap_method()
        
        if not recommended_method or not env_info.bootstrap_capable:
            if not self.silent_mode:
                utils.console.print(
                    f"[IdentityManager] No identity found for {agent_id} and auto-bootstrap not available in this environment",
                    style="yellow"
                )
            return None
        
        if not self.silent_mode:
            utils.console.print(
                f"[IdentityManager] No identity found for {agent_id}, attempting auto-bootstrap using {recommended_method}",
                style="yellow"
            )
        
        # Try auto-bootstrap using the recommended provider
        for provider in self.providers:
            if provider.name == recommended_method:
                try:
                    bootstrap_identity = provider.get_identity(agent_id)
                    if bootstrap_identity:
                        if not self.silent_mode:
                            utils.console.print(
                                f"[IdentityManager] Successfully auto-bootstrapped identity for {agent_id} using {recommended_method}",
                                style="green"
                            )
                        return bootstrap_identity
                except Exception as e:
                    if not self.silent_mode:
                        utils.console.print(
                            f"[IdentityManager] Auto-bootstrap failed for {agent_id} using {recommended_method}: {e}",
                            style="red"
                        )
                break
        
        return None
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get detailed environment information for debugging and logging."""
        return self.environment_detector.get_environment_summary()

    def authenticate(self, agent_id: str) -> str:
        """
        Authenticates the agent and returns a JWT.
        Delegates the entire challenge-response flow to the API client.
        """
        if not self.api_client:
            raise IdentityManagerError("API client not configured. Cannot authenticate.")
        
        try:
            # The api_client handles the full challenge-response flow
            return self.api_client.get_access_token(agent_id)
        except Exception as e:
            # Re-raise exceptions from the client as IdentityManagerErrors
            # for consistent error handling at the call site.
            raise IdentityManagerError(f"Authentication failed for agent {agent_id}: {e}") from e

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """
        Attempts to find an agent's identity by querying the configured providers in order.
        
        Args:
            agent_id: The ID of the agent to find.
            
        Returns:
            An AgentIdentity object if found, otherwise None.
        """
        if not self.silent_mode:
            utils.console.print(f"[IdentityManager] Searching for identity for agent [cyan]{agent_id}[/cyan]...", style="dim")
            
        for provider in self.providers:
            try:
                identity = provider.get_identity(agent_id)
                if identity:
                    if not self.silent_mode:
                        utils.console.print(f"[IdentityManager] Identity for agent [cyan]{agent_id}[/cyan] successfully found via [bold green]{provider.name}[/bold green] provider.", style="green")
                    return identity
            except Exception as e:
                # Log errors from providers but don't stop the chain
                if not self.silent_mode:
                    utils.console.print(f"[IdentityManager] Error from provider '{provider.name}' for agent {agent_id}: {e}", style="bold red")
        
        if not self.silent_mode:
            utils.console.print(f"[IdentityManager] Identity for agent [yellow]{agent_id}[/yellow] could not be found via any configured provider.", style="yellow")
            
        return None
        
    @staticmethod
    def generate_agent_id(public_key_pem: str) -> str:
        """
        Generates a unique, deterministic agent ID from its public key.
        This ensures that the same public key will always produce the same agent ID.
        """
        # Create a SHA-256 hash of the public key bytes
        hasher = hashlib.sha256()
        hasher.update(public_key_pem.encode('utf-8'))
        # Use the first part of the hex digest for a readable, unique ID
        return f"agent-{hasher.hexdigest()[:16]}"

    def _generate_agent_id(self) -> str:
        """Generate a new agent ID."""
        return f"agent-{uuid.uuid4()}"

    def generate_ed25519_keypair_raw_b64(self) -> Dict[str, str]:
        """
        Generates a new Ed25519 key pair.
        Returns: Dict with "private_key" and "public_key" (base64-encoded raw bytes).
        """
        return self.key_manager.generate_identity_keypair()

    def get_public_key_fingerprint(self, public_key_b64: str) -> str:
        """Generate a fingerprint for the given public key."""
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            fingerprint = hashlib.sha256(public_key_bytes).hexdigest()
            return f"sha256:{fingerprint[:64]}"
        except Exception as e:
            raise IdentityManagerError(f"Failed to generate fingerprint: {e}")

    def decode_private_key(self, private_key_b64: str):
        """Decode a base64-encoded private key for cryptographic operations."""
        try:
            private_key_bytes = base64.b64decode(private_key_b64)
            return ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        except Exception as e:
            raise IdentityManagerError(f"Failed to decode private key: {e}")

    def create_keypair_for_agent(self, agent_id: str) -> Dict[str, str]:
        """
        Creates and stores a new keypair for the given agent ID.
        Only stores the private key in keychain - no local metadata files.
        
        Returns: Dict with public_key, private_key, and public_key_fingerprint
        """
        # Generate new keypair
        keys = self.generate_ed25519_keypair_raw_b64()
        public_key_b64 = keys["public_key"]
        private_key_b64 = keys["private_key"]
        
        # Store private key in keychain
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Private key for agent [cyan]{agent_id}[/cyan] securely stored in system keyring (Service: '{keyring_service_name}').", style="green")
        except NoKeyringError:
            msg = (f"CRITICAL SECURITY RISK: No system keyring backend found. "
                   f"Private key for agent {agent_id} cannot be stored securely. "
                   f"Aborting keypair creation. Please install and configure a keyring backend.")
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg)
        except PasswordSetError as pse:
            msg = f"Failed to store private key in keyring for agent {agent_id} (PasswordSetError): {pse}. Check keyring access and permissions."
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from pse
        except Exception as e:
            msg = f"An unexpected error occurred while storing private key in keyring for agent {agent_id}: {e}"
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from e

        # Generate fingerprint
        try:
            public_key_fingerprint = self.get_public_key_fingerprint(public_key_b64)
        except IdentityManagerError as e:
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Warning: Could not generate fingerprint for new keypair {agent_id}: {e}", style="yellow")
            public_key_fingerprint = "Error/Unavailable"
        
        return {
            "public_key": public_key_b64,
            "private_key": private_key_b64,
            "public_key_fingerprint": public_key_fingerprint
        }

    def delete_private_key(self, agent_id: str) -> bool:
        """
        Deletes the private key for an agent from the keychain.
        Returns True if successful or key didn't exist, False on error.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            keyring.delete_password(keyring_service_name, agent_id)
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Deleted private key for agent {agent_id} from system keyring (Service: '{keyring_service_name}').", style="dim")
            return True
        except PasswordDeleteError: 
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Private key for agent {agent_id} not found in system keyring (Service: '{keyring_service_name}') (considered success for deletion).", style="dim")
            return True
        except NoKeyringError:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Warning: No system keyring backend. Cannot delete private key for agent {agent_id} from keyring (Service: '{keyring_service_name}').", style="bold yellow")
            return False
        except Exception as e:
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Error deleting key for {agent_id} from keyring: {e}", style="bold red")
            return False

    def get_all_keychain_agent_ids(self) -> List[str]:
        """
        Scans the keychain for all stored agent keys and returns their IDs.
        WARNING: This is a potentially slow and inefficient operation on some backends.
        """
        # This is a placeholder for a more robust discovery mechanism if keyring supported it.
        # For now, we cannot list credentials across services, so this is not feasible.
        # We will need a local manifest file to track agent IDs. This will be revisited.
        raise NotImplementedError("Reliable discovery of all agent IDs from keyring is not currently supported.")

    def cleanup_orphaned_keychain_entries(self, valid_agent_ids: List[str], confirm: bool = True) -> int:
        """
        Compares a list of valid agent IDs from the API with keys in the keychain and
        removes any orphaned keys.
        """
        # This function also depends on the get_all_keychain_agent_ids and is thus not implementable
        # in its current form. Will be implemented when local agent manifest is added.
        raise NotImplementedError("Orphaned key cleanup is not supported without a local agent manifest.")

    def store_private_key_directly(self, agent_id: str, private_key_b64: str) -> None:
        """
        A direct method to store a private key in the keyring, bypassing generation.
        Useful for tests or when restoring an identity.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode:
                utils.console.print(f"Stored private key for {agent_id} in keychain.", style="dim")
        except NoKeyringError:
            raise IdentityManagerError("No system keyring backend found. Cannot store private key.")
        except Exception as e:
            raise IdentityManagerError(f"Failed to store private key directly: {e}") from e

    def get_private_key(self, agent_id: str) -> Optional[str]:
        """
        Retrieves an agent's private key directly from the keyring.
        Returns the base64-encoded private key string or None if not found.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            return keyring.get_password(keyring_service_name, agent_id)
        except NoKeyringError:
            return None # If no keyring, no key can be found
        except Exception:
            return None # Any other error, assume key is not available

    def sign(self, private_key_b64: str, data: Union[str, bytes]) -> str:
        """Signs data with the given private key."""
        try:
            private_key = self.decode_private_key(private_key_b64)
            message_bytes = data.encode('utf-8') if isinstance(data, str) else data
            signature_bytes = private_key.sign(message_bytes)
            return base64.b64encode(signature_bytes).decode('utf-8')
        except Exception as e:
            raise IdentityManagerError(f"Failed to sign message: {e}") 