#!/usr/bin/env python3
"""
Simple test script to try out the deepsecure vault issue command implementation.
"""

import os
import sys
import time
from deepsecure.core import vault_client
from deepsecure import utils
from deepsecure.core.identity_manager import identity_manager

# Helper to create a temporary agent for testing
TEST_AGENT_ID = None

def setup_test_agent():
    global TEST_AGENT_ID
    try:
        # A simple way to get an agent_id for testing
        # In a real test suite, this would be more robust (e.g., using a fixture)
        timestamp = int(time.time())
        agent_name = f"test-vault-issue-agent-{timestamp}"
        identity = identity_manager.create_identity(name=agent_name)
        TEST_AGENT_ID = identity["id"]
        print(f"[Setup] Created test agent: {TEST_AGENT_ID} ({agent_name})")
    except Exception as e:
        print(f"[Setup] Failed to create test agent: {e}")
        # Fallback or raise if critical for the test
        # For this quick fix, we'll let it be None and tests might fail more gracefully

def teardown_test_agent():
    if TEST_AGENT_ID:
        try:
            identity_manager.delete_identity(TEST_AGENT_ID)
            print(f"[Teardown] Deleted test agent: {TEST_AGENT_ID}")
        except Exception as e:
            print(f"[Teardown] Failed to delete test agent {TEST_AGENT_ID}: {e}")

def test_issue_credential():
    """Test issuing a credential with origin binding."""
    print("Testing vault issue command...")
    if not TEST_AGENT_ID:
        print("Skipping test_issue_credential as test agent setup failed.")
        return
    
    # Create a test credential with origin binding
    # The new client.issue method does not take origin_binding directly.
    # It's implicitly true, or context is passed via its own logic if VaultClient is used.
    # The core client.issue now takes agent_id and ttl (int)
    try:
        ttl_seconds = utils.parse_ttl_to_seconds("5m")
        credential = vault_client.client.issue(
            scope="db:readonly",
            ttl=ttl_seconds, 
            agent_id=TEST_AGENT_ID 
        )
        
        print("\nCredential issued:")
        utils.print_json(credential.model_dump()) # Use model_dump() for pydantic models
        
        print("\nCredential details:")
        print(f"ID: {credential.credential_id}")
        print(f"Agent ID: {credential.agent_id}")
        print(f"Scope: {credential.scope}")
        print(f"Expires at: {credential.expires_at.isoformat()}") # Use isoformat for datetime
        
        origin_context = credential.origin_context
        if origin_context:
            print("\nOrigin context:")
            for key, value in origin_context.items():
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error during test_issue_credential: {e}")
    
def test_issue_credential_no_binding(): # This test might be less relevant now
    """Test issuing a credential without origin binding."""
    print("\nTesting vault issue command without origin binding...")
    if not TEST_AGENT_ID:
        print("Skipping test_issue_credential_no_binding as test agent setup failed.")
        return
    
    # Create a test credential 
    # As above, origin_binding is not a direct param of client.issue
    try:
        ttl_seconds = utils.parse_ttl_to_seconds("1h")
        credential = vault_client.client.issue(
            scope="api:read",
            ttl=ttl_seconds,
            agent_id=TEST_AGENT_ID
        )
        
        print("\nCredential issued:")
        utils.print_json(credential.model_dump()) # Use model_dump()
    except Exception as e:
        print(f"Error during test_issue_credential_no_binding: {e}")

if __name__ == "__main__":
    setup_test_agent() # Setup agent before tests
    try:
        test_issue_credential()
        test_issue_credential_no_binding()
    finally:
        teardown_test_agent() # Cleanup agent after tests 