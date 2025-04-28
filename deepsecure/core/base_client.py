'''Base client class for API interaction.'''

import os
from typing import Dict, Any, Optional
import requests

from .. import auth, config, exceptions

class BaseClient:
    """Base client for DeepSecure API interactions."""
    
    def __init__(self, service_name: str):
        """
        Initialize the base client.
        
        Args:
            service_name: Name of the service this client interacts with
        """
        self.service_name = service_name
        self.api_url = self._get_api_url()
        self.token = self._get_token()
    
    def _get_api_url(self) -> str:
        """Get the API URL from environment or config."""
        # Priority: Environment variable > Config file > Default
        env_var = f"DEEPSECURE_{self.service_name.upper()}_API_URL"
        return os.environ.get(env_var, f"https://api.deepsecure.dev/v1/{self.service_name}")
    
    def _get_token(self) -> Optional[str]:
        """Get the authentication token."""
        return auth.get_token()
    
    def _make_headers(self) -> Dict[str, str]:
        """Create headers for API requests."""
        headers = {
            "User-Agent": "DeepSecureCLI/0.0.2",
            "Content-Type": "application/json",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    def _handle_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle and standardize API response.
        
        Args:
            response_data: The raw API response data
            
        Returns:
            Standardized response data
        """
        # In a real implementation, this would validate the response format,
        # handle errors, etc. For now, we'll just return the data as-is.
        return response_data
    
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
        print(f"[DEBUG] Would make {method} request to {self.api_url}{path}")
        print(f"[DEBUG] - params: {params}")
        print(f"[DEBUG] - data: {data}")
        
        # In a real implementation:
        # url = f"{self.api_url}{path}"
        # headers = self._make_headers()
        # response = requests.request(method, url, headers=headers, params=params, json=data)
        # if not response.ok:
        #     raise exceptions.ApiError(f"API error: {response.status_code} - {response.text}")
        # return response.json()
        
        # Return dummy successful response
        return {"status": "success", "data": {}} 