# examples/05_langchain_secure_tools.py
"""
This example demonstrates how to build secure, fine-grained tools for LangChain
agents using the DeepSecure SDK.

It showcases the "Tool Factory" and "Dependency Injection" patterns, where each
tool is created with an agent-specific DeepSecure client context. This ensures
that each tool can only access the secrets its designated agent is authorized for,
enforcing the Principle of Least Privilege.

**Scenario:**
- We have two agents: a "researcher" and a "writer".
- The "researcher" needs access to a search tool that uses a Tavily API key.
- The "writer" needs access to a publishing tool that uses a Notion API key.
- We will create policies ensuring the researcher can ONLY access the Tavily key,
  and the writer can ONLY access the Notion key.

**To Run This Example:**
1. Make sure the `credservice` backend is running.
2. Set up the necessary agents and policies using the DeepSecure CLI:
   ```bash
   # Create agent identities
   deepsecure agent register --name researcher
   deepsecure agent register --name writer

   # Store the secrets in the vault
   deepsecure vault store tavily_api_key --value "tvly-your-real-or-dummy-key"
   deepsecure vault store notion_api_key --value "secret_your-real-or-dummy-key"

   # Create fine-grained access policies
   deepsecure policy create --agent-name researcher --secret-name tavily_api_key --action read
   deepsecure policy create --agent-name writer --secret-name notion_api_key --action read
   ```
3. Install langchain-community:
    ```bash
    pip install langchain-community
    ```
"""
import deepsecure
from deepsecure.client import Client
from deepsecure.exceptions import DeepSecureClientError
from langchain_community.tools import tool

# --- Tool Factory Definition ---

def create_secure_search_tool(client: Client):
    """
    This is a "Tool Factory". It takes a DeepSecure client and returns a
    configured, secure LangChain tool.
    """
    @tool
    def tavily_search(query: str) -> str:
        """A secure tool that uses the provided DeepSecure client to fetch its API key."""
        print(f"Attempting to use the search tool with agent: '{client._agent_context.name}'")
        try:
            # The tool explicitly uses the injected client to get the secret.
            # No magic, just clear, testable code.
            api_key_secret = client.get_secret("tavily_api_key")
            print(f"✅ SUCCESS: Agent '{client._agent_context.name}' successfully fetched 'tavily_api_key'.")
            # In a real scenario, you would use the key:
            # tavily_client = TavilyClient(api_key=api_key_secret.value)
            # return tavily_client.search(query)
            return f"Search results for '{query}' using key '{api_key_secret.value[:4]}...'"
        except DeepSecureClientError as e:
            print(f"❌ FAILURE: Agent '{client._agent_context.name}' failed to fetch 'tavily_api_key'. Error: {e}")
            return "Error: Agent is not authorized to perform this search."

    return tavily_search

def create_secure_publish_tool(client: Client):
    """Another tool factory, this time for a publishing tool."""
    @tool
    def notion_publish(content: str) -> str:
        """A secure tool to publish content to Notion."""
        print(f"Attempting to use the publish tool with agent: '{client._agent_context.name}'")
        try:
            api_key_secret = client.get_secret("notion_api_key")
            print(f"✅ SUCCESS: Agent '{client._agent_context.name}' successfully fetched 'notion_api_key'.")
            return f"Published content starting with '{content[:20]}...' to Notion."
        except DeepSecureClientError as e:
            print(f"❌ FAILURE: Agent '{client._agent_context.name}' failed to fetch 'notion_api_key'. Error: {e}")
            return "Error: Agent is not authorized to publish to Notion."
            
    return notion_publish


# --- Main Application Logic ---

def main():
    print("--- DeepSecure LangChain Fine-Grained Tool Demo ---")

    # 1. Initialize the main DeepSecure client once.
    #    This client has no default agent context.
    try:
        client = deepsecure.Client()
    except DeepSecureClientError as e:
        print(f"Failed to initialize DeepSecure client. Have you run `deepsecure configure`? Error: {e}")
        return

    # 2. Create tools by passing an agent-specific client context.
    #    The `.with_agent()` method creates a temporary client view that can only
    #    act on behalf of the specified agent.
    print("\n--- Creating tools with agent-specific contexts... ---")
    researcher_client = client.with_agent("researcher", auto_create=True)
    writer_client = client.with_agent("writer", auto_create=True)
    
    # The researcher tool is created with a client scoped *only* to the "researcher" identity.
    research_tool = create_secure_search_tool(researcher_client)
    
    # The writer tool is created with a client scoped *only* to the "writer" identity.
    publish_tool = create_secure_publish_tool(writer_client)
    
    print("Tools created successfully.")

    # 3. Demonstrate that each tool can only perform its authorized action.
    print("\n--- Simulating Researcher Agent ---")
    print("Researcher tries to use the search tool (should succeed):")
    result1 = research_tool.invoke({"query": "latest AI trends"})
    print(f"Tool output: {result1}")
    
    print("\nResearcher tries to use the publish tool (should fail):")
    # To simulate this, we pass the researcher's client to the publish tool factory
    unauthorized_publish_tool = create_secure_publish_tool(researcher_client)
    result2 = unauthorized_publish_tool.invoke({"content": "This should not be published."})
    print(f"Tool output: {result2}")
    
    print("\n" + "="*50 + "\n")
    
    print("--- Simulating Writer Agent ---")
    print("Writer tries to use the publish tool (should succeed):")
    result3 = publish_tool.invoke({"content": "My new blog post about AI agents."})
    print(f"Tool output: {result3}")

    print("\nWriter tries to use the search tool (should fail):")
    # To simulate this, we pass the writer's client to the search tool factory
    unauthorized_search_tool = create_secure_search_tool(writer_client)
    result4 = unauthorized_search_tool.invoke({"query": "This search should not happen."})
    print(f"Tool output: {result4}")
    
    print("\n--- Demo Complete ---")


if __name__ == "__main__":
    main() 