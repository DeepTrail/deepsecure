'''Base client class for API interaction.'''

from typing import Dict, Any, Optional
import requests

from .. import auth, config, exceptions

class BaseClient:
    """Base client for API interactions, handling authentication and common operations."""
    
    def __init__(self, service_name: str):
        """Initialize the base client.
        
        Args:
            service_name: The name of the service (e.g., "vault", "audit").
        """
        self.service_name = service_name
        self.base_url = self._get_service_url()
    
    def _get_service_url(self) -> str:
        """Get the base URL for the service from configuration."""
        api_endpoint = config.get_config_value("api_endpoint")
        return f"{api_endpoint}/{self.service_name}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get the common headers for API requests, including auth token."""
        token = auth.ensure_authenticated()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DeepSecure-CLI/0.0.1"  # TODO: Get version dynamically
        }
    
    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, 
                 data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Path relative to the base URL
            params: Query parameters
            data: Request body data
            
        Returns:
            The parsed JSON response
            
        Raises:
            ApiError: If the API returns an error
        """
        # Placeholder implementation that doesn't actually make HTTP requests
        # This would be implemented to use requests.request() in a real implementation
        print(f"[DEBUG] Would make {method} request to {self.base_url}{path}")
        print(f"[DEBUG] - params: {params}")
        print(f"[DEBUG] - data: {data}")
        
        # In a real implementation:
        # url = f"{self.base_url}{path}"
        # headers = self._get_headers()
        # response = requests.request(method, url, headers=headers, params=params, json=data)
        # if not response.ok:
        #     raise exceptions.ApiError(f"API error: {response.status_code} - {response.text}")
        # return response.json()
        
        # Return dummy successful response
        return {"status": "success", "data": {}} 