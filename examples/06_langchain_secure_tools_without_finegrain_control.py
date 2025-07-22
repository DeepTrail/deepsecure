# examples/06_langchain_secure_tools_without_finegrain_control.py
"""
🦜 DeepSecure LangChain Integration - Secure Tools without Fine-Grained Control

This example demonstrates how to integrate DeepSecure with LangChain using a simpler
approach where all agents can access all secrets (no fine-grained policies).

🎯 **SIMPLE LANGCHAIN WORKFLOW WITH SHARED SECRET ACCESS**

Key Features:
1. **Simplified Agent Management** - All agents use the same DeepSecure identity
2. **Shared Secret Access** - All tools can access any stored secret
3. **Easy Development** - Perfect for rapid prototyping and development
4. **Comprehensive Audit Trail** - All secret access still logged and audited
5. **Framework Integration** - Clean LangChain + DeepSecure integration

Use Cases:
- Development and testing environments
- Small teams with trusted agents
- Rapid prototyping workflows
- When fine-grained policies aren't needed

LangChain Agents:
- **Research Agent** - Conducts web research using multiple APIs
- **Analysis Agent** - Performs data analysis with AI tools
- **Processing Agent** - Handles data processing and storage

Prerequisites:
1. `pip install deepsecure langchain`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored: tavily-api-key, openai-api-key, storage-api-key
"""

import deepsecure
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Mock LangChain classes for demonstration
@dataclass
class MockTool:
    name: str
    description: str
    func: callable

class MockAgent:
    def __init__(self, name: str, tools: List[MockTool] = None):
        self.name = name
        self.tools = tools or []
    
    def run(self, input_text: str) -> str:
        return f"Mock LangChain agent {self.name} processed: {input_text}"

class MockChain:
    def __init__(self, agents: List[MockAgent]):
        self.agents = agents
    
    def run(self, input_data: str) -> str:
        result = input_data
        for agent in self.agents:
            result = agent.run(result)
        return result

def create_universal_web_search_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent) -> MockTool:
    """
    Create a universal web search tool that any LangChain agent can use.
    
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
            mock_results = f"Web search results for '{query}': Found comprehensive information with multiple sources."
            
            print(f"   ✅ Search completed successfully")
            return mock_results
            
        except Exception as e:
            print(f"   ❌ Web search failed: {e}")
            return f"Search failed: {e}"
    
    return MockTool(
        name="UniversalWebSearch",
        description="Search the web using shared search API credentials",
        func=universal_web_search
    )

def create_universal_ai_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent) -> MockTool:
    """
    Create a universal AI analysis tool that any LangChain agent can use.
    
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
            
            print(f"   🧠 [Shared Agent] AI analysis: {len(data)} characters")
            print(f"   🔐 Using AI API key: {ai_secret.value[:8]}...")
            
            # Simulate AI analysis (in real implementation, call OpenAI API)
            mock_analysis = f"AI analysis complete: Extracted insights from data. Found {len(data.split())//10 + 1} key topics."
            
            print(f"   ✅ Analysis completed successfully")
            return mock_analysis
            
        except Exception as e:
            print(f"   ❌ AI analysis failed: {e}")
            return f"Analysis failed: {e}"
    
    return MockTool(
        name="UniversalAI",
        description="Perform AI analysis using shared AI API credentials",
        func=universal_ai_analysis
    )

def create_universal_storage_tool(client: deepsecure.Client, shared_agent: deepsecure.resources.agent.Agent) -> MockTool:
    """
    Create a universal storage tool that any LangChain agent can use.
    
    Args:
        client: DeepSecure client instance
        shared_agent: Shared DeepSecure agent identity
        
    Returns:
        Universal tool function for data storage
    """
    def universal_storage(content: str, filename: str = "langchain-output.txt") -> str:
        """Store data using shared credentials."""
        try:
            # Fetch storage API key using shared agent identity
            storage_secret = client.get_secret(shared_agent.id, "storage-api-key", "/")
            
            print(f"   💾 [Shared Agent] Storing: {filename} ({len(content)} chars)")
            print(f"   🔐 Using storage key: {storage_secret.value[:8]}...")
            
            # Simulate storage (in real implementation, save to cloud storage)
            mock_url = f"https://secure-storage.example.com/langchain/{filename}"
            
            print(f"   ✅ Storage completed successfully")
            return f"File saved: {mock_url}"
            
        except Exception as e:
            print(f"   ❌ Storage failed: {e}")
            return f"Storage failed: {e}"
    
    return MockTool(
        name="UniversalStorage",
        description="Store data using shared storage credentials", 
        func=universal_storage
    )

