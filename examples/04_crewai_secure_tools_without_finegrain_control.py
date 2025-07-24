# examples/04_crewai_secure_tools_without_finegrain_control.py
"""
🤖 DeepSecure CrewAI Integration - Secure Tools without Fine-Grained Control

This example demonstrates how to integrate DeepSecure with CrewAI using a simpler
approach where all agents can access all secrets (no fine-grained policies).

🎯 **SIMPLE CREWAI WORKFLOW WITH SHARED SECRET ACCESS**

Key Features:
1. **Simplified Agent Management** - All agents use the same DeepSecure identity
2. **Shared Secret Access** - All tools can access any stored secret
3. **Easy Development** - Perfect for rapid prototyping and development
4. **Comprehensive Audit Trail** - All secret access still logged and audited
5. **Framework Integration** - Clean CrewAI + DeepSecure integration

Use Cases:
- Development and testing environments
- Small teams with trusted agents
- Rapid prototyping workflows
- When fine-grained policies aren't needed

CrewAI Agents:
- **Research Agent** - Conducts web research
- **Analysis Agent** - Performs data analysis
- **Report Agent** - Generates reports

Prerequisites:
1. `pip install deepsecure crewai`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored: tavily-api-key, openai-api-key, storage-api-key
"""

import deepsecure
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Mock CrewAI classes for demonstration
@dataclass
class MockAgent:
    role: str
    goal: str
    backstory: str
    tools: list = None

@dataclass
class MockTask:
    description: str
    agent: MockAgent
    expected_output: str

class MockCrew:
    def __init__(self, agents, tasks):
        self.agents = agents
        self.tasks = tasks
    
    def kickoff(self):
        return {"status": "completed", "output": "Mock crew execution completed"}

def create_universal_web_search_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent):
    """
    Create a universal web search tool that any CrewAI agent can use.
    
    Args:
        client: DeepSecure client instance
        shared_agent: Shared DeepSecure agent identity
        
    Returns:
        Universal tool function for web searches
    """
    def universal_web_search(query: str) -> str:
        """Perform web search using shared credentials."""
        try:
            # Fetch search API key using shared agent identity
            search_secret = client.get_secret(shared_agent.id, "tavily-api-key", "/")
            
            print(f"   🔍 [Shared Agent] Web search: '{query[:50]}...'")
            print(f"   🔐 Using API key: {search_secret.value[:8]}...")
            
            # Simulate web search (in real implementation, use the actual API)
            mock_results = f"Search results for '{query}': Found relevant information about {query}."
            
            print(f"   ✅ Search completed successfully")
            return mock_results
            
        except Exception as e:
            print(f"   ❌ Web search failed: {e}")
            return f"Search failed: {e}"
    
    return universal_web_search

def create_universal_analysis_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent):
    """
    Create a universal analysis tool that any CrewAI agent can use.
    
    Args:
        client: DeepSecure client instance
        shared_agent: Shared DeepSecure agent identity
        
    Returns:
        Universal tool function for AI analysis
    """
    def universal_ai_analysis(data: str) -> str:
        """Perform AI analysis using shared credentials."""
        try:
            # Fetch AI API key using shared agent identity
            ai_secret = client.get_secret(shared_agent.id, "openai-api-key", "/")
            
            print(f"   🧠 [Shared Agent] Analyzing: {len(data)} characters")
            print(f"   🔐 Using AI API key: {ai_secret.value[:8]}...")
            
            # Simulate AI analysis (in real implementation, call OpenAI API)
            mock_analysis = f"Analysis complete: Key insights extracted from data. Found {len(data)//50} main topics."
            
            print(f"   ✅ Analysis completed successfully")
            return mock_analysis
            
        except Exception as e:
            print(f"   ❌ AI analysis failed: {e}")
            return f"Analysis failed: {e}"
    
    return universal_ai_analysis

def create_universal_storage_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent):
    """
    Create a universal storage tool that any CrewAI agent can use.
    
    Args:
        client: DeepSecure client instance
        shared_agent: Shared DeepSecure agent identity
        
    Returns:
        Universal tool function for data storage
    """
    def universal_storage(content: str, filename: str = "output.txt") -> str:
        """Store data using shared credentials."""
        try:
            # Fetch storage API key using shared agent identity
            storage_secret = client.get_secret(shared_agent.id, "storage-api-key", "/")
            
            print(f"   💾 [Shared Agent] Storing: {filename} ({len(content)} chars)")
            print(f"   🔐 Using storage key: {storage_secret.value[:8]}...")
            
            # Simulate storage (in real implementation, save to cloud storage)
            mock_url = f"https://secure-storage.example.com/files/{filename}"
            
            print(f"   ✅ Storage completed successfully")
            return f"File saved: {mock_url}"
            
        except Exception as e:
            print(f"   ❌ Storage failed: {e}")
            return f"Storage failed: {e}"
    
    return universal_storage

