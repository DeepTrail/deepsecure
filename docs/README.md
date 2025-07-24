# DeepSecure Python SDK

Welcome to the DeepSecure Python SDK documentation! This SDK provides a developer-friendly way to secure your AI agents with minimal effort, so you can focus on building amazing agent capabilities.

## Why Use the DeepSecure SDK?

The DeepSecure SDK is designed specifically for **AI agent developers** who need:

- 🔐 **Secure credential management** without hardcoded API keys
- 🤖 **Agent identity management** with automatic key generation and storage
- ⚡ **Just-in-time credential issuance** with configurable TTL
- 🔧 **Framework integration** with LangChain, CrewAI, and other agentic frameworks
- 📊 **Audit trails** for all agent actions and credential usage
- 🚀 **Production-ready security** from day one

### SDK vs CLI: When to Use What?

- **Use the SDK** when building AI agents that need programmatic access to secrets
- **Use the CLI** for administrative tasks, setup, and manual credential management
- **Use both together** for a complete development and deployment workflow

## Getting Started

### Prerequisites

- Python 3.9 or higher
- A running DeepSecure Control Plane backend

### Installation

Install the DeepSecure package:

```bash
pip install deepsecure
```

### Backend Services Setup

You'll need the DeepSecure backend services (Control Plane and Gateway) running to use the SDK. For complete, step-by-step instructions on how to run the services locally, please see our comprehensive:

➡️ **[Backend Services Setup Guide](./backend-services-setup.md)**

## Quick Start Guide

Here's how to get started with the SDK in just a few lines of code:

### 1. Initialize the Client

```python
import deepsecure

# Initialize the client - it automatically picks up your environment configuration
client = deepsecure.Client()
```

### 2. Create an Agent Identity

```python
# Create or get an agent identity
# This handles key generation, registration, and secure local storage
agent_handle = client.agent("my-ai-agent", auto_create=True)
print(f"Agent ready: {agent_handle.agent_id}")
```

### 3. Store a Secret

```python
# Store a secret in the vault (typically done once during setup)
client.vault.store_secret("openai_api_key", "sk-your-openai-key-here")
```

### 4. Fetch Secrets Securely

```python
# Your agent can now fetch secrets just-in-time
secret = client.get_secret("openai_api_key")
print(f"Secret retrieved: {secret.name}")
print(f"Expires at: {secret.expires_at}")

# Use the secret value (never logged or exposed)
api_key = secret.value
```

### Complete Example

```python
import deepsecure
from openai import OpenAI

def main():
    # 1. Initialize the DeepSecure client
    client = deepsecure.Client()
    
    # 2. Ensure agent identity exists
    agent = client.agent("openai-assistant", auto_create=True)
    
    # 3. Fetch API key securely
    secret = client.get_secret("openai_api_key")
    
    # 4. Use the secret with your AI service
    openai_client = OpenAI(api_key=secret.value)
    
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello, secure world!"}]
    )
    
    print(response.choices[0].message.content)

if __name__ == "__main__":
    main()
```

## Framework Integration Examples

### LangChain Integration

```python
import deepsecure
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# Initialize DeepSecure client
client = deepsecure.Client()

def create_secure_chat_tool(client: deepsecure.Client):
    """Factory function for creating secure LangChain tools."""
    
    @tool
    def secure_chat(query: str) -> str:
        """A secure chat tool that fetches API keys just-in-time."""
        # Fetch the API key securely
        secret = client.get_secret("openai_api_key")
        
        # Create the LangChain client
        chat = ChatOpenAI(api_key=secret.value, model="gpt-3.5-turbo")
        
        # Use it
        response = chat.invoke(query)
        return response.content
    
    return secure_chat

# Create and use the secure tool
secure_tool = create_secure_chat_tool(client)
result = secure_tool.invoke("What is the weather like?")
```

### CrewAI Integration

