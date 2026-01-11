"""
OpenAI integration for DeepSecure.

This module provides convenience methods for interacting with the OpenAI API
through the DeepSecure Gateway. It uses the generic GatewayClient underneath.
"""

from typing import Any, Dict, List, Optional
import httpx


class OpenAIIntegration:
    """
    Convenience wrapper for OpenAI API calls through the DeepSecure Gateway.
    
    This integration provides high-level methods for common OpenAI operations
    while the underlying GatewayClient handles authentication, policy enforcement,
    and secret injection.
    
    Example usage:
        # List models
        resp = client.openai.list_models(agent_id=agent.id)
        
        # Chat completion
        resp = client.openai.chat_completion(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gpt-4"
        )
    """
    
    TARGET_BASE_URL = "https://api.openai.com"
    DEFAULT_SECRET = "openai-api-key"
    
    def __init__(self, client: 'Client'):
        """
        Initialize the OpenAI integration.
        
        Args:
            client: The main DeepSecure Client instance
        """
        self._client = client
    
    def list_models(self, agent_id: Optional[str] = None) -> httpx.Response:
        """
        List available OpenAI models.
        
        Args:
            agent_id: Agent making the request. Uses current session if None.
            
        Returns:
            httpx.Response containing the list of models
            
        Example:
            resp = client.openai.list_models()
            models = resp.json()["data"]
            for m in models:
                print(m["id"])
        """
        return self._client.gateway.get(
            "/v1/models",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET
        )
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        agent_id: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Create a chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (default: "gpt-4")
            agent_id: Agent making the request. Uses current session if None.
            **kwargs: Additional parameters passed to the API (temperature, max_tokens, etc.)
            
        Returns:
            httpx.Response containing the completion
            
        Example:
            resp = client.openai.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello!"}
                ],
                model="gpt-4",
                temperature=0.7
            )
            print(resp.json()["choices"][0]["message"]["content"])
        """
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        return self._client.gateway.post(
            "/v1/chat/completions",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET,
            json=payload
        )
    
    def create_embedding(
        self,
        input: str,
        model: str = "text-embedding-3-small",
        agent_id: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Create an embedding for the given input.
        
        Args:
            input: Text to embed
            model: Embedding model to use
            agent_id: Agent making the request. Uses current session if None.
            **kwargs: Additional parameters
            
        Returns:
            httpx.Response containing the embedding
        """
        payload = {
            "model": model,
            "input": input,
            **kwargs
        }
        
        return self._client.gateway.post(
            "/v1/embeddings",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET,
            json=payload
        )
    
    def list_files(self, agent_id: Optional[str] = None) -> httpx.Response:
        """
        List files uploaded to OpenAI.
        
        Args:
            agent_id: Agent making the request. Uses current session if None.
            
        Returns:
            httpx.Response containing the list of files
        """
        return self._client.gateway.get(
            "/v1/files",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET
        )
