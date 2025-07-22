import random
import string

def random_lower_string(length: int = 8) -> str:
    """Generate a random lowercase string of specified length."""
    return ''.join(random.choices(string.ascii_lowercase, k=length)) 