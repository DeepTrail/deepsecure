# deepsecure/types.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Secret:
    """
    A secure container for a fetched secret value and its metadata.

    The actual secret value is stored in a private attribute (`_value`)
    and is not displayed in the default representation of the object to
    prevent accidental logging or printing.
    """
    name: str
    expires_at: datetime
    _value: str = field(repr=False)

    @property
    def value(self) -> str:
        """The actual secret value."""
        return self._value

    def __str__(self) -> str:
        return f"Secret(name='{self.name}', expires_at='{self.expires_at.isoformat()}', value='**********')" 