```python
import deepsecure
from crewai import Agent, Task, Crew

# Initialize DeepSecure with agent-specific contexts
client = deepsecure.Client()

# Create tools with agent-specific permissions
def create_research_tools(agent_client):
    """Create research tools for a specific agent."""
    # This agent can only access research-related secrets
    tavily_secret = agent_client.get_secret("tavily_api_key")
    # ... create tools using tavily_secret.value
    return [research_tool]

def create_writing_tools(agent_client):
    """Create writing tools for a specific agent."""
    # This agent can only access writing-related secrets  
    notion_secret = agent_client.get_secret("notion_api_key")
    # ... create tools using notion_secret.value
    return [writing_tool]

# Create agents with scoped access
researcher = Agent(
    role='Researcher',
    tools=create_research_tools(client.with_agent("researcher")),
    backstory="You research topics thoroughly..."
)

writer = Agent(
    role='Writer', 
    tools=create_writing_tools(client.with_agent("writer")),
    backstory="You write engaging content..."
)

# Create and run the crew
crew = Crew(agents=[researcher, writer], tasks=[...])
result = crew.kickoff()
```

## Configuration

The SDK automatically reads configuration from:

1. **Environment variables** (recommended for production):
   ```bash
   export DEEPSECURE_CONTROL_PLANE_URL="http://localhost:8000"
   export DEEPSECURE_API_TOKEN="your-token"
   ```

2. **Configuration file** (good for development):
   ```bash
   # Set up using the CLI
   deepsecure configure
   ```

3. **Direct initialization** (for testing):
   ```python
   client = deepsecure.Client(
       backend_url="http://localhost:8000",
       api_token="your-token"
   )
   ```

## API Reference

### Core Classes

- **`deepsecure.Client`** - Main entry point for the SDK
- **`client.agent(name, auto_create=False)`** - Get or create agent identity
- **`client.get_secret(name)`** - Fetch a secret securely
- **`client.vault`** - Direct vault operations

### Key Methods

```python
# Client initialization
client = deepsecure.Client()
client = deepsecure.Client(backend_url="...", api_token="...")

# Agent management
agent = client.agent("agent-name", auto_create=True)
agent_list = client.list_agents()

# Secret operations
secret = client.get_secret("secret-name")
client.vault.store_secret("name", "value")
client.vault.list_secrets()

# Agent-specific contexts (for multi-agent systems)
scoped_client = client.with_agent("specific-agent-name")
```

## Best Practices

### Security
- ✅ Never log or print `secret.value` 
- ✅ Use `auto_create=True` for development, explicit registration for production
- ✅ Set appropriate TTL values for credentials
- ✅ Use agent-specific contexts in multi-agent systems

### Performance
- ✅ Reuse the `Client` instance across your application
- ✅ Cache secrets appropriately (respecting TTL)
- ✅ Use connection pooling for high-throughput scenarios

### Development
- ✅ Use environment variables for configuration
- ✅ Test with mock secrets in development
- ✅ Implement proper error handling for network issues

## Troubleshooting

### Common Issues

**"Backend URL env var DEEPSECURE_CONTROL_PLANE_URL is not set"**
```bash
# Solution: Set the environment variable
export DEEPSECURE_CONTROL_PLANE_URL="http://localhost:8000"
```

**"Agent not found" errors**
```python
# Solution: Use auto_create or register the agent first
agent = client.agent("my-agent", auto_create=True)
```

**"Secret not found" errors**
```bash
# Solution: Store the secret first using the CLI or vault API
deepsecure vault store my_secret --value "secret-value"
```

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = deepsecure.Client()
# Now you'll see detailed API calls and responses
```

## Examples Repository

For more comprehensive examples, check out our [examples directory](../examples/):

- `01_create_agent_and_issue_credential.py` - Basic agent setup
- `02_sdk_secret_fetch.py` - Simple secret fetching
- `03_crewai_secure_tools.py` - CrewAI integration
- `04_multi_agent_communication.py` - Agent-to-agent communication  
- `05_langchain_secure_tools.py` - LangChain integration

## Next Steps

- 📖 **[CLI Reference](./cli_reference.md)** - Learn about administrative commands
- 🔧 **[Backend Setup Guide](./backend-services-setup.md)** - Detailed backend configuration
- 🏗️ **[Contributing Guide](../CONTRIBUTING.md)** - Help improve DeepSecure
- 💬 **[GitHub Discussions](https://github.com/your-repo/discussions)** - Get help from the community

---

**Questions?** Open an issue on [GitHub](https://github.com/your-repo/issues) or start a discussion in our [community forum](https://github.com/your-repo/discussions). 