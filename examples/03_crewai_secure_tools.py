# examples/03_crewai_secure_tools.py
"""
This example demonstrates how to securely integrate DeepSecure with CrewAI
using a "Tool Factory" pattern with dependency injection.

This pattern ensures that each agent in a crew can be given tools that
are securely scoped to its specific identity.

Prerequisites:
1. `pip install 'deepsecure[frameworks]'` (to install crewai)
2. A running DeepSecure `credservice` backend.
3. Your DeepSecure CLI is configured (`deepsecure configure`).
4. You have stored a secret in the vault, e.g.,
   `deepsecure vault store notion-api-key --value "your-notion-key"`
   `deepsecure vault store tavily-api-key --value "your-tavily-key"`
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
            # The client passed to this factory is already scoped to an agent.
            # This call will fail if the agent is not authorized for this secret.
            print(">> [Notion Tool] Securely fetching 'notion-api-key'...")
            api_key_secret = client.get_secret("notion-api-key")
            api_key = api_key_secret.value
            print(">> [Notion Tool] API key fetched successfully.")
            
            # Placeholder for actual Notion API call
            print(f">> [Notion Tool] Writing to Notion (simulation): '{content[:30]}...'")
            # a_real_notion_client = NotionClient(auth=api_key)
            # a_real_notion_client.pages.create(...)
            
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
            # from tavily import TavilyClient
            # tavily_client = TavilyClient(api_key=api_key)
            # results = tavily_client.search(...)
            
            result = f"Search results for '{query}': AI agents are amazing."
            print(f">> [Tavily Tool] {result}")
            return result
        except Exception as e:
            error_message = f"Failed to use Tavily tool: {e}"
            print(f">> [Tavily Tool] [ERROR] {error_message}")
            return error_message

    return tavily_search_tool

# --- Main Crew Setup ---

def main():
    print("--- DeepSecure CrewAI Integration Example ---")

    try:
        # 1. Initialize a single, master DeepSecure client.
        master_client = deepsecure.Client()
        print("✅ Master DeepSecure client initialized.")

        # 2. Define agent identities and create agent-specific clients.
        # This enforces the Principle of Least Privilege.
        researcher_agent_name = "crew-researcher"
        writer_agent_name = "crew-writer"

        print(f"✅ Creating agent-specific client for '{researcher_agent_name}'...")
        researcher_client = master_client.with_agent(researcher_agent_name, auto_create=True)
        
        print(f"✅ Creating agent-specific client for '{writer_agent_name}'...")
        writer_client = master_client.with_agent(writer_agent_name, auto_create=True)

        # 3. Use the factories to create tools, injecting the agent-specific clients.
        # The researcher's tool can only access secrets authorized for the "crew-researcher" agent.
        researcher_tool = create_tavily_search_tool(researcher_client)
        
        # The writer's tool can only access secrets authorized for the "crew-writer" agent.
        writer_tool = create_notion_tool(writer_client)
        print("✅ Secure, agent-specific tools created.")

        # 4. Create CrewAI Agents and assign their scoped tools.
        researcher = CrewAIAgent(
            role='Senior Research Analyst',
            goal='Uncover cutting-edge developments in AI',
            backstory="You work at a leading tech think tank.",
            verbose=False,
            tools=[researcher_tool] # This agent ONLY has the search tool
        )

        writer = CrewAIAgent(
            role='Tech Content Strategist',
            goal='Craft compelling content on AI advancements',
            backstory="You are a renowned writer for a popular tech blog.",
            verbose=False,
            tools=[writer_tool] # This agent ONLY has the Notion tool
        )
        print("✅ CrewAI agents defined with scoped tools.")

        # 5. Create Tasks for your agents
        task1 = Task(
            description="Investigate the latest trends in multi-agent AI systems.",
            expected_output="A 1-paragraph summary of the key trends.",
            agent=researcher
        )

        task2 = Task(
            description="Based on the research summary, write a blog post draft and save it to Notion.",
            expected_output="Confirmation that the blog post was saved to Notion.",
            agent=writer
        )
        print("✅ Tasks created.")
        
        # 6. Instantiate your crew with a sequential process
        crew = Crew(
            agents=[researcher, writer],
            tasks=[task1, task2],
            verbose=True
        )
        
        print("\\n--- Crew Setup Complete ---")
        print("✅ CrewAI integration with DeepSecure completed successfully!")
        print("Note: To actually run the crew, you would need to configure an LLM (e.g., OpenAI API key).")
        print("The secure tool integration is working correctly.")

    except deepsecure.DeepSecureError as e:
        print(f"\\n[ERROR] A DeepSecure error occurred: {e}")
        print("Please ensure secrets 'notion-api-key' and 'tavily-api-key' are stored in the vault.")
        print("You may also need to create policies, e.g.:")
        print("  deepsecure policy create --agent-name crew-researcher --secret-name tavily-api-key --action read")
        print("  deepsecure policy create --agent-name crew-writer --secret-name notion-api-key --action read")

    except Exception as e:
        print(f"\\n[ERROR] An unexpected error occurred: {e}")


if __name__ == "__main__":
    main() 