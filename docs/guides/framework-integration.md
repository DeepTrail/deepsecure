# Secure Integration Patterns for AI Agent Frameworks

This guide outlines the recommended pattern for securely integrating the DeepSecure SDK with popular AI agentic frameworks like CrewAI, LangChain, and others. The core principle is **Dependency Injection** using a "Tool Factory" pattern.

## The Challenge: Providing Secure Tools to Agents

When building systems with multiple agents (like a research agent and a writer agent), a key security challenge is ensuring each agent only has access to the credentials it needs. For example, the researcher needs the Tavily API key, but should not have access to the Notion key, and vice-versa for the writer.

A naive approach would be to have the main script load all secrets and pass them to the correct tools, but this breaks encapsulation and makes the system harder to maintain and secure.

## The Solution: The "Tool Factory" Pattern

The "Tool Factory" pattern provides a clean, secure, and scalable solution. It works like this:

1.  **Tool Factories**: Instead of creating tools directly, you write functions that *create* tools. These functions (factories) take a configured `deepsecure.Client` instance as an argument.
2.  **Dependency Injection**: The factory *injects* the client into the tool it creates. The tool then uses this client to fetch its required secrets just-in-time.
3.  **Agent-Specific Clients**: You use the `client.with_agent("agent-name")` method to create temporary, agent-scoped clients. When you pass one of these scoped clients to a tool factory, the resulting tool can *only* act on behalf of that specific agent.

This enforces the **Principle of Least Privilege** at an architectural level.

### Example: A Secure CrewAI Implementation

Let's look at how this works in practice with a `researcher` and a `writer` agent in CrewAI. You can find the full, runnable code for this in `examples/03_crewai_secure_tools.py`.

#### Step 1: Define Tool Factories

First, we create factories for our tools. Each factory accepts a `client` object.

```python
# tools.py
import deepsecure
from langchain_community.tools import tool

def create_tavily_search_tool(client: deepsecure.Client):
    """Factory to create a secure Tavily search tool."""

    @tool("Tavily Search Tool")
    def tavily_search_tool(query: str) -> str:
        """This tool uses the provided client to fetch its API key."""
        # This client is pre-scoped to a specific agent.
        tavily_key = client.get_secret("tavily-api-key").value
        
        # ... use the key to perform the search ...
        return f"Results for {query}..."

    return tavily_search_tool

def create_notion_tool(client: deepsecure.Client):
    """Factory to create a secure Notion tool."""
    
    @tool("Notion Tool")
    def notion_tool(content: str) -> str:
        """This tool uses the provided client to fetch its API key."""
        notion_key = client.get_secret("notion-api-key").value
        
        # ... use the key to write to Notion ...
        return "Successfully wrote to Notion."
            
    return notion_tool
```

#### Step 2: Set Up Policies

In your terminal, you define which agent can access which secret. This policy is enforced by the backend.

```bash
# The researcher can read the tavily key
deepsecure policy create --agent-name "crew-researcher" --secret-name "tavily-api-key" --action "read"

# The writer can read the notion key
deepsecure policy create --agent-name "crew-writer" --secret-name "notion-api-key" --action "read"
```

#### Step 3: Inject Scoped Clients into Factories

In your main script, you create a master client, then use `.with_agent()` to create scoped clients, and pass those to your factories.

```python
# main_crew.py
import deepsecure
from crewai import Agent as CrewAIAgent
# from tools import create_tavily_search_tool, create_notion_tool

# 1. Initialize a single, master DeepSecure client.
master_client = deepsecure.Client()

# 2. Create agent-specific clients using .with_agent()
researcher_client = master_client.with_agent("crew-researcher", auto_create=True)
writer_client = master_client.with_agent("crew-writer", auto_create=True)

# 3. Create tools by injecting the agent-specific clients.
researcher_tool = create_tavily_search_tool(researcher_client)
writer_tool = create_notion_tool(writer_client)

# 4. Assign the securely scoped tools to the correct agents.
researcher = CrewAIAgent(
    role='Researcher',
    tools=[researcher_tool] # Can ONLY use the researcher's tool
)
writer = CrewAIAgent(
    role='Writer',
    tools=[writer_tool] # Can ONLY use the writer's tool
)
```

### Security Benefits of This Pattern

*   **Least Privilege**: The `researcher` agent literally cannot access the Notion API key. Even if it were accidentally given the `notion_tool`, the call to `client.get_secret("notion-api-key")` inside the tool would fail, because the underlying client is authenticated as the `"crew-researcher"` identity, which is not authorized by the policy for that secret.
*   **Clean Code**: Your orchestration logic (the main script) is not cluttered with secret management. It deals with high-level concepts like clients and tools.
*   **Testability**: The tools are easy to unit test. You can pass a mock `deepsecure.Client` to the factory and verify the tool's behavior without needing a live backend.
*   **Scalability**: This pattern scales cleanly as you add more agents and tools to your system. The security policies and agent-specific contexts ensure that complexity remains manageable. 