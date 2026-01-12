"""
Anthropic integration for DeepSecure.

This module provides convenience methods for interacting with the Anthropic API
(Claude models) through the DeepSecure Gateway.
"""

from typing import Any, Dict, List, Optional, Union
import httpx


class AnthropicIntegration:
    """
    Convenience wrapper for Anthropic API calls through the DeepSecure Gateway.
    
    This integration provides high-level methods for common Anthropic operations
    while the underlying GatewayClient handles authentication, policy enforcement,
    and secret injection.
    
    Example usage:
        # Create a message
        resp = client.anthropic.create_message(
            messages=[{"role": "user", "content": "Hello, Claude!"}],
            model="claude-3-sonnet-20240229"
        )
        
        # Stream a response
        resp = client.anthropic.create_message(
            messages=[{"role": "user", "content": "Tell me a story"}],
            stream=True
        )
    """
    
    TARGET_BASE_URL = "https://api.anthropic.com"
    DEFAULT_SECRET = "anthropic-api-key"
    DEFAULT_VERSION = "2023-06-01"
    
    def __init__(self, client: 'Client'):
        """
        Initialize the Anthropic integration.
        
        Args:
            client: The main DeepSecure Client instance
        """
        self._client = client
    
    def _get_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Get required Anthropic headers.
        
        Args:
            extra_headers: Additional headers to include
            
        Returns:
            Dict of headers including anthropic-version
        """
        headers = {
            "anthropic-version": self.DEFAULT_VERSION,
            "content-type": "application/json"
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        agent_id: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        stream: bool = False,
        **kwargs
    ) -> httpx.Response:
        """
        Create a message using Claude.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
                     Roles can be 'user' or 'assistant'.
            model: Model to use. Options include:
                   - "claude-sonnet-4-20250514" (default, best balance)
                   - "claude-3-5-sonnet-20241022" (previous generation)
                   - "claude-3-opus-20240229" (most capable)
                   - "claude-3-haiku-20240307" (fastest)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            agent_id: Agent making the request. Uses current session if None.
            system: System prompt (optional)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            stop_sequences: List of sequences that stop generation
            stream: Whether to stream the response
            **kwargs: Additional parameters passed to the API
            
        Returns:
            httpx.Response containing the message
            
        Example:
            # Simple message
            resp = client.anthropic.create_message(
                messages=[{"role": "user", "content": "What is Python?"}],
                model="claude-sonnet-4-20250514",
                max_tokens=500
            )
            data = resp.json()
            print(data["content"][0]["text"])
            
            # With system prompt
            resp = client.anthropic.create_message(
                messages=[{"role": "user", "content": "Hello!"}],
                system="You are a helpful coding assistant.",
                temperature=0.7
            )
            
            # Multi-turn conversation
            resp = client.anthropic.create_message(
                messages=[
                    {"role": "user", "content": "My name is Alice."},
                    {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
                    {"role": "user", "content": "What's my name?"}
                ]
            )
        """
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        
        if system is not None:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if top_k is not None:
            payload["top_k"] = top_k
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        if stream:
            payload["stream"] = True
        
        # Add any additional kwargs
        payload.update(kwargs)
        
        return self._client.gateway.post(
            "/v1/messages",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET,
            headers=self._get_headers(),
            json=payload
        )
    
    def count_tokens(
        self,
        messages: List[Dict[str, Any]],
        model: str = "claude-sonnet-4-20250514",
        agent_id: Optional[str] = None,
        system: Optional[str] = None,
    ) -> httpx.Response:
        """
        Count tokens in a message before sending.
        
        This is useful for managing context window limits.
        
        Args:
            messages: List of message dicts to count tokens for
            model: Model to use for tokenization
            agent_id: Agent making the request. Uses current session if None.
            system: System prompt (optional)
            
        Returns:
            httpx.Response with token count
            
        Example:
            resp = client.anthropic.count_tokens(
                messages=[{"role": "user", "content": "Hello, Claude!"}]
            )
            count = resp.json()["input_tokens"]
            print(f"Message uses {count} tokens")
        """
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        
        if system is not None:
            payload["system"] = system
        
        return self._client.gateway.post(
            "/v1/messages/count_tokens",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET,
            headers=self._get_headers(),
            json=payload
        )
    
    def complete(
        self,
        prompt: str,
        model: str = "claude-2.1",
        max_tokens_to_sample: int = 1024,
        agent_id: Optional[str] = None,
        stop_sequences: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Create a completion using the legacy completions API.
        
        Note: This is the older API. For new applications, use create_message().
        
        Args:
            prompt: The prompt to complete (must start with "\\n\\nHuman:" and end with "\\n\\nAssistant:")
            model: Model to use (e.g., "claude-2.1", "claude-instant-1.2")
            max_tokens_to_sample: Maximum tokens to generate
            agent_id: Agent making the request. Uses current session if None.
            stop_sequences: List of sequences that stop generation
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Returns:
            httpx.Response containing the completion
        """
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "max_tokens_to_sample": max_tokens_to_sample,
        }
        
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        if temperature is not None:
            payload["temperature"] = temperature
        
        payload.update(kwargs)
        
        return self._client.gateway.post(
            "/v1/complete",
            self.TARGET_BASE_URL,
            agent_id=agent_id,
            secret_name=self.DEFAULT_SECRET,
            headers=self._get_headers(),
            json=payload
        )
