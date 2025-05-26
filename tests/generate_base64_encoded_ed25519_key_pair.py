import base64
from cryptography.hazmat.primitives.asymmetric import ed25519

private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()
ephemeral_private_key_b64 = base64.b64encode(private_key.private_bytes_raw()).decode('utf-8')
ephemeral_public_key_b64 = base64.b64encode(public_key.public_bytes_raw()).decode('utf-8')
print(f"Ephemeral Public Key (Base64): {ephemeral_public_key_b64}")
print(f"Ephemeral Private Key (Base64): {ephemeral_private_key_b64}")
