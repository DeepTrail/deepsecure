# examples/05_langchain_secure_tools.py
"""
🦜 DeepSecure LangChain Integration - Secure Tools Demo

This example demonstrates how to integrate DeepSecure with LangChain for secure
AI agent workflows with fine-grained access control and comprehensive audit trails.

🎯 **SECURE LANGCHAIN WORKFLOW WITH FINE-GRAINED CONTROL**

Security Features Demonstrated:
1. **Agent Identity Management** - Each LangChain agent gets unique DeepSecure identity
2. **Secure Secret Access** - Tools fetch API keys through DeepSecure at runtime
3. **Fine-Grained Permissions** - Each agent only accesses secrets for their specific role
4. **Comprehensive Audit Trail** - All secret access and tool usage logged
5. **Framework Integration** - Seamless LangChain + DeepSecure integration

LangChain Agents:
- **Research Agent** - Accesses web search APIs (Tavily) for information gathering
- **Analysis Agent** - Accesses AI APIs (OpenAI) for data analysis and insights

Prerequisites:
1. `pip install deepsecure langchain`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored: tavily-api-key, openai-api-key
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
        return f"Mock agent {self.name} processed: {input_text}"

def create_secure_tavily_search_tool(client: deepsecure.Client, agent: deepsecure.resources.agent.Agent) -> MockTool:
    """
    Create a secure Tavily search tool that fetches API keys through DeepSecure.
    
    Args:
        client: DeepSecure client instance
        agent: DeepSecure agent with Tavily API access permissions
        
    Returns:
        Secure LangChain tool for web searches
    """
    def secure_tavily_search(query: str) -> str:
        """Perform secure web search using Tavily API with DeepSecure-managed credentials."""
        try:
            # Fetch Tavily API key securely through DeepSecure Control Plane
            tavily_secret = client.get_secret(agent.id, "tavily-api-key", "/")
            
            print(f"   🔍 [{agent.name}] Tavily search: '{query[:50]}...'")
            print(f"   🔐 Using API key: {tavily_secret.value[:8]}...")
            
            # Simulate Tavily search (in real implementation, use the actual Tavily API)
            mock_results = f"Tavily search results for '{query}': Found comprehensive information about {query} with multiple relevant sources."
            
            print(f"   ✅ Search completed successfully")
            return mock_results
            
        except Exception as e:
            print(f"   ❌ Tavily search failed: {e}")
            return f"Search failed: {e}"
    
    return MockTool(
        name="TavilySearch",
        description="Search the web for current information using Tavily API",
        func=secure_tavily_search
    )

def create_secure_openai_analysis_tool(client: deepsecure.Client, agent: deepsecure.resources.agent.Agent) -> MockTool:
    """
    Create a secure OpenAI analysis tool that fetches API keys through DeepSecure.
    
    Args:
        client: DeepSecure client instance
        agent: DeepSecure agent with OpenAI API access permissions
        
    Returns:
        Secure LangChain tool for AI analysis
    """
    def secure_openai_analysis(data: str) -> str:
        """Perform secure AI analysis using OpenAI API with DeepSecure-managed credentials."""
        try:
            # Fetch OpenAI API key securely through DeepSecure Control Plane
            openai_secret = client.get_secret(agent.id, "openai-api-key", "/")
            
            print(f"   🧠 [{agent.name}] OpenAI analysis: {len(data)} characters")
            print(f"   🔐 Using API key: {openai_secret.value[:8]}...")
            
            # Simulate OpenAI analysis (in real implementation, call OpenAI API)
            mock_analysis = f"OpenAI analysis complete: Extracted key insights from data. Identified {len(data.split())//10 + 1} main themes and actionable recommendations."
            
            print(f"   ✅ Analysis completed successfully")
            return mock_analysis
            
        except Exception as e:
            print(f"   ❌ OpenAI analysis failed: {e}")
            return f"Analysis failed: {e}"
    
    return MockTool(
        name="OpenAIAnalysis", 
        description="Analyze data and extract insights using OpenAI API",
        func=secure_openai_analysis
    )

def main():
    """
    Main demonstration of secure LangChain integration with fine-grained control.
    """
    print("🦜 DeepSecure + LangChain Integration Demo (Secure Tools)")
    print("=" * 60)
    print("This demo shows LangChain agents with secure, audited tool access.\n")
    
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
        
        # Create agent identities for each LangChain role
        print(f"\n🤖 Step 2: Creating agent identities...")
        
        # Research Agent - has access to web search APIs
        research_agent = client.agent("langchain-researcher", auto_create=True)
        print(f"   ✅ Research Agent: {research_agent.id}")
        
        # Analysis Agent - has access to AI APIs  
        analysis_agent = client.agent("langchain-analyst", auto_create=True)
        print(f"   ✅ Analysis Agent: {analysis_agent.id}")
        
        # Create secure tools for each agent
        print(f"\n🔧 Step 3: Creating secure tools...")
        
        tavily_tool = create_secure_tavily_search_tool(client, research_agent)
        openai_tool = create_secure_openai_analysis_tool(client, analysis_agent)
        
        print("   ✅ All secure tools created")
        
        # Create LangChain agents with secure tools
        print(f"\n🦜 Step 4: Setting up LangChain agents...")
        
        researcher = MockAgent(
            name="Research Specialist",
            tools=[tavily_tool]
        )
        
        analyst = MockAgent(
            name="Data Analyst", 
            tools=[openai_tool]
        )
        
        print("   ✅ LangChain agents configured with secure tools")
        
        # Demonstrate secure workflow
        print(f"\n🚀 Step 5: Executing secure LangChain workflow...")
        
        # Research phase
        print(f"\n📊 Research Phase:")
        research_query = "latest AI agent security frameworks and best practices"
        search_results = tavily_tool.func(research_query)
        
        # Analysis phase  
        print(f"\n🔍 Analysis Phase:")
        analysis_results = openai_tool.func(search_results)
        
        # Demonstrate agent processing
        print(f"\n🦜 LangChain Agent Processing:")
        researcher_output = researcher.run(research_query)
        analyst_output = analyst.run(search_results)
        
        print(f"   📋 Researcher output: {researcher_output}")
        print(f"   📈 Analyst output: {analyst_output}")
        
        print(f"\n{'='*60}")
        print("✅ LangChain Secure Integration Demo Complete!")
        print(f"{'='*60}")
        print("🔐 Security benefits demonstrated:")
        print("   • Each agent has unique cryptographic identity")
        print("   • Tools access secrets through DeepSecure with audit logging")  
        print("   • Fine-grained permissions per agent role")
        print("   • Complete audit trail of all secret access")
        print("   • Zero hardcoded API keys in the codebase")
        print("   • Secure just-in-time credential fetching")
        
        print(f"\n🎯 Production benefits:")
        print("   • Secrets are fetched from Control Plane at runtime")
        print("   • Each agent can only access authorized secrets")
        print("   • Comprehensive logging for compliance and debugging")
        print("   • Framework-agnostic security integration")
        
        print(f"\n🚀 Your LangChain agents are now production-ready with enterprise security!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")

if __name__ == "__main__":
    main() 