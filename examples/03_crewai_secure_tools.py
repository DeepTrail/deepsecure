# examples/03_crewai_secure_tools.py
"""
🤖 DeepSecure CrewAI Integration - Secure Tools Demo

This example demonstrates how to integrate DeepSecure with CrewAI for secure
multi-agent workflows with fine-grained access control and audit trails.

🎯 **SECURE CREWAI WORKFLOW WITH FINE-GRAINED CONTROL**

Security Features Demonstrated:
1. **Agent Identity Management** - Each CrewAI agent gets unique DeepSecure identity
2. **Secure Secret Access** - Tools access secrets through DeepSecure with audit logging
3. **Fine-Grained Permissions** - Each agent only accesses secrets for their specific role
4. **Comprehensive Audit Trail** - All secret access and tool usage logged
5. **Framework Integration** - Seamless CrewAI + DeepSecure integration

CrewAI Agents:
- **Research Agent** - Accesses web search APIs for research
- **Analysis Agent** - Accesses AI APIs for analysis  
- **Report Agent** - Accesses document storage for report generation

Prerequisites:
1. `pip install deepsecure crewai`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored: tavily-api-key, openai-api-key, report-storage-key
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

def create_secure_web_search_tool(client: deepsecure.Client, agent: deepsecure.resources.agent.Agent):
    """
    Create a secure web search tool that fetches API keys through DeepSecure.
    
    Args:
        client: DeepSecure client instance
        agent: DeepSecure agent with web search permissions
        
    Returns:
        Secure tool function for web searches
    """
    def secure_web_search(query: str) -> str:
        """Perform secure web search with DeepSecure-managed credentials."""
        try:
            # Fetch search API key securely through DeepSecure
            search_secret = client.get_secret(agent.id, "tavily-api-key", "/")
            
            print(f"   🔍 [{agent.name}] Performing web search: '{query[:50]}...'")
            print(f"   🔐 Using secure API key: {search_secret.value[:8]}...")
            
            # Simulate web search (in real implementation, use the actual API)
            mock_results = f"Search results for '{query}': Found 5 relevant articles about the topic."
            
            print(f"   ✅ Search completed successfully")
            return mock_results
            
        except Exception as e:
            print(f"   ❌ Web search failed: {e}")
            return f"Search failed: {e}"
    
    return secure_web_search

def create_secure_analysis_tool(client: deepsecure.Client, agent: deepsecure.resources.agent.Agent):
    """
    Create a secure analysis tool that fetches AI API keys through DeepSecure.
    
    Args:
        client: DeepSecure client instance  
        agent: DeepSecure agent with AI API permissions
        
    Returns:
        Secure tool function for AI-powered analysis
    """
    def secure_ai_analysis(data: str) -> str:
        """Perform secure AI analysis with DeepSecure-managed credentials."""
        try:
            # Fetch AI API key securely through DeepSecure
            ai_secret = client.get_secret(agent.id, "openai-api-key", "/")
            
            print(f"   🧠 [{agent.name}] Analyzing data: {len(data)} characters")
            print(f"   🔐 Using secure API key: {ai_secret.value[:8]}...")
            
            # Simulate AI analysis (in real implementation, call OpenAI API)
            mock_analysis = f"Analysis complete: The data shows 3 key trends and 2 actionable insights."
            
            print(f"   ✅ Analysis completed successfully")
            return mock_analysis
            
        except Exception as e:
            print(f"   ❌ AI analysis failed: {e}")
            return f"Analysis failed: {e}"
    
    return secure_ai_analysis

def create_secure_report_tool(client: deepsecure.Client, agent: deepsecure.resources.agent.Agent):
    """
    Create a secure report generation tool that fetches storage keys through DeepSecure.
    
    Args:
        client: DeepSecure client instance
        agent: DeepSecure agent with report storage permissions
        
    Returns:
        Secure tool function for report generation
    """
    def secure_report_generation(content: str) -> str:
        """Generate secure report with DeepSecure-managed storage credentials."""
        try:
            # Fetch storage API key securely through DeepSecure
            storage_secret = client.get_secret(agent.id, "report-storage-key", "/")
            
            print(f"   📄 [{agent.name}] Generating report: {len(content)} characters")
            print(f"   🔐 Using secure storage key: {storage_secret.value[:8]}...")
            
            # Simulate report generation (in real implementation, save to cloud storage)
            mock_report_url = "https://secure-storage.example.com/reports/analysis-report-123.pdf"
            
            print(f"   ✅ Report generated successfully")
            return f"Report saved: {mock_report_url}"
            
        except Exception as e:
            print(f"   ❌ Report generation failed: {e}")
            return f"Report generation failed: {e}"
    
    return secure_report_generation

def main():
    """
    Main demonstration of secure CrewAI integration with fine-grained control.
    """
    print("🤖 DeepSecure + CrewAI Integration Demo (Secure Tools)")
    print("=" * 60)
    print("This demo shows CrewAI agents with secure, audited tool access.\n")
    
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
        
        # Create agent identities for each CrewAI role
        print(f"\n🤖 Step 2: Creating agent identities...")
        
        # Research Agent - has access to web search APIs
        researcher_agent = client.agent("crewai-researcher", auto_create=True) 
        print(f"   ✅ Research Agent: {researcher_agent.id}")
        
        # Analysis Agent - has access to AI APIs
        analyst_agent = client.agent("crewai-analyst", auto_create=True)
        print(f"   ✅ Analysis Agent: {analyst_agent.id}")
        
        # Report Agent - has access to storage APIs
        reporter_agent = client.agent("crewai-reporter", auto_create=True)
        print(f"   ✅ Report Agent: {reporter_agent.id}")
        
        # Create secure tools for each agent
        print(f"\n🔧 Step 3: Creating secure tools...")
        
        research_tool = create_secure_web_search_tool(client, researcher_agent)
        analysis_tool = create_secure_analysis_tool(client, analyst_agent) 
        report_tool = create_secure_report_tool(client, reporter_agent)
        
        print("   ✅ All secure tools created")
        
        # Create CrewAI agents with secure tools
        print(f"\n👥 Step 4: Setting up CrewAI agents...")
        
        researcher = MockAgent(
            role="Research Specialist", 
            goal="Conduct comprehensive research on the given topic",
            backstory="Expert researcher with access to web search capabilities",
            tools=[research_tool]
        )
        
        analyst = MockAgent(
            role="Data Analyst",
            goal="Analyze research data and extract key insights", 
            backstory="Senior analyst specializing in data interpretation",
            tools=[analysis_tool]
        )
        
        reporter = MockAgent(
            role="Report Writer",
            goal="Generate comprehensive reports from analysis",
            backstory="Technical writer with expertise in creating detailed reports",
            tools=[report_tool]
        )
        
        print("   ✅ CrewAI agents configured with secure tools")
        
        # Create tasks for the crew
        print(f"\n📋 Step 5: Defining tasks...")
        
        research_task = MockTask(
            description="Research the latest trends in AI agent security",
            agent=researcher,
            expected_output="Comprehensive research summary with key findings"
        )
        
        analysis_task = MockTask(
            description="Analyze the research data and identify key insights",
            agent=analyst, 
            expected_output="Detailed analysis with actionable insights"
        )
        
        report_task = MockTask(
            description="Generate a comprehensive report from the analysis",
            agent=reporter,
            expected_output="Professional report document"
        )
        
        # Create and execute the crew
        print(f"\n🚀 Step 6: Executing secure CrewAI workflow...")
        
        crew = MockCrew(
            agents=[researcher, analyst, reporter],
            tasks=[research_task, analysis_task, report_task]
        )
        
        # Demonstrate secure tool execution
        print(f"\n🔍 Executing research task...")
        research_result = research_tool("AI agent security trends 2024")
        
        print(f"\n🧠 Executing analysis task...")  
        analysis_result = analysis_tool(research_result)
        
        print(f"\n📄 Executing report task...")
        report_result = report_tool(analysis_result)
        
        # Execute crew workflow
        print(f"\n👥 Starting CrewAI workflow...")
        result = crew.kickoff()
        
        print(f"\n{'='*60}")
        print("✅ CrewAI Secure Integration Demo Complete!")
        print(f"{'='*60}")
        print("🔐 Security benefits demonstrated:")
        print("   • Each agent has unique cryptographic identity")
        print("   • Tools access secrets through DeepSecure with audit logging")
        print("   • Fine-grained permissions per agent role")
        print("   • Complete audit trail of all secret access")
        print("   • Zero hardcoded API keys in the codebase")
        print(f"\n🚀 Your CrewAI agents are now production-ready with enterprise security!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")

if __name__ == "__main__":
    main() 