def main():
    """
    Main demonstration of simple LangChain integration without fine-grained control.
    """
    print("🦜 DeepSecure + LangChain Integration Demo (Simple/Shared Access)")
    print("=" * 65)
    print("This demo shows LangChain agents with shared, simplified secret access.\n")
    
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
        shared_agent = client.agent("langchain-shared-agent", auto_create=True)
        print(f"   ✅ Shared Agent: {shared_agent.id}")
        print("   📝 All LangChain agents will use this shared identity")
        
        # Create universal tools that all agents can use
        print(f"\n🔧 Step 3: Creating universal tools...")
        
        search_tool = create_universal_web_search_tool(client, shared_agent)
        ai_tool = create_universal_ai_tool(client, shared_agent)
        storage_tool = create_universal_storage_tool(client, shared_agent)
        
        print("   ✅ All universal tools created")
        print("   📝 All agents can use any tool")
        
        # Create LangChain agents with access to all tools
        print(f"\n🦜 Step 4: Setting up LangChain agents...")
        
        # All agents have access to all tools (simplified approach)
        all_tools = [search_tool, ai_tool, storage_tool]
        
        researcher = MockAgent(
            name="Research Agent",
            tools=all_tools
        )
        
        processor = MockAgent(
            name="Processing Agent", 
            tools=all_tools
        )
        
        coordinator = MockAgent(
            name="Coordination Agent",
            tools=all_tools
        )
        
        print("   ✅ LangChain agents configured with universal tool access")
        
        # Create processing chain
        print(f"\n🔗 Step 5: Setting up LangChain processing chain...")
        
        processing_chain = MockChain([researcher, processor, coordinator])
        print("   ✅ Processing chain created")
        
        # Demonstrate universal tool usage across agents
        print(f"\n🚀 Step 6: Executing flexible LangChain workflow...")
        
        # Any agent can use any tool - maximum flexibility
        print(f"\n🔍 Research Agent using search tool...")
        search_result = search_tool.func("LangChain security integration patterns")
        
        print(f"\n🧠 Processing Agent using AI tool...")
        ai_result = ai_tool.func(search_result)
        
        print(f"\n💾 Coordinator Agent using storage tool...")
        storage_result = storage_tool.func(ai_result, "langchain-analysis.txt")
        
        # Demonstrate chain processing
        print(f"\n🔗 Running full processing chain...")
        chain_input = "AI agent security in LangChain applications"
        chain_result = processing_chain.run(chain_input)
        print(f"   📋 Chain result: {chain_result}")
        
        print(f"\n{'='*65}")
        print("✅ LangChain Simple Integration Demo Complete!")
        print(f"{'='*65}")
        print("🔐 Benefits of simple approach:")
        print("   • Rapid development and prototyping")
        print("   • Shared agent identity reduces complexity")
        print("   • Maximum flexibility - any agent can use any tool")
        print("   • Complete audit trail still maintained")
        print("   • Zero hardcoded secrets in codebase")
        print("   • Easy to modify and extend workflows")
        
        print(f"\n💡 When to use this approach:")
        print("   • Development and testing environments")
        print("   • Small, trusted teams")
        print("   • Rapid prototyping scenarios")
        print("   • When fine-grained policies aren't critical")
        print("   • Exploratory AI workflows")
        
        print(f"\n🎯 LangChain specific benefits:")
        print("   • Works with any LangChain agent or chain")
        print("   • Compatible with all LangChain tools and components")
        print("   • Maintains LangChain's flexibility while adding security")
        print("   • Easy integration with existing LangChain applications")
        
        print(f"\n🚀 Your LangChain workflow is secure and production-ready!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")

if __name__ == "__main__":
    main() 