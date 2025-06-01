'''Base client class for API interaction.'''

import os
from typing import Dict, Any, Optional
import requests
import logging

from .. import exceptions
from .. import __version__ # Import the version
# from ..core.config import load_cli_config # Removed config import

logger = logging.getLogger(__name__)

class BaseClient:
    """Base client for DeepSecure API interactions.

    Handles header construction (including auth) and making HTTP requests.
    Reads configuration directly from environment variables.
    """

    def __init__(self):
        """
        Initialize the base client.
        """
        # Removed config loading
        self._backend_url: Optional[str] = None
        self._backend_api_token: Optional[str] = None
        self.session = requests.Session() # Use a session object

    # Removed config property
    # @property
    # def config(self) -> Dict[str, Any]: ...

    @property
    def backend_url(self) -> Optional[str]:
        """Get the backend service URL from environment variable."""
        if self._backend_url is None:
            env_url = os.environ.get("DEEPSECURE_CREDSERVICE_URL")
            # Removed config file fallback
            self._backend_url = env_url
            if self._backend_url:
                 logger.debug(f"Using backend URL from env: {self._backend_url}")
            else:
                 logger.warning("Backend URL env var DEEPSECURE_CREDSERVICE_URL is not set.")
        return self._backend_url

    @property
    def backend_api_token(self) -> Optional[str]:
        """Get the backend API token from environment variable."""
        if self._backend_api_token is None:
            env_token = os.environ.get("DEEPSECURE_CREDSERVICE_API_TOKEN")
            # Removed config file fallback
            self._backend_api_token = env_token
            if not self._backend_api_token:
                logger.warning("Backend API token env var DEEPSECURE_CREDSERVICE_API_TOKEN is not set.")
        return self._backend_api_token

    def _make_headers(self, target_url: str) -> Dict[str, str]:
        """Construct standard headers for API requests.
        
        Includes User-Agent and Content-Type. Adds Authorization header
        if the target URL matches the configured backend URL and a token exists.
        """
        headers = {
            "User-Agent": f"DeepSecureCLI/{__version__}", # Use dynamic version
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        token = self.backend_api_token
        backend_url = self.backend_url
        if token and backend_url and target_url.startswith(backend_url):
            logger.debug(f"Adding Authorization header for request to {target_url}")
            headers["Authorization"] = f"Bearer {token}"
        else:
             logger.debug(f"No Authorization header added for request to {target_url}")

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
            logger.debug(f"Response Status: {response.status_code}, URL: {response.url}")
            response.raise_for_status() # Raises HTTPError for 4xx/5xx
            if response.status_code == 204: # No Content
                return {"status": "success", "data": None} # Return success indicator
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_details = "No response body" 
            try:
                # Try to get more specific detail from JSON response if available
                json_error = response.json()
                error_details = json_error.get("detail", response.text[:500])
            except requests.exceptions.JSONDecodeError:
                 error_details = response.text[:500] if response.text else "No details"
            
            logger.error(
                f"API request failed: {response.status_code} {response.reason}. "
                f"URL: {response.url}. Details: {error_details}"
            )
            # Raise specific exception with details
            raise exceptions.ApiError(
                f"API Error {response.status_code}: {error_details}",
                status_code=response.status_code
            ) from e
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"Failed to decode API response as JSON. URL: {response.url}. Response text: {response.text[:200]}")
            raise exceptions.ApiError(f"Failed to decode API response as JSON. URL: {response.url}") from e

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_backend_request: bool = False # Flag to indicate if this is for the credservice backend
    ) -> Dict[str, Any]:
        """Make an HTTP request.
        
        Args:
            method: HTTP method (e.g., "GET", "POST", "PUT", "DELETE").
            path: API endpoint path (e.g., "/credentials" or full URL if not backend).
            params: Optional dictionary of query string parameters.
            data: Optional dictionary of data to send in the request body (for POST/PUT).
            is_backend_request: If True, use the configured backend URL and add auth.

        Returns:
            The parsed JSON response from the API.

        Raises:
            exceptions.ApiError: If the API request fails.
            ValueError: If backend URL is needed but not configured.
        """
        if is_backend_request:
            base_url = self.backend_url
            if not base_url:
                # Updated error message
                raise ValueError("Backend URL env var DEEPSECURE_CREDSERVICE_URL is not set.")
            # Ensure path starts with / and base_url doesn't end with /
            full_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        else:
            # Assume path is already a full URL for non-backend requests (if any)
            full_url = path 

        headers = self._make_headers(target_url=full_url)

        logger.info(f"Sending {method} request to {full_url}")
        if params: logger.debug(f" - Query Params: {params}")
        if data: logger.debug(f" - Request Body: {data}") # Be cautious logging sensitive data
        logger.debug(f" - Headers: { {k: v for k, v in headers.items() if k.lower() != 'authorization'} }") # Log headers except auth

        try:
            response = self.session.request(
                method,
                full_url,
                headers=headers,
                params=params,
                json=data,
                timeout=30 # Increased timeout
            )
            return self._handle_response(response)
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out: {method} {full_url}")
            raise exceptions.ApiError(f"Request timed out accessing {full_url}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {method} {full_url}: {e}")
            raise exceptions.ApiError(f"Could not connect to {full_url}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during API request: {method} {full_url}: {e}")
            raise exceptions.ApiError(f"Network error during API request to {full_url}: {e}") from e 