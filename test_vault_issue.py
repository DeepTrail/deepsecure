#!/usr/bin/env python3
"""
Simple test script to try out the deepsecure vault issue command implementation.
"""

import os
import sys
from deepsecure.core import vault_client
from deepsecure import utils

def test_issue_credential():
    """Test issuing a credential with origin binding."""
    print("Testing vault issue command...")
    
    # Create a test credential with origin binding
    credential = vault_client.client.issue_credential(
        scope="db:readonly",
        ttl="5m",
        origin_binding=True
    )
    
    print("\nCredential issued:")
    utils.print_json(credential)
    
    print("\nCredential details:")
    print(f"ID: {credential['id']}")
    print(f"Agent ID: {credential['agent_id']}")
    print(f"Scope: {credential['scope']}")
    print(f"Expires at: {utils.format_timestamp(credential['expires_at'])}")
    
    print("\nOrigin context:")
    for key, value in credential.get('origin_context', {}).items():
        print(f"  {key}: {value}")
    
def test_issue_credential_no_binding():
    """Test issuing a credential without origin binding."""
    print("\nTesting vault issue command without origin binding...")
    
    # Create a test credential without origin binding
    credential = vault_client.client.issue_credential(
        scope="api:read",
        ttl="1h",
        origin_binding=False
    )
    
    print("\nCredential issued:")
    utils.print_json(credential)

if __name__ == "__main__":
    test_issue_credential()
    test_issue_credential_no_binding() 