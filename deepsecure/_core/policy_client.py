'''Client for interacting with the Policy API.'''

from typing import List, Dict, Any

from .base_client import BaseClient
from .._core.schemas import PolicyResponse

class PolicyClient(BaseClient):
    """
    Client for interacting with the policy management endpoints.
    """

    def create(
        self,
        name: str,
        agent_id: str,
        actions: List[str],
        resources: List[str],
        effect: str = "allow",
    ) -> PolicyResponse:
        """
        Creates a new policy.

        Args:
            name: The name of the policy.
            agent_id: The ID of the agent this policy applies to.
            actions: A list of actions allowed by the policy (e.g., 'secret:read').
            resources: A list of resource ARNs this policy applies to.
            effect: The effect of the policy ('allow' or 'deny').

        Returns:
            The created policy object.
        """
        policy_data = {
            "name": name,
            "agent_id": agent_id,
            "actions": actions,
            "resources": resources,
            "effect": effect,
        }
        response = self._request("POST", "/api/v1/policies/", json=policy_data)
        return PolicyResponse(**response.json())

    def list(self) -> List[PolicyResponse]:
        """
        Lists all existing policies.

        Returns:
            A list of policy objects.
        """
        response = self._request("GET", "/api/v1/policies/")
        return [PolicyResponse(**p) for p in response.json()]

    def get(self, policy_id: str) -> PolicyResponse:
        """
        Retrieves a single policy by its ID.

        Args:
            policy_id: The ID of the policy to retrieve.

        Returns:
            The requested policy object.
        """
        response = self._request("GET", f"/api/v1/policies/{policy_id}")
        return PolicyResponse(**response.json())

    def delete(self, policy_id: str) -> Dict[str, Any]:
        """
        Deletes a policy by its ID.

        Args:
            policy_id: The ID of the policy to delete.
        
        Returns:
            A confirmation message.
        """
        response = self._request("DELETE", f"/api/v1/policies/{policy_id}")
        return response.json()

    def create_attestation_policy(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new attestation policy.

        Args:
            policy_data: The dictionary containing the policy details.

        Returns:
            The created attestation policy object.
        """
        response = self._request("POST", "/api/v1/policies/attestation/", json=policy_data)
        return response.json()

    def list_attestation_policies(self) -> List[Dict[str, Any]]:
        """
        Lists all existing attestation policies.

        Returns:
            A list of attestation policy objects.
        """
        response = self._request("GET", "/api/v1/policies/attestation/")
        return response.json()

    def get_attestation_policy(self, policy_id: str) -> Dict[str, Any]:
        """
        Retrieves a single attestation policy by its ID.

        Args:
            policy_id: The ID of the attestation policy to retrieve.

        Returns:
            The requested attestation policy object.
        """
        response = self._request("GET", f"/api/v1/policies/attestation/{policy_id}")
        return response.json()

    def update_attestation_policy(self, policy_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates an attestation policy.

        Args:
            policy_id: The ID of the attestation policy to update.
            update_data: The dictionary containing the fields to update.

        Returns:
            The updated attestation policy object.
        """
        response = self._request("PUT", f"/api/v1/policies/attestation/{policy_id}", json=update_data)
        return response.json()

    def delete_attestation_policy(self, policy_id: str) -> Dict[str, Any]:
        """
        Deletes an attestation policy by its ID.

        Args:
            policy_id: The ID of the attestation policy to delete.
        
        Returns:
            A confirmation message.
        """
        response = self._request("DELETE", f"/api/v1/policies/attestation/{policy_id}")
        return response.json() 