from typing import Any, Dict, Optional
import requests
from .._core.base_client import BaseClient

class OpenAIIntegration:
    """
    Helper for interacting with OpenAI via the DeepSecure Gateway.
    """
    def __init__(self, client: BaseClient):
        self._client = client

    def list_models(self, agent_id: str) -> Any:
        """
        Lists OpenAI models via the gateway.
        
        This effectively calls GET /v1/models on OpenAI, 
        but routed through the DeepSecure Gateway which injects the API key.
        """
        # We use the 'get_secret' pattern where the gateway fetches the secret
        # and forwards the request.
        # Ideally, this should be a more generic 'proxy_request' method on the client,
        # but 'get_secret' currently implements the gateway proxy logic.
        # We might need to refactor Client.get_secret to be more generic or use it here.
        
        # Assuming Client has a method to proxy requests. 
        # Looking at Client.get_secret, it does exactly this:
        # calls /proxy/{path} with X-Deeptrail-Secret-Name header.
        
        # However, OpenAIIntegration doesn't have access to 'get_secret' if passed BaseClient.
        # It needs 'Client' or we need to duplicate the proxy logic or move it to BaseClient.
        # For now, let's assume we can call a method on the parent client or replicate the request.
        
        # Let's look at how Client.get_secret is implemented:
        # headers = {
        #     "X-Deeptrail-Secret-Name": secret_name,
        #     "X-Target-Base-URL": target_base_url 
        # }
        # response = self._authenticated_request("GET", f"/proxy/{path}", ...)
        
        secret_name = "openai-api-key"
        target_base_url = "https://api.openai.com"
        path = "v1/models"
        
        headers = {
            "X-Deeptrail-Secret-Name": secret_name,
            "X-Target-Base-URL": target_base_url
        }
        
        # We need to use _authenticated_request from the client
        response = self._client._authenticated_request(
            "GET",
            f"/proxy/{path}",
            agent_id=agent_id,
            headers=headers,
            base_url_override=self._client._gateway_url 
        )
        
        return response
