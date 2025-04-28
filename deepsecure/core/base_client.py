'''Base client class for API interaction.'''

import os
from typing import Dict, Any, Optional
import requests

from .. import auth, exceptions

# TODO: Integrate config loading (e.g., from config.py or a config object)
#       to get API URLs and other settings instead of relying solely on env vars/defaults.

class BaseClient:
    """Base client for DeepSecure API interactions.
    
    Provides common functionality for service-specific clients, including:
    - Determining the target API URL.
    - Retrieving the authentication token.
    - Constructing standard request headers.
    - A placeholder method for making HTTP requests.
    """
    
    def __init__(self, service_name: str):
        """
        Initialize the base client for a specific DeepSecure service.
        
        Args:
            service_name: The name of the service (e.g., "vault", "audit") used
                          to determine API URLs and potentially configuration.
        """
        self.service_name = service_name
        self.api_url = self._get_api_url()
        self.token = self._get_token()
        # TODO: Initialize requests.Session() for connection pooling and configuration.
    
    def _get_api_url(self) -> str:
        """Determine the API URL for the service.
        
        Checks for an environment variable `DEEPSECURE_<SERVICE_NAME>_API_URL` first,
        then falls back to a default URL structure.
        
        Returns:
            The determined API URL string.
        """
        # TODO: Integrate with a config system for more flexible URL configuration.
        env_var = f"DEEPSECURE_{self.service_name.upper()}_API_URL"
        # TODO: Use a centralized default base URL.
        default_url = f"https://api.deepsecure.dev/v1/{self.service_name}"
        return os.environ.get(env_var, default_url)
    
    def _get_token(self) -> Optional[str]:
        """Retrieve the authentication token using the auth module.
        
        Returns:
            The authentication token string, or None if not found.
        """
        return auth.get_token()
    
    def _make_headers(self) -> Dict[str, str]:
        """Construct standard headers for API requests.
        
        Includes User-Agent, Content-Type, and Authorization (Bearer token)
        if a token is available.
        
        Returns:
            A dictionary of HTTP headers.
        """
        # TODO: Get version dynamically for User-Agent.
        headers = {
            "User-Agent": "DeepSecureCLI/0.0.2", 
            "Content-Type": "application/json",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        # TODO: Add other potential standard headers (e.g., Accept, Request-ID).
        
        return headers
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle and parse the API response.

        Checks for HTTP errors and attempts to parse the JSON body.
        
        Args:
            response: The `requests.Response` object.
            
        Returns:
            The parsed JSON response data as a dictionary.
            
        Raises:
            exceptions.ApiError: If the API returns an HTTP error status or 
                               if the response body is not valid JSON.
        """
        try:
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            # TODO: Add more sophisticated error handling based on status codes or error bodies.
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Include response text in the error message if possible
            error_details = response.text[:500] if response.text else "No details"
            raise exceptions.ApiError(
                f"API request failed: {response.status_code} {response.reason}. "
                f"URL: {response.url}. Details: {error_details}"
            ) from e
        except requests.exceptions.JSONDecodeError as e:
            raise exceptions.ApiError(f"Failed to decode API response as JSON. URL: {response.url}") from e
    
    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, 
                 data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request to the service's API.
        
        **(Placeholder)** This method currently prints debug information and returns
        a dummy success response. It needs to be implemented using the `requests` library.
        
        Args:
            method: HTTP method (e.g., "GET", "POST", "PUT", "DELETE").
            path: API endpoint path relative to the service's base URL (e.g., "/credentials").
            params: Optional dictionary of query string parameters.
            data: Optional dictionary of data to send in the request body (for POST/PUT).
            
        Returns:
            The parsed JSON response from the API (currently placeholder).
            
        Raises:
            exceptions.ApiError: If the API request fails (in a real implementation).
        """
        # TODO: Implement actual HTTP requests using the requests library.
        # url = f"{self.api_url.rstrip('/')}/{path.lstrip('/')}"
        # headers = self._make_headers()
        # try:
        #     response = requests.request(method, url, headers=headers, params=params, json=data, timeout=10)
        #     return self._handle_response(response)
        # except requests.exceptions.RequestException as e:
        #     raise exceptions.ApiError(f"Network error during API request to {url}: {e}") from e
        
        # Placeholder debug output
        full_url = f"{self.api_url.rstrip('/')}/{path.lstrip('/')}"
        print(f"[DEBUG] Would make {method} request to {full_url}")
        if params: print(f"[DEBUG] - params: {params}")
        if data: print(f"[DEBUG] - data: {data}")
        print(f"[DEBUG] - headers: {self._make_headers()}")
        
        # Return dummy successful response for now
        return {"status": "success", "data": {}} 