"""
Macaroon-based Delegation System for DeepSecure

This module implements cryptographically secure agent-to-agent delegation using
macaroons (Google Research NDSS 2014) with contextual caveats for fine-grained
access control.

Key Features:
- HMAC-SHA256 cryptographic signatures
- Contextual caveats (time, resource, action, agent restrictions)
- Delegation chain tracking with attenuation
- JWT integration for stateless enforcement
- Production-ready performance and security
"""

import time
import secrets
import hmac
import hashlib
import base64
import json
import uuid
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

class CaveatType(Enum):
    """Types of contextual restrictions that can be applied to macaroons."""
    TIME_BEFORE = 'time_before'           # Must be used before timestamp
    TIME_AFTER = 'time_after'             # Must be used after timestamp  
    RESOURCE_PREFIX = 'resource_prefix'   # Resource URL must start with value
    ACTION_LIMIT = 'action_limit'         # Actions limited to comma-separated list
    AGENT_ID = 'agent_id'                 # Must be used by specific agent
    IP_ADDRESS = 'ip_address'             # Must originate from specific IP
    REQUEST_COUNT = 'request_count'       # Limited number of uses
    DELEGATION_DEPTH = 'delegation_depth' # Maximum delegation chain depth

@dataclass
class Caveat:
    """A contextual restriction applied to a macaroon."""
    caveat_type: CaveatType
    value: str
    
    def to_string(self) -> str:
        """Serialize caveat to string format for signature computation."""
        return f'{self.caveat_type.value}:{self.value}'
    
    @classmethod
    def from_string(cls, caveat_str: str) -> 'Caveat':
        """Deserialize caveat from string format."""
        try:
            caveat_type_str, value = caveat_str.split(':', 1)
            caveat_type = CaveatType(caveat_type_str)
            return cls(caveat_type, value)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid caveat format: {caveat_str}") from e

@dataclass
class MacaroonLocation:
    """Identifies the service and endpoint for a macaroon."""
    service: str
    endpoint: Optional[str] = None
    
    def to_string(self) -> str:
        """Serialize location to string format."""
        if self.endpoint:
            return f'{self.service}:{self.endpoint}'
        return self.service

    @classmethod
    def from_string(cls, location_str: str) -> 'MacaroonLocation':
        """Deserialize location from string format."""
        parts = location_str.split(':', 1)
        if len(parts) == 2:
            return cls(parts[0], parts[1])
        return cls(parts[0])

