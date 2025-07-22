import random
import string
import uuid

def random_lower_string(length: int = 8) -> str:
    """Generate a random lowercase string of specified length."""
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def random_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4()) 