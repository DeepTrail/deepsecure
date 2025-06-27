# examples/04_crewai_secure_tools_without_finegrain_control.py
"""
This example demonstrates how to securely integrate DeepSecure with CrewAI
using a "Tool Factory" pattern with dependency injection.

This version works immediately without requiring fine-grained policy setup.
All agents share access to all secrets (permissive mode), but the example
still demonstrates the professional patterns for secure tool creation.

Prerequisites:
1. `pip install 'deepsecure[frameworks]'` (to install crewai)
2. A running DeepSecure `credservice` backend.
3. Your DeepSecure CLI is configured (`deepsecure configure`).
4. You have stored secrets in the vault, e.g.,
   `deepsecure vault store notion-api-key --value "your-notion-key"`
   `deepsecure vault store tavily-api-key --value "your-tavily-key"`

Note: This example demonstrates the tool factory pattern and framework integration.
In a production environment with fine-grained policies, each agent would be
restricted to only their authorized secrets.
"""
import os
import deepsecure
from crewai import Agent as CrewAIAgent, Task, Crew
from crewai.tools import tool

# --- Tool Factory Pattern ---
# This section defines functions that *create* tools.
# They take a DeepSecure client as an argument, which makes them secure and testable.

def create_notion_tool(client: deepsecure.Client):
    """Factory to create a secure Notion tool."""
    
    @tool("Notion Tool")
    def notion_tool(content: str) -> str:
        """
        A tool to write content to a Notion page.
        It securely fetches the Notion API key using its DeepSecure client.
        """
        print("\\n>> [Notion Tool] Action started.")
        try:
            # The client passed to this factory handles secure secret retrieval
            print(">> [Notion Tool] Securely fetching 'notion-api-key'...")
            api_key_secret = client.get_secret("notion-api-key")
            api_key = api_key_secret.value
            print(">> [Notion Tool] API key fetched successfully.")
            
            # Placeholder for actual Notion API call
            print(f">> [Notion Tool] Writing to Notion (simulation): '{content[:30]}...'")
            # Example: Real Notion integration would look like:
            # from notion_client import Client as NotionClient
            # notion_client = NotionClient(auth=api_key)
            # notion_client.pages.create(...)
            
            result = "Successfully wrote content to Notion."
            print(f">> [Notion Tool] {result}")
            return result
        except Exception as e:
            error_message = f"Failed to use Notion tool: {e}"
            print(f">> [Notion Tool] [ERROR] {error_message}")
            return error_message
            
    return notion_tool

def create_tavily_search_tool(client: deepsecure.Client):
    """Factory to create a secure Tavily search tool."""

    @tool("Tavily Search Tool")
    def tavily_search_tool(query: str) -> str:
        """
        A tool to search the web using Tavily.
        It securely fetches the Tavily API key using its DeepSecure client.
        """
        print("\\n>> [Tavily Tool] Action started.")
        try:
            print(">> [Tavily Tool] Securely fetching 'tavily-api-key'...")
            api_key_secret = client.get_secret("tavily-api-key")
            api_key = api_key_secret.value
            print(">> [Tavily Tool] API key fetched successfully.")
            
            # Placeholder for actual Tavily API call
            print(f">> [Tavily Tool] Searching Tavily for (simulation): '{query}'")
            # Example: Real Tavily integration would look like:
            # from tavily import TavilyClient
            # tavily_client = TavilyClient(api_key=api_key)
            # results = tavily_client.search(query)
            
            result = f"Search results for '{query}': Found comprehensive information about AI agents and security patterns."
            print(f">> [Tavily Tool] {result}")
            return result
        except Exception as e:
            error_message = f"Failed to use Tavily tool: {e}"
            print(f">> [Tavily Tool] [ERROR] {error_message}")
            return error_message

    return tavily_search_tool

# --- Main Crew Setup ---

