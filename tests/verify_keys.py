# verify_keys.py
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519

# Key data for agent-39fb237e-984b-42dc-b1c2-f8b1218b9009 ("KeyringSigner")
# Private key as loaded by VaultClient (ostensibly from keyring via IdentityManager)
# This value is taken from the `agent_private_key_b64` local variable in your last traceback for VaultClient.issue_credential
#private_key_b64_from_client_debug = "CnibHiyWEIqLm9ABsZbJihDsfp71vBojWAbN5/XY/R0="
private_key_b64_from_client_debug = "aW4e+jupK55BjCYhqAKamwLr81SbtUzX60WViLA7eCs="

# Public key as loaded by VaultClient (from agent_identity dict, sourced from JSON metadata)
# This value is taken from the `loaded_public_key_b64` local variable (or `agent_identity['public_key']`) 
# in your last traceback for VaultClient.issue_credential
public_key_b64_from_client_debug = "eIB60GPaU0fmTgDePcPmFHwvuuqWnrVEAd9opvcZCw4="

print("--- Key Pair Consistency Check ---")
print(f"Private Key (Base64, from client debug): {private_key_b64_from_client_debug}")
print(f"Public Key (Base64, from client debug):  {public_key_b64_from_client_debug}")

try:
    private_key_bytes = base64.b64decode(private_key_b64_from_client_debug)
    
    if len(private_key_bytes) != 32:
        print(f"\nERROR: Decoded private key is {len(private_key_bytes)} bytes, expected 32.")
    else:
        print(f"Decoded private key is {len(private_key_bytes)} bytes (correct length for Ed25519 seed).")
        
        priv_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        derived_public_key_obj = priv_key_obj.public_key()
        derived_public_key_raw_bytes = derived_public_key_obj.public_bytes_raw()
        derived_public_key_b64_from_priv = base64.b64encode(derived_public_key_raw_bytes).decode('utf-8')
        
        print(f"Public Key derived from the private key (Base64): {derived_public_key_b64_from_priv}")
        
        if derived_public_key_b64_from_priv == public_key_b64_from_client_debug:
            print("\n[SUCCESS] Key Pair VALID: The private key correctly derives the public key.")
            print("This means the client IS using a consistent internal key pair.")
            print("If signature verification still fails on the server, the server's registered public key for this agent must be different.")
        else:
            print("\n[ERROR] Key Pair INVALID: The private key DOES NOT derive the public key.")
            print("This means the IdentityManager is providing an inconsistent key pair to the VaultClient.")
            print("  - Private key from keyring might not match the public key in the agent's JSON metadata file.")
            print("  - Or, the agent registration process stored a different public key on the server than what's in the local metadata.")

except Exception as e:
    print(f"\nAn error occurred during key verification script: {type(e).__name__} - {e}") 