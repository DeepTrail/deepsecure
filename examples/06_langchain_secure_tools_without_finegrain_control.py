# examples/06_langchain_secure_tools_without_finegrain_control.py
"""
This example demonstrates how to build secure, reusable tools for LangChain
agents using the DeepSecure SDK without requiring fine-grained policy setup.

It showcases the "Tool Factory" and "Dependency Injection" patterns, where each
tool is created with a DeepSecure client context. This version works immediately
in "permissive mode" where agents can access all secrets.

**Scenario:**
- We have two conceptual agents: a "researcher" and a "writer".
- The "researcher" uses a search tool that needs a Tavily API key.
- The "writer" uses a publishing tool that needs a Notion API key.
- Both tools demonstrate secure secret retrieval patterns.

**To Run This Example:**
1. Make sure the `credservice` backend is running.
2. Configure the DeepSecure CLI (`deepsecure configure`).
3. Store the secrets in the vault:
   ```bash
   deepsecure vault store tavily_api_key --value "tvly-your-real-or-dummy-key"
   deepsecure vault store notion_api_key --value "secret_your-real-or-dummy-key"
   ```
4. Install langchain-community:
   ```bash
   pip install langchain-community
   ```

Note: This example demonstrates the integration patterns. In a production
environment with fine-grained policies, each agent would be restricted to
only their authorized secrets.
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
        agent_name = getattr(client, '_agent_context', None)
        agent_display = agent_name.name if agent_name else 'default'
        
        print(f"\\n🔍 [Search Tool] Executing search with agent context: '{agent_display}'")
        try:
            # The tool explicitly uses the injected client to get the secret.
            # No magic, just clear, testable code.
            print("🔍 [Search Tool] Fetching 'tavily_api_key' securely...")
            api_key_secret = client.get_secret("tavily_api_key")
            print(f"✅ [Search Tool] SUCCESS: API key retrieved for agent '{agent_display}'.")
            
            # In a real scenario, you would use the key with the actual API:
            # from tavily import TavilyClient
            # tavily_client = TavilyClient(api_key=api_key_secret.value)
            # return tavily_client.search(query)
            
            # For demonstration, we'll simulate the response
            print(f"🔍 [Search Tool] Simulating search for: '{query}'")
            result = f"Search results for '{query}': Found information about AI agent security, identity management, and secure credential handling using key '{api_key_secret.value[:8]}...'"
            print(f"📋 [Search Tool] Returning results.")
            return result
            
        except DeepSecureClientError as e:
            error_msg = f"❌ FAILURE: Agent '{agent_display}' failed to fetch 'tavily_api_key'. Error: {e}"
            print(error_msg)
            return "Error: Agent is not authorized to perform this search."

    return tavily_search

def create_secure_publish_tool(client: Client):
    """Another tool factory, this time for a publishing tool."""
    @tool
    def notion_publish(content: str) -> str:
        """A secure tool to publish content to Notion."""
        agent_name = getattr(client, '_agent_context', None)
        agent_display = agent_name.name if agent_name else 'default'
        
        print(f"\\n📝 [Publish Tool] Executing publish with agent context: '{agent_display}'")
        try:
            print("📝 [Publish Tool] Fetching 'notion_api_key' securely...")
            api_key_secret = client.get_secret("notion_api_key")
            print(f"✅ [Publish Tool] SUCCESS: API key retrieved for agent '{agent_display}'.")
            
            # In a real scenario, you would use the key with the actual API:
            # from notion_client import Client as NotionClient
            # notion_client = NotionClient(auth=api_key_secret.value)
            # notion_client.pages.create(...)
            
            # For demonstration, we'll simulate the response
            print(f"📝 [Publish Tool] Simulating content publish: '{content[:50]}...'")
            result = f"Published content to Notion successfully using key '{api_key_secret.value[:8]}...'. Content preview: '{content[:100]}...'"
            print(f"✅ [Publish Tool] Content published successfully.")
            return result
            
        except DeepSecureClientError as e:
            error_msg = f"❌ FAILURE: Agent '{agent_display}' failed to fetch 'notion_api_key'. Error: {e}"
            print(error_msg)
            return "Error: Agent is not authorized to publish to Notion."
            
    return notion_publish


# --- Main Application Logic ---

def main():
    print("--- DeepSecure LangChain Secure Tools Demo (Permissive Mode) ---")

    # 1. Initialize the main DeepSecure client once.
    #    This client has no default agent context.
    try:
        print("🚀 Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   ✅ Client initialized successfully.")
    except DeepSecureClientError as e:
        print(f"❌ Failed to initialize DeepSecure client. Have you run `deepsecure configure`? Error: {e}")
        return

    # 2. Create tools by passing an agent-specific client context.
    #    The `.with_agent()` method creates a temporary client view that can only
    #    act on behalf of the specified agent.
    print("\\n🔧 Creating tools with agent-specific contexts...")
    
    try:
        # Create agent identities and scoped clients
        print("   Creating researcher agent context...")
        researcher_client = client.with_agent("researcher", auto_create=True)
        
        print("   Creating writer agent context...")
        writer_client = client.with_agent("writer", auto_create=True)
        
        # The researcher tool is created with a client scoped *only* to the "researcher" identity.
        print("   🔍 Creating search tool for researcher...")
        research_tool = create_secure_search_tool(researcher_client)
        
        # The writer tool is created with a client scoped *only* to the "writer" identity.
        print("   📝 Creating publish tool for writer...")
        publish_tool = create_secure_publish_tool(writer_client)
        
        print("✅ Tools created successfully with agent-specific contexts.")
        
    except Exception as e:
        print(f"❌ Failed to create agent contexts or tools: {e}")
        return

    # 3. Demonstrate the tool usage patterns.
    print("\\n" + "="*70)
    print("🧪 TESTING TOOL FUNCTIONALITY")
    print("="*70)
    
    print("\\n--- Researcher Agent Workflow ---")
    print("🔍 Researcher using search tool (should work):")
    try:
        result1 = research_tool.invoke({"query": "latest AI agent security trends"})
        print(f"📋 Tool output: {result1}")
    except Exception as e:
        print(f"❌ Error invoking search tool: {e}")
    
    print("\\n📝 Researcher attempting to use publish tool (cross-agent access):")
    try:
        # To simulate cross-agent access, we create a publish tool with researcher's client
        unauthorized_publish_tool = create_secure_publish_tool(researcher_client)
        result2 = unauthorized_publish_tool.invoke({"content": "This should work in permissive mode."})
        print(f"📋 Tool output: {result2}")
        print("💡 Note: In permissive mode, this succeeds. With policies, it would be restricted.")
    except Exception as e:
        print(f"❌ Error invoking publish tool: {e}")
    
    print("\\n" + "-"*70)
    
    print("\\n--- Writer Agent Workflow ---")
    print("📝 Writer using publish tool (should work):")
    try:
        result3 = publish_tool.invoke({"content": "My comprehensive blog post about AI agent security best practices and how DeepSecure enables secure credential management."})
        print(f"📋 Tool output: {result3}")
    except Exception as e:
        print(f"❌ Error invoking publish tool: {e}")

    print("\\n🔍 Writer attempting to use search tool (cross-agent access):")
    try:
        # To simulate cross-agent access, we create a search tool with writer's client
        unauthorized_search_tool = create_secure_search_tool(writer_client)
        result4 = unauthorized_search_tool.invoke({"query": "This search should work in permissive mode."})
        print(f"📋 Tool output: {result4}")
        print("💡 Note: In permissive mode, this succeeds. With policies, it would be restricted.")
    except Exception as e:
        print(f"❌ Error invoking search tool: {e}")
    
    print("\\n" + "="*70)
    print("✅ DEMO COMPLETE")
    print("="*70)
    
    print("\\n🔧 FRAMEWORK INTEGRATION DEMONSTRATED:")
    print("   • Tool Factory Pattern: Functions that create secure tools")
    print("   • Dependency Injection: Tools receive configured DeepSecure clients")
    print("   • Agent Identity Management: Each agent has a distinct identity")
    print("   • Secure Secret Retrieval: Tools fetch API keys just-in-time")
    print("   • LangChain Integration: Tools work seamlessly with LangChain agents")
    print()
    print("💡 SECURITY NOTES:")
    print("   • This example runs in 'permissive mode' - agents can access any secret")
    print("   • In production, configure fine-grained policies to enforce least privilege")
    print("   • The patterns shown here scale to policy-enforced environments")
    print()
    print("🚀 NEXT STEPS:")
    print("   • Use these tools in actual LangChain agents or chains")
    print("   • Configure fine-grained policies for production security")
    print("   • Explore advanced patterns like agent-to-agent communication")


if __name__ == "__main__":
    main() 