def main():
    print("--- DeepSecure CrewAI Integration Example (Permissive Mode) ---")

    try:
        # 1. Initialize a single DeepSecure client.
        # In this permissive mode, we'll use the same client for all agents.
        print("✅ Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   Client initialized successfully.")

        # 2. Create agent identities for demonstration purposes.
        # Note: In permissive mode, both agents can access all secrets,
        # but we still create distinct identities for proper logging and audit trails.
        researcher_agent_name = "crew-researcher"
        writer_agent_name = "crew-writer"

        print(f"✅ Ensuring agent '{researcher_agent_name}' exists...")
        researcher_agent = client.agent(researcher_agent_name, auto_create=True)
        print(f"   Researcher agent ID: {researcher_agent.id}")
        
        print(f"✅ Ensuring agent '{writer_agent_name}' exists...")
        writer_agent = client.agent(writer_agent_name, auto_create=True)
        print(f"   Writer agent ID: {writer_agent.id}")

        # 3. Create agent-specific clients for clean separation (recommended pattern).
        # Even in permissive mode, this pattern promotes good architecture.
        researcher_client = client.with_agent(researcher_agent_name)
        writer_client = client.with_agent(writer_agent_name)

        # 4. Use the factories to create tools with agent-specific clients.
        # This demonstrates the dependency injection pattern.
        researcher_tool = create_tavily_search_tool(researcher_client)
        writer_tool = create_notion_tool(writer_client)
        print("✅ Secure, agent-specific tools created using factory pattern.")

        # 5. Create CrewAI Agents and assign their tools.
        researcher = CrewAIAgent(
            role='Senior Research Analyst',
            goal='Uncover cutting-edge developments in AI security',
            backstory="You work at a leading cybersecurity think tank specializing in AI agent security.",
            verbose=False,
            tools=[researcher_tool]
        )

        writer = CrewAIAgent(
            role='Tech Content Strategist',
            goal='Craft compelling content on AI security advancements',
            backstory="You are a renowned writer for a popular cybersecurity blog.",
            verbose=False,
            tools=[writer_tool]
        )
        print("✅ CrewAI agents defined with their respective tools.")

        # 6. Create Tasks for your agents
        task1 = Task(
            description="Research the latest trends in AI agent security and identity management.",
            expected_output="A 2-paragraph summary of the key security trends and challenges.",
            agent=researcher
        )

        task2 = Task(
            description="Based on the research summary, write a blog post draft about AI agent security and save it to Notion.",
            expected_output="Confirmation that the blog post was saved to Notion with a brief excerpt.",
            agent=writer
        )
        print("✅ Tasks created for the crew.")
        
        # 7. Instantiate your crew with a sequential process
        crew = Crew(
            agents=[researcher, writer],
            tasks=[task1, task2],
            verbose=True
        )
        
        print("\\n--- Crew Setup Complete ---")
        print("✅ CrewAI integration with DeepSecure completed successfully!")
        print()
        print("🔧 FRAMEWORK INTEGRATION DEMONSTRATED:")
        print("   • Tool Factory Pattern: Functions that create secure tools")
        print("   • Dependency Injection: Tools receive configured DeepSecure clients")
        print("   • Agent Identity Management: Each agent has a distinct identity")
        print("   • Secure Secret Retrieval: Tools fetch API keys just-in-time")
        print()
        print("💡 Note: This example runs in 'permissive mode' where agents can access any secret.")
        print("   In production, you would configure fine-grained policies to restrict access.")
        print()
        print("🚀 To actually run the crew, configure an LLM (e.g., set OPENAI_API_KEY)")
        print("   and uncomment the line below:")
        print("   # result = crew.kickoff()")

    except deepsecure.DeepSecureError as e:
        print(f"\\n[ERROR] A DeepSecure error occurred: {e}")
        print("Please ensure:")
        print("  1. The credservice backend is running")
        print("  2. DeepSecure CLI is configured (`deepsecure configure`)")
        print("  3. Secrets are stored in the vault:")
        print("     deepsecure vault store notion-api-key --value 'your-key'")
        print("     deepsecure vault store tavily-api-key --value 'your-key'")

    except Exception as e:
        print(f"\\n[ERROR] An unexpected error occurred: {e}")


if __name__ == "__main__":
    main() 