"""
Just-In-Time (JIT) Secret Reassembly Engine for DeepTrail Gateway

This module implements the core JIT reassembly functionality that:
1. Fetches share_1 from the control plane via internal API
2. Retrieves share_2 from local Redis storage
3. Combines shares using Shamir's Secret Sharing (python-sslib)
4. Returns the complete secret for immediate use
5. Performs secure memory cleanup after use

The JIT approach ensures secrets exist in memory only during active requests,
minimizing the attack surface and providing defense-in-depth security.
"""

import asyncio
import httpx
import gc
import time
import hmac
import hashlib
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
from sslib import shamir

from .share_storage import ShareStorageManager

logger = logging.getLogger(__name__)

class JITReassemblyEngine:
    """
    Just-In-Time secret reassembly engine with secure memory management.
    
    This engine orchestrates the retrieval and combination of secret shares
    to reconstruct complete secrets on-demand, ensuring minimal exposure
    time and secure cleanup.
    """
    
    def __init__(
        self, 
        control_plane_url: str, 
        internal_api_token: str,
        share_storage: ShareStorageManager
    ):
        """
        Initialize the JIT reassembly engine.
        
        Args:
            control_plane_url: URL of the control plane for share_1 retrieval
            internal_api_token: Authentication token for internal API calls
            share_storage: Storage manager for local share_2 retrieval
        """
        self.control_plane_url = control_plane_url.rstrip('/')
        self.internal_api_token = internal_api_token
        self.share_storage = share_storage
        
        # HTTP client for control plane communication
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=10)
        )
        
        logger.info("JIT reassembly engine initialized")
        logger.info(f"Control plane URL: {control_plane_url}")
    
    async def reassemble_secret(
        self, 
        secret_name: str, 
        agent_id: str,
        request_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Reassemble secret from split shares with secure handling.
        
        This is the core JIT reassembly method that:
        1. Fetches share_1 from control plane
        2. Retrieves share_2 from local storage
        3. Combines shares using Shamir's Secret Sharing
        4. Returns the secret for immediate use
        5. Securely clears all sensitive data from memory
        
        Args:
            secret_name: Name of the secret to reassemble
            agent_id: ID of the requesting agent
            request_id: Optional unique request identifier for audit
            
        Returns:
            The reassembled secret value, or None if reassembly fails
        """
        
        # Generate request ID if not provided
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Generate request signature for security
        timestamp = int(time.time())
        request_signature = self._generate_request_signature(
            secret_name, agent_id, request_id, timestamp
        )
        
        logger.info(f"Starting JIT reassembly for secret '{secret_name}' (agent: {agent_id}, request: {request_id})")
        
        try:
            # Parallel retrieval of both shares for performance
            share_1_task = asyncio.create_task(
                self._fetch_share_1(secret_name, agent_id, request_id, timestamp, request_signature)
            )
            share_2_task = asyncio.create_task(
                self._fetch_share_2(secret_name)
            )
            
            # Wait for both shares with timeout
            try:
                share_1_data, share_2_data = await asyncio.wait_for(
                    asyncio.gather(share_1_task, share_2_task, return_exceptions=True),
                    timeout=5.0  # 5 second timeout for share retrieval
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout during share retrieval for '{secret_name}'")
                return None
            
            # Check for errors in share retrieval
            if isinstance(share_1_data, Exception):
                logger.error(f"Failed to fetch share_1 for '{secret_name}': {share_1_data}")
                return None
            
            if isinstance(share_2_data, Exception):
                logger.error(f"Failed to fetch share_2 for '{secret_name}': {share_2_data}")
                return None
            
            if not share_1_data or not share_2_data:
                logger.warning(f"Missing shares for secret '{secret_name}' (share_1: {bool(share_1_data)}, share_2: {bool(share_2_data)})")
                return None
            
            # Extract shares from response data
            share_1 = share_1_data.get("share_1")
            share_2 = share_2_data.get("share_2")
            
            if not share_1 or not share_2:
                logger.error(f"Invalid share data for secret '{secret_name}' (share_1: {bool(share_1)}, share_2: {bool(share_2)})")
                return None
            
            # Reassemble secret using Shamir's Secret Sharing
            try:
                logger.debug(f"Combining shares for secret '{secret_name}'")
                combined_bytes = shamir.combine_shares([share_1, share_2])
                secret_value = combined_bytes.decode('utf-8')
                
                logger.info(f"Successfully reassembled secret '{secret_name}' for agent '{agent_id}' (request: {request_id})")
                
                # Return secret for immediate use
                return secret_value
                
            except Exception as e:
                logger.error(f"Failed to combine shares for '{secret_name}': {e}")
                return None
            
        except Exception as e:
            logger.error(f"Error in JIT reassembly for '{secret_name}': {e}")
            return None
        
        finally:
            # Secure memory cleanup
            self._secure_cleanup()
    
    async def _fetch_share_1(
        self, 
        secret_name: str, 
        agent_id: str, 
        request_id: str,
        timestamp: int,
        signature: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch share_1 from control plane with authentication.
        
        Args:
            secret_name: Name of the secret
            agent_id: Requesting agent ID
            request_id: Unique request identifier
            timestamp: Request timestamp
            signature: Request signature for authentication
            
        Returns:
            Dictionary containing share_1 and metadata, or None if failed
        """
        try:
            url = f"{self.control_plane_url}/api/v1/internal/secrets/{secret_name}/share"
            headers = {
                "X-Internal-API-Token": self.internal_api_token,
                "X-Request-Signature": signature,
                "X-Timestamp": str(timestamp),
                "Content-Type": "application/json"
            }
            params = {
                "agent_id": agent_id,
                "request_id": request_id
            }
            
            logger.debug(f"Fetching share_1 for '{secret_name}' from control plane")
            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Successfully fetched share_1 for '{secret_name}'")
            return data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Secret '{secret_name}' not found in control plane")
            elif e.response.status_code == 403:
                logger.warning(f"Agent '{agent_id}' not authorized for secret '{secret_name}'")
            elif e.response.status_code == 401:
                logger.error(f"Authentication failed for control plane request")
            else:
                logger.error(f"HTTP error fetching share_1: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching share_1 for '{secret_name}' from control plane")
            return None
        except Exception as e:
            logger.error(f"Error fetching share_1 for '{secret_name}': {e}")
            return None
    
    async def _fetch_share_2(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch share_2 from local storage.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Dictionary containing share_2 and metadata, or None if not found
        """
        try:
            logger.debug(f"Fetching share_2 for '{secret_name}' from local storage")
            share_data = await self.share_storage.retrieve_share(secret_name)
            
            if share_data:
                logger.debug(f"Successfully fetched share_2 for '{secret_name}'")
            else:
                logger.warning(f"No share_2 found in local storage for '{secret_name}'")
            
            return share_data
            
        except Exception as e:
            logger.error(f"Error fetching share_2 for '{secret_name}': {e}")
            return None
    
    def _generate_request_signature(
        self, 
        secret_name: str, 
        agent_id: str, 
        request_id: str,
        timestamp: int
    ) -> str:
        """
        Generate HMAC signature for request authentication.
        
        Args:
            secret_name: Name of the secret
            agent_id: Requesting agent ID
            request_id: Unique request identifier
            timestamp: Request timestamp
            
        Returns:
            HMAC-SHA256 signature as hex string
        """
        message = f"{secret_name}:{agent_id}:{request_id}:{timestamp}"
        signature = hmac.new(
            self.internal_api_token.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _secure_cleanup(self):
        """
        Perform secure memory cleanup.
        
        Note: This attempts to clean up sensitive variables from memory.
        The effectiveness depends on the Python implementation and garbage collector.
        """
        try:
            # Force garbage collection to clean up sensitive variables
            gc.collect()
            
            # Note: In a production environment, you might want to use
            # more sophisticated memory protection techniques like:
            # - Memory locking (mlock/mlock2)
            # - Explicit memory zeroing
            # - Secure allocators
            
            logger.debug("Performed secure memory cleanup after secret reassembly")
        except Exception as e:
            logger.warning(f"Error during secure cleanup: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the JIT reassembly engine.
        
        Returns:
            Dictionary containing health status information
        """
        try:
            # Test control plane connectivity
            start_time = time.time()
            url = f"{self.control_plane_url}/health"
            
            try:
                response = await self.http_client.get(url, timeout=5.0)
                control_plane_healthy = response.status_code == 200
                control_plane_latency = (time.time() - start_time) * 1000
            except Exception:
                control_plane_healthy = False
                control_plane_latency = None
            
            # Test share storage
            storage_health = await self.share_storage.health_check()
            
            return {
                "status": "healthy" if control_plane_healthy and storage_health.get("status") == "healthy" else "unhealthy",
                "control_plane": {
                    "healthy": control_plane_healthy,
                    "latency_ms": round(control_plane_latency, 2) if control_plane_latency else None,
                    "url": self.control_plane_url
                },
                "share_storage": storage_health,
                "jit_engine": {
                    "version": "1.0.0",
                    "library": "sslib (Shamir's Secret Sharing)"
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def close(self):
        """Close HTTP client connections."""
        try:
            await self.http_client.aclose()
            logger.info("Closed JIT reassembly engine HTTP client")
        except Exception as e:
            logger.error(f"Error closing HTTP client: {e}")

class SecretReassemblyError(Exception):
    """Custom exception for secret reassembly errors."""
    
    def __init__(self, message: str, secret_name: str, agent_id: str, error_code: Optional[str] = None):
        self.secret_name = secret_name
        self.agent_id = agent_id
        self.error_code = error_code
        super().__init__(message)

class ShareRetrievalError(SecretReassemblyError):
    """Exception for share retrieval failures."""
    pass

class ShareCombinationError(SecretReassemblyError):
    """Exception for share combination failures."""
    pass 