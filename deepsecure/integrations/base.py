# deepsecure/integrations/base.py

class DeepSecureIntegrationError(Exception):
    """Base exception for DeepSecure integration issues."""
    pass

class BaseIntegration:
    """Base class for DeepSecure framework integrations."""

    def __init__(self, vault_client, agent_client, **kwargs):
        self.vault_client = vault_client
        self.agent_client = agent_client
        self.config = kwargs

    def initialize(self):
        """Initialize the integration with the specific framework."""
        raise NotImplementedError("Subclasses must implement this method.")

    def get_tool_description(self) -> str:
        """Return a description of the tools or capabilities provided by this integration."""
        return "No specific tool description provided for this integration."

    # Other common methods can be added here 