class Macaroon:
    """
    A macaroon credential with cryptographic integrity and contextual caveats.
    
    Based on Google Research: "Macaroons: Cookies with Contextual Caveats for 
    Decentralized Authorization in the Cloud" (NDSS 2014).
    """
    
    def __init__(self, location: MacaroonLocation, identifier: str, key: bytes):
        self.location = location
        self.identifier = identifier
        self.key = key
        self.caveats: List[Caveat] = []
        self.signature = self._compute_signature()
        self.parent_signature: Optional[str] = None
        self.creation_time = time.time()
        
    def _compute_signature(self) -> str:
        """Compute HMAC-SHA256 signature over macaroon contents."""
        # Construct the data to be signed: location + identifier + caveats
        data = f'{self.location.to_string()}:{self.identifier}'
        for caveat in self.caveats:
            data += f':{caveat.to_string()}'
        
        # Compute HMAC-SHA256 signature
        signature = hmac.new(
            self.key,
            data.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def add_caveat(self, caveat: Caveat) -> 'Macaroon':
        """
        Add a caveat (restriction) to the macaroon, returning a new attenuated macaroon.
        
        This implements the macaroon attenuation principle: each caveat can only
        add restrictions, never remove them. This ensures monotonic privilege reduction.
        """
        # Create new macaroon with same location, identifier, and key
        new_macaroon = Macaroon(self.location, self.identifier, self.key)
        
        # Copy existing caveats
        new_macaroon.caveats = self.caveats.copy()
        
        # Add the new caveat
        new_macaroon.caveats.append(caveat)
        
        # Recompute signature with new caveat
        new_macaroon.signature = new_macaroon._compute_signature()
        new_macaroon.parent_signature = self.signature
        new_macaroon.creation_time = self.creation_time
        
        logger.debug(f"Added caveat {caveat.to_string()} to macaroon {self.identifier}")
        
        return new_macaroon
    
    def verify(self, key: bytes, request_context: Dict[str, Any]) -> bool:
        """
        Verify the macaroon's cryptographic signature and all contextual caveats.
        
        Args:
            key: The root key used to verify the signature
            request_context: Context information for caveat verification
            
        Returns:
            True if the macaroon is valid and all caveats pass, False otherwise
        """
        try:
            # 1. Verify cryptographic signature
            expected_signature = self._compute_signature_with_key(key)
            if not hmac.compare_digest(expected_signature, self.signature):
                logger.warning(f"Signature verification failed for macaroon {self.identifier}")
                return False
            
            # 2. Verify all caveats against request context
            for caveat in self.caveats:
                if not self._verify_caveat(caveat, request_context):
                    logger.warning(f"Caveat verification failed: {caveat.to_string()}")
                    return False
            
            logger.debug(f"Macaroon {self.identifier} verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying macaroon {self.identifier}: {e}")
            return False
    
    def _compute_signature_with_key(self, key: bytes) -> str:
        """Compute signature using a specific key (for verification)."""
        data = f'{self.location.to_string()}:{self.identifier}'
        for caveat in self.caveats:
            data += f':{caveat.to_string()}'
        
        signature = hmac.new(
            key,
            data.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _verify_caveat(self, caveat: Caveat, context: Dict[str, Any]) -> bool:
        """Verify a single caveat against the request context."""
        try:
            if caveat.caveat_type == CaveatType.TIME_BEFORE:
                return time.time() < float(caveat.value)
            elif caveat.caveat_type == CaveatType.TIME_AFTER:
                return time.time() > float(caveat.value)
            elif caveat.caveat_type == CaveatType.RESOURCE_PREFIX:
                resource = context.get('resource', '')
                return resource.startswith(caveat.value)
            elif caveat.caveat_type == CaveatType.ACTION_LIMIT:
                allowed_actions = caveat.value.split(',')
                requested_action = context.get('action', '')
                return requested_action in allowed_actions
            elif caveat.caveat_type == CaveatType.AGENT_ID:
                return context.get('agent_id') == caveat.value
            elif caveat.caveat_type == CaveatType.IP_ADDRESS:
                return context.get('ip_address') == caveat.value
            elif caveat.caveat_type == CaveatType.REQUEST_COUNT:
                # In production, this would check against stored usage counts
                current_count = int(context.get('request_count', 0))
                max_count = int(caveat.value)
                return current_count <= max_count
            elif caveat.caveat_type == CaveatType.DELEGATION_DEPTH:
                current_depth = int(context.get('delegation_depth', 0))
                max_depth = int(caveat.value)
                return current_depth <= max_depth
            
            # Unknown caveat type - fail closed
            logger.warning(f"Unknown caveat type: {caveat.caveat_type}")
            return False
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error verifying caveat {caveat.to_string()}: {e}")
            return False
    
    def serialize(self) -> str:
        """Serialize macaroon to base64-encoded JSON for transport."""
        data = {
            'location': self.location.to_string(),
            'identifier': self.identifier,
            'caveats': [caveat.to_string() for caveat in self.caveats],
            'signature': self.signature,
            'parent_signature': self.parent_signature,
            'creation_time': self.creation_time
        }
        
        json_str = json.dumps(data, separators=(',', ':'))
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    @classmethod
    def deserialize(cls, serialized: str, key: bytes) -> 'Macaroon':
        """Deserialize macaroon from base64-encoded JSON."""
        try:
            json_str = base64.b64decode(serialized).decode('utf-8')
            data = json.loads(json_str)
            
            # Reconstruct macaroon
            location = MacaroonLocation.from_string(data['location'])
            macaroon = cls(location, data['identifier'], key)
            
            # Restore caveats
            macaroon.caveats = [Caveat.from_string(caveat_str) for caveat_str in data['caveats']]
            
            # Restore metadata
            macaroon.signature = data['signature']
            macaroon.parent_signature = data.get('parent_signature')
            macaroon.creation_time = data.get('creation_time', time.time())
            
            # Verify signature matches
            expected_signature = macaroon._compute_signature()
            if not hmac.compare_digest(expected_signature, macaroon.signature):
                raise ValueError("Invalid macaroon signature")
            
            return macaroon
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid macaroon format: {e}") from e

class DelegationManager:
    """
    Manages macaroon-based delegation chains with cryptographic security.
    
    Provides high-level delegation operations including:
    - Root macaroon creation
    - Agent-to-agent delegation with attenuation
    - Delegation chain verification
    - JWT integration for stateless enforcement
    """
    
    def __init__(self, root_key: Optional[bytes] = None):
        self.root_key = root_key or secrets.token_bytes(32)
        self.macaroons: Dict[str, Macaroon] = {}
        self.delegation_chains: Dict[str, List[str]] = {}
        
        logger.info("DelegationManager initialized with 256-bit root key")
    
    def create_root_macaroon(self, agent_id: str, location: MacaroonLocation,
                           initial_caveats: Optional[List[Caveat]] = None) -> Macaroon:
        """
        Create a root macaroon for an agent with full permissions.
        
        Args:
            agent_id: The agent ID to bind the macaroon to
            location: Service location for the macaroon
            initial_caveats: Optional initial restrictions to apply
            
        Returns:
            A root macaroon with agent binding and any initial caveats
        """
        # Generate unique identifier for the macaroon
        identifier = f'agent:{agent_id}:{uuid.uuid4()}'
        
        # Create base macaroon
        macaroon = Macaroon(location, identifier, self.root_key)
        
        # Add agent ID binding caveat (required for all macaroons)
        agent_caveat = Caveat(CaveatType.AGENT_ID, agent_id)
        macaroon = macaroon.add_caveat(agent_caveat)
        
        # Add any initial caveats
        if initial_caveats:
            for caveat in initial_caveats:
                macaroon = macaroon.add_caveat(caveat)
        
        # Store macaroon and initialize delegation chain
        self.macaroons[identifier] = macaroon
        self.delegation_chains[identifier] = [identifier]
        
        logger.info(f"Created root macaroon for agent {agent_id}: {identifier}")
        return macaroon
    
    def delegate_macaroon(self, parent_macaroon: Macaroon, target_agent_id: str,
                         additional_caveats: List[Caveat]) -> Macaroon:
        """
        Create a delegated macaroon with additional restrictions (attenuation).
        
        This implements the core macaroon delegation principle: delegation can only
        add restrictions, never remove them. This ensures least-privilege delegation.
        
        Args:
            parent_macaroon: The macaroon being delegated
            target_agent_id: The agent receiving the delegation
            additional_caveats: Additional restrictions to impose
            
        Returns:
            A new delegated macaroon with combined restrictions
        """
        # Generate unique identifier for delegated macaroon
        identifier = f'delegated:{target_agent_id}:{uuid.uuid4()}'
        
        # Create new macaroon with same location and root key
        delegated_macaroon = Macaroon(parent_macaroon.location, identifier, self.root_key)
        
        # Copy parent caveats (except agent_id which gets replaced)
        for caveat in parent_macaroon.caveats:
            if caveat.caveat_type != CaveatType.AGENT_ID:
                delegated_macaroon = delegated_macaroon.add_caveat(caveat)
        
        # Add target agent ID caveat (replaces parent's agent_id)
        agent_caveat = Caveat(CaveatType.AGENT_ID, target_agent_id)
        delegated_macaroon = delegated_macaroon.add_caveat(agent_caveat)
        
        # Add delegation depth tracking
        parent_depth = self._get_delegation_depth(parent_macaroon)
        depth_caveat = Caveat(CaveatType.DELEGATION_DEPTH, str(parent_depth + 1))
        delegated_macaroon = delegated_macaroon.add_caveat(depth_caveat)
        
        # Add additional restrictions (attenuation)
        for caveat in additional_caveats:
            delegated_macaroon = delegated_macaroon.add_caveat(caveat)
        
        # Store macaroon and update delegation chain
        self.macaroons[identifier] = delegated_macaroon
        parent_chain = self.delegation_chains.get(parent_macaroon.identifier, [parent_macaroon.identifier])
        self.delegation_chains[identifier] = parent_chain + [identifier]
        
        logger.info(f"Delegated macaroon from {parent_macaroon.identifier} to agent {target_agent_id}: {identifier}")
        return delegated_macaroon
    
    def _get_delegation_depth(self, macaroon: Macaroon) -> int:
        """Get the current delegation depth of a macaroon."""
        for caveat in macaroon.caveats:
            if caveat.caveat_type == CaveatType.DELEGATION_DEPTH:
                return int(caveat.value)
        return 0  # Root macaroon has depth 0
    
    def verify_macaroon(self, macaroon: Macaroon, request_context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verify a macaroon's validity and contextual caveats.
        
        Args:
            macaroon: The macaroon to verify
            request_context: Context for caveat verification
            
        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            if macaroon.verify(self.root_key, request_context):
                return True, 'Macaroon verified successfully'
            else:
                return False, 'Caveat verification failed'
        except Exception as e:
            return False, f'Verification error: {str(e)}'
    
    def get_delegation_chain(self, macaroon_id: str) -> List[str]:
        """Get the complete delegation chain for a macaroon."""
        return self.delegation_chains.get(macaroon_id, [])
    
    def macaroon_to_jwt_claims(self, macaroon: Macaroon) -> Dict[str, Any]:
        """
        Convert a macaroon to JWT claims for stateless enforcement.
        
        This enables macaroons to be embedded in JWT tokens for gateway enforcement
        without requiring the gateway to store any state.
        """
        # Extract agent ID from caveats
        agent_id = None
        for caveat in macaroon.caveats:
            if caveat.caveat_type == CaveatType.AGENT_ID:
                agent_id = caveat.value
                break
        
        claims = {
            'sub': agent_id,
            'macaroon_id': macaroon.identifier,
            'macaroon_location': macaroon.location.to_string(),
            'caveats': [caveat.to_string() for caveat in macaroon.caveats],
            'delegation_chain': self.get_delegation_chain(macaroon.identifier),
            'macaroon_signature': macaroon.signature,
            'parent_signature': macaroon.parent_signature,
            'macaroon_created': macaroon.creation_time,
            'iat': int(time.time()),
        }
        
        # Add expiration from time_before caveat if present
        for caveat in macaroon.caveats:
            if caveat.caveat_type == CaveatType.TIME_BEFORE:
                claims['exp'] = int(float(caveat.value))
                break
        
        return claims
    
    def jwt_claims_to_macaroon(self, claims: Dict[str, Any]) -> Macaroon:
        """
        Reconstruct a macaroon from JWT claims for verification.
        
        This enables stateless macaroon verification at the gateway by reconstructing
        the macaroon from JWT token claims.
        """
        # Reconstruct location
        location = MacaroonLocation.from_string(claims['macaroon_location'])
        
        # Create macaroon with identifier and root key
        macaroon = Macaroon(location, claims['macaroon_id'], self.root_key)
        
        # Restore caveats
        macaroon.caveats = [Caveat.from_string(caveat_str) for caveat_str in claims['caveats']]
        
        # Restore metadata
        macaroon.signature = claims['macaroon_signature']
        macaroon.parent_signature = claims.get('parent_signature')
        macaroon.creation_time = claims.get('macaroon_created', time.time())
        
        # Restore delegation chain
        if claims['macaroon_id'] not in self.delegation_chains:
            self.delegation_chains[claims['macaroon_id']] = claims['delegation_chain']
        
        return macaroon

# Global delegation manager instance
delegation_manager = DelegationManager() 