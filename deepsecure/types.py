# deepsecure/types.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Secret:
    """
    Represents the result of a successful, proxied API call for a secret.

    The actual response body from the downstream service is stored in a private 
    attribute (`_response_body`) and is not displayed in the default 
    representation of the object to prevent accidental logging of sensitive data.
    """
    name: str
    _response_body: str = field(repr=False)

    @property
    def value(self) -> str:
        """The response body from the downstream service call."""
        return self._response_body

    def __str__(self) -> str:
        return f"Secret(name='{self.name}', value='(response body held securely)')" 