def main():
    """
    Main demonstration of simple CrewAI integration without fine-grained control.
    """
    print("🤖 DeepSecure + CrewAI Integration Demo (Simple/Shared Access)")
    print("=" * 65)
    print("This demo shows CrewAI agents with shared, simplified secret access.\n")
    
    # Environment check
    if not os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL"):
        print("⚠️  [WARNING] DEEPSECURE_DEEPTRAIL_CONTROL_URL not set")
        print("🔧 [INFO] Using mock implementation for demonstration\n")
    
    try:
        # Initialize DeepSecure client
        print("🚀 Step 1: Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   ✅ DeepSecure client initialized")
        print(f"   🏗️  Control Plane: {client._api_url}")
        
        # Create single shared agent identity
        print(f"\n🤖 Step 2: Creating shared agent identity...")
        shared_agent = client.agent("crewai-shared-agent", auto_create=True)
        print(f"   ✅ Shared Agent: {shared_agent.id}")
        print("   📝 All CrewAI agents will use this shared identity")
        
        # Create universal tools that all agents can use
        print(f"\n🔧 Step 3: Creating universal tools...")
        
        search_tool = create_universal_web_search_tool(client, shared_agent)
        analysis_tool = create_universal_analysis_tool(client, shared_agent)
        storage_tool = create_universal_storage_tool(client, shared_agent)
        
        print("   ✅ All universal tools created")
        print("   📝 All agents can use any tool")
        
        # Create CrewAI agents with access to all tools
        print(f"\n👥 Step 4: Setting up CrewAI agents...")
        
        # All agents have access to all tools (simplified approach)
        all_tools = [search_tool, analysis_tool, storage_tool]
        
        researcher = MockAgent(
            role="Research Specialist",
            goal="Conduct comprehensive research on any topic",
            backstory="Expert researcher with broad access to search capabilities",
            tools=all_tools
        )
        
        analyst = MockAgent(
            role="Data Analyst",
            goal="Analyze any data and extract insights",
            backstory="Senior analyst with access to AI and storage capabilities", 
            tools=all_tools
        )
        
        coordinator = MockAgent(
            role="Project Coordinator",
            goal="Coordinate workflows and manage outputs",
            backstory="Project manager with full tool access for coordination",
            tools=all_tools
        )
        
        print("   ✅ CrewAI agents configured with universal tool access")
        
        # Create tasks for the crew
        print(f"\n📋 Step 5: Defining collaborative tasks...")
        
        research_task = MockTask(
            description="Research the latest developments in AI agent security frameworks",
            agent=researcher,
            expected_output="Comprehensive research summary with sources"
        )
        
        analysis_task = MockTask(
            description="Analyze research findings and extract actionable insights",
            agent=analyst,
            expected_output="Detailed analysis with recommendations"
        )
        
        coordination_task = MockTask(
            description="Coordinate the final output and store results securely",
            agent=coordinator,
            expected_output="Organized final deliverable with secure storage"
        )
        
        # Create and execute the crew
        print(f"\n🚀 Step 6: Executing collaborative CrewAI workflow...")
        
        crew = MockCrew(
            agents=[researcher, analyst, coordinator],
            tasks=[research_task, analysis_task, coordination_task]
        )
        
        # Demonstrate universal tool usage
        print(f"\n🔍 Researcher executing search...")
        search_result = search_tool("AI agent security best practices")
        
        print(f"\n🧠 Analyst performing analysis...")
        analysis_result = analysis_tool(search_result)
        
        print(f"\n💾 Coordinator storing results...")
        storage_result = storage_tool(analysis_result, "ai-security-analysis.txt")
        
        # Execute crew workflow
        print(f"\n👥 Starting collaborative CrewAI workflow...")
        result = crew.kickoff()
        
        print(f"\n{'='*65}")
        print("✅ CrewAI Simple Integration Demo Complete!")
        print(f"{'='*65}")
        print("🔐 Benefits of simple approach:")
        print("   • Rapid development and prototyping")
        print("   • Shared agent identity reduces complexity")
        print("   • All agents have flexible tool access")
        print("   • Complete audit trail still maintained")
        print("   • Zero hardcoded secrets in codebase")
        print("   • Easy to scale and modify workflows")
        
        print(f"\n💡 When to use this approach:")
        print("   • Development and testing environments")
        print("   • Small, trusted teams")
        print("   • Rapid prototyping scenarios")
        print("   • When fine-grained policies aren't critical")
        
        print(f"\n🚀 Your CrewAI workflow is secure and production-ready!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")

if __name__ == "__main__":
    main() 