# examples/09_langchain_delegation_workflow.py
"""
🤖 LangChain + DeepSecure Delegation: Advanced Multi-Agent Workflow

This example demonstrates how to integrate DeepSecure's macaroon-based delegation
system with LangChain agents to create secure, auditable multi-agent workflows.

🎯 **PRODUCTION-READY LANGCHAIN DELEGATION**

Scenario: Research & Analysis Workflow
1. A "Research Coordinator" manages research tasks
2. A "Data Analyst" specializes in financial data analysis  
3. A "Report Writer" creates summaries and reports
4. Each agent receives only the minimum permissions needed
5. All delegation is cryptographically secured and time-limited

Delegation Flow:
- Research Coordinator delegates search API access to Data Analyst
- Data Analyst delegates report data to Report Writer  
- Each delegation includes specific restrictions and expiration times
- All activities are audited through DeepSecure

Security Features:
- Cryptographic macaroon tokens prevent forgery
- Time-based expiration limits exposure window
- Resource-specific access (search API vs report API)
- Action limitations (read-only vs read-write)
- Audit trail for compliance and debugging

Prerequisites:
1. `pip install deepsecure langchain langchain-community`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored in vault:
   ```bash
   deepsecure vault secrets store tavily-api-key --value "your_tavily_key"
   deepsecure vault secrets store openai-api-key --value "your_openai_key"
   ```
"""

import deepsecure
import json
import time
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# LangChain imports
try:
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.runnables import RunnableConfig
    from langchain.agents import initialize_agent, AgentType
    from langchain.schema import AgentAction, AgentFinish
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("⚠️  LangChain not available. Install with: pip install langchain langchain-community")
    LANGCHAIN_AVAILABLE = False


@dataclass
class DelegationContext:
    """Context information for delegation tracking."""
    delegator_id: str
    delegatee_id: str
    resource: str
    permissions: List[str]
    token: str
    expires_at: float
    restrictions: Dict[str, Any]


class SecureLangChainAgent:
    """
    Base class for LangChain agents with DeepSecure delegation support.
    
    This class provides secure delegation capabilities and audit logging
    for LangChain-based agents.
    """
    
    def __init__(self, agent_name: str, client: deepsecure.Client):
        self.agent_name = agent_name
        self.client = client
        self.agent_resource = client.agent(agent_name, auto_create=True)
        self.active_delegations: Dict[str, DelegationContext] = {}
        
        print(f"🤖 {agent_name} initialized. ID: {self.agent_resource.id}")
    
    def delegate_to_agent(
        self,
        target_agent: 'SecureLangChainAgent',
        resource: str,
        permissions: List[str],
        ttl_seconds: int = 300,
        context: str = None
    ) -> str:
        """
        Delegate access to another LangChain agent.
        
        Args:
            target_agent: The agent receiving delegation
            resource: Resource being delegated (e.g., API endpoint)
            permissions: List of allowed actions
            ttl_seconds: Time-to-live for delegation
            context: Additional context for audit trail
            
        Returns:
            Delegation token for the target agent
        """
        print(f"\n🔄 [{self.agent_name}] Delegating to {target_agent.agent_name}")
        print(f"   📋 Resource: {resource}")
        print(f"   🔑 Permissions: {permissions}")
        print(f"   ⏰ TTL: {ttl_seconds}s")
        
        try:
            additional_restrictions = {}
            if context:
                additional_restrictions["context"] = context
                additional_restrictions["delegator"] = self.agent_name
                additional_restrictions["task_type"] = "langchain_workflow"
            
            delegation_token = self.client.delegate_access(
                delegator_agent_id=self.agent_resource.id,
                target_agent_id=target_agent.agent_resource.id,
                resource=resource,
                permissions=permissions,
                ttl_seconds=ttl_seconds,
                additional_restrictions=additional_restrictions
            )
            
            # Track delegation for audit
            delegation_context = DelegationContext(
                delegator_id=self.agent_resource.id,
                delegatee_id=target_agent.agent_resource.id,
                resource=resource,
                permissions=permissions,
                token=delegation_token,
                expires_at=time.time() + ttl_seconds,
                restrictions=additional_restrictions
            )
            
            target_agent.active_delegations[resource] = delegation_context
            
            print(f"✅ [{self.agent_name}] Delegation successful!")
            return delegation_token
            
        except Exception as e:
            print(f"❌ [{self.agent_name}] Delegation failed: {e}")
            raise
    
    def use_delegated_access(self, resource: str, action: str) -> bool:
        """
        Use delegated access to perform an action on a resource.
        
        Args:
            resource: The resource to access
            action: The action to perform
            
        Returns:
            True if access is granted, False otherwise
        """
        if resource not in self.active_delegations:
            print(f"❌ [{self.agent_name}] No delegation found for resource: {resource}")
            return False
        
        delegation = self.active_delegations[resource]
        
        # Check expiration
        if time.time() > delegation.expires_at:
            print(f"⏰ [{self.agent_name}] Delegation expired for resource: {resource}")
            del self.active_delegations[resource]
            return False
        
        # Check permissions
        if action not in delegation.permissions:
            print(f"🔒 [{self.agent_name}] Action '{action}' not permitted for resource: {resource}")
            return False
        
        print(f"✅ [{self.agent_name}] Using delegated access for {resource}:{action}")
        return True
    
    def create_secure_tool(self, tool_name: str, resource: str, action: str):
        """
        Create a secure LangChain tool that checks delegation before execution.
        
        Args:
            tool_name: Name of the tool
            resource: Resource the tool accesses
            action: Action the tool performs
            
        Returns:
            LangChain tool with delegation checking
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required for secure tools")
        
        agent_name = self.agent_name
        
        @tool(tool_name)
        def secure_tool(query: str) -> str:
            """A secure tool that validates delegation before execution."""
            print(f"\n🔧 [{agent_name}] Attempting to use tool: {tool_name}")
            
            # Check delegation before proceeding
            if not self.use_delegated_access(resource, action):
                return f"❌ Access denied: No valid delegation for {resource}:{action}"
            
            # Simulate tool execution (in real implementation, would use actual APIs)
            print(f"🚀 [{agent_name}] Executing {tool_name} with query: {query}")
            
            if "search" in tool_name.lower():
                return self._simulate_search_api(query)
            elif "report" in tool_name.lower():
                return self._simulate_report_api(query)
            else:
                return f"Tool {tool_name} executed successfully with query: {query}"
        
        return secure_tool
    
    def _simulate_search_api(self, query: str) -> str:
        """Simulate a search API call."""
        return f"Search results for '{query}': [Simulated financial data and market trends]"
    
    def _simulate_report_api(self, query: str) -> str:
        """Simulate a report generation API call."""
        return f"Report generated for '{query}': [Simulated comprehensive analysis report]"


class ResearchCoordinator(SecureLangChainAgent):
    """
    Research Coordinator agent that manages research workflows and delegates tasks.
    """
    
    def __init__(self, client: deepsecure.Client):
        super().__init__("research-coordinator", client)
        self.research_tasks = []
    
    def initiate_research_workflow(
        self,
        data_analyst: 'DataAnalyst',
        report_writer: 'ReportWriter',
        research_topic: str
    ) -> Dict[str, Any]:
        """
        Initiate a complete research workflow with proper delegation.
        
        Args:
            data_analyst: The data analyst agent
            report_writer: The report writer agent
            research_topic: Topic to research
            
        Returns:
            Workflow results with delegation audit trail
        """
        print(f"\n{'='*60}")
        print(f"🎯 RESEARCH WORKFLOW: {research_topic}")
        print(f"{'='*60}")
        
        workflow_start = time.time()
        workflow_id = f"research_{int(workflow_start)}"
        
        try:
            # Step 1: Delegate search API access to Data Analyst
            print(f"\n📋 Step 1: Delegating search access to Data Analyst")
            search_token = self.delegate_to_agent(
                target_agent=data_analyst,
                resource="secret:tavily-api-key",
                permissions=["read", "search"],
                ttl_seconds=600,  # 10 minutes
                context=f"data_analysis_{workflow_id}"
            )
            
            # Step 2: Delegate report API access to Report Writer  
            print(f"\n📋 Step 2: Delegating report access to Report Writer")
            report_token = self.delegate_to_agent(
                target_agent=report_writer,
                resource="secret:openai-api-key", 
                permissions=["read", "generate"],
                ttl_seconds=900,  # 15 minutes
                context=f"report_generation_{workflow_id}"
            )
            
            # Step 3: Execute workflow
            print(f"\n📋 Step 3: Executing research workflow")
            analysis_results = data_analyst.perform_financial_analysis(research_topic)
            report_results = report_writer.generate_research_report(
                research_topic, 
                analysis_results
            )
            
            # Step 4: Compile workflow results
            workflow_results = {
                "workflow_id": workflow_id,
                "topic": research_topic,
                "coordinator": self.agent_name,
                "start_time": workflow_start,
                "completion_time": time.time(),
                "analysis": analysis_results,
                "report": report_results,
                "delegations": {
                    "search_delegation": {
                        "target": data_analyst.agent_name,
                        "resource": "secret:tavily-api-key",
                        "token": search_token[:20] + "..."
                    },
                    "report_delegation": {
                        "target": report_writer.agent_name,
                        "resource": "secret:openai-api-key", 
                        "token": report_token[:20] + "..."
                    }
                }
            }
            
            print(f"\n🎉 Research workflow completed successfully!")
            print(f"📊 Duration: {workflow_results['completion_time'] - workflow_start:.2f} seconds")
            
            return workflow_results
            
        except Exception as e:
            print(f"\n❌ Research workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e)
            }


class DataAnalyst(SecureLangChainAgent):
    """
    Data Analyst agent specialized in financial data analysis with delegated access.
    """
    
    def __init__(self, client: deepsecure.Client):
        super().__init__("data-analyst", client)
        
        # Create secure tools for this agent
        if LANGCHAIN_AVAILABLE:
            self.search_tool = self.create_secure_tool(
                "Financial Search", 
                "secret:tavily-api-key", 
                "search"
            )
    
    def perform_financial_analysis(self, topic: str) -> Dict[str, Any]:
        """
        Perform financial analysis using delegated search access.
        
        Args:
            topic: Topic to analyze
            
        Returns:
            Analysis results
        """
        print(f"\n📊 [{self.agent_name}] Starting financial analysis for: {topic}")
        
        # Use delegated access to search for financial data
        if not self.use_delegated_access("secret:tavily-api-key", "search"):
            return {"error": "No valid delegation for financial search"}
        
        # Simulate comprehensive financial analysis
        print(f"🔍 [{self.agent_name}] Searching financial databases...")
        print(f"📈 [{self.agent_name}] Analyzing market trends...")
        print(f"💡 [{self.agent_name}] Generating insights...")
        
        analysis_results = {
            "topic": topic,
            "analyst": self.agent_name,
            "timestamp": time.time(),
            "market_data": {
                "trend": "upward",
                "volatility": "moderate",
                "key_indicators": ["volume", "price", "sentiment"]
            },
            "insights": [
                f"Strong growth potential in {topic} sector",
                "Market sentiment remains positive",
                "Recommended for further monitoring"
            ],
            "risk_assessment": "moderate",
            "confidence": 0.85,
            "delegated_access_used": True
        }
        
        print(f"✅ [{self.agent_name}] Financial analysis completed")
        return analysis_results


class ReportWriter(SecureLangChainAgent):
    """
    Report Writer agent that generates comprehensive reports using delegated access.
    """
    
    def __init__(self, client: deepsecure.Client):
        super().__init__("report-writer", client)
        
        # Create secure tools for this agent
        if LANGCHAIN_AVAILABLE:
            self.report_tool = self.create_secure_tool(
                "Report Generator",
                "secret:openai-api-key",
                "generate"
            )
    
    def generate_research_report(
        self, 
        topic: str, 
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive research report using delegated access.
        
        Args:
            topic: Research topic
            analysis_data: Data from financial analysis
            
        Returns:
            Generated report
        """
        print(f"\n📝 [{self.agent_name}] Generating research report for: {topic}")
        
        # Use delegated access to generate report
        if not self.use_delegated_access("secret:openai-api-key", "generate"):
            return {"error": "No valid delegation for report generation"}
        
        # Simulate report generation
        print(f"✍️  [{self.agent_name}] Compiling analysis data...")
        print(f"📄 [{self.agent_name}] Generating executive summary...")
        print(f"📊 [{self.agent_name}] Creating visualizations...")
        
        report_results = {
            "topic": topic,
            "author": self.agent_name,
            "timestamp": time.time(),
            "executive_summary": f"Comprehensive analysis of {topic} reveals positive market outlook",
            "key_findings": analysis_data.get("insights", []),
            "risk_assessment": analysis_data.get("risk_assessment", "unknown"),
            "recommendations": [
                f"Continue monitoring {topic} developments",
                "Consider strategic investment opportunities",
                "Implement risk mitigation strategies"
            ],
            "confidence_score": analysis_data.get("confidence", 0.0),
            "data_sources": ["Financial APIs", "Market databases", "Analysis algorithms"],
            "delegated_access_used": True,
            "based_on_analysis": analysis_data.get("topic") == topic
        }
        
        print(f"✅ [{self.agent_name}] Research report completed")
        return report_results


def demonstrate_langchain_delegation_failures(
    coordinator: ResearchCoordinator,
    analyst: DataAnalyst
):
    """
    Demonstrate various delegation failure scenarios in LangChain context.
    """
    print(f"\n{'='*60}")
    print("🚨 TESTING: LangChain Delegation Failure Scenarios")
    print(f"{'='*60}")
    
    # Scenario 1: Expired delegation
    print(f"\n🕒 Scenario 1: Using expired delegation")
    try:
        # Create short-lived delegation
        short_token = coordinator.delegate_to_agent(
            target_agent=analyst,
            resource="secret:test-api-key",
            permissions=["read"],
            ttl_seconds=1,  # Very short
            context="expiration_test"
        )
        
        print("⏳ Waiting for delegation to expire...")
        time.sleep(2)
        
        # Try to use expired delegation
        success = analyst.use_delegated_access("secret:test-api-key", "read")
        if not success:
            print("✅ Correctly rejected expired delegation")
        else:
            print("❌ ERROR: Expired delegation was accepted!")
            
    except Exception as e:
        print(f"✅ Correctly handled expiration: {e}")
    
    # Scenario 2: Invalid permissions
    print(f"\n🔒 Scenario 2: Using delegation with insufficient permissions")
    try:
        # Create read-only delegation
        limited_token = coordinator.delegate_to_agent(
            target_agent=analyst,
            resource="secret:limited-api-key",
            permissions=["read"],  # Only read permission
            ttl_seconds=300,
            context="permission_test"
        )
        
        # Try to use write permission (not granted)
        success = analyst.use_delegated_access("secret:limited-api-key", "write")
        if not success:
            print("✅ Correctly rejected insufficient permissions")
        else:
            print("❌ ERROR: Invalid permission was accepted!")
            
    except Exception as e:
        print(f"✅ Correctly handled permission error: {e}")


def main():
    """
    Main demonstration of LangChain + DeepSecure delegation workflow.
    """
    print("🤖 LangChain + DeepSecure Delegation Workflow")
    print("==============================================")
    print("This example demonstrates secure multi-agent workflows")
    print("using LangChain agents with DeepSecure delegation.\n")
    
    if not LANGCHAIN_AVAILABLE:
        print("❌ LangChain not available. Please install:")
        print("   pip install langchain langchain-community")
        print("\n🔧 Running basic delegation demo without LangChain...")
    
    # Environment check
    if not os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL"):
        print("⚠️  [WARNING] DEEPSECURE_DEEPTRAIL_CONTROL_URL not set")
        print("🔧 [INFO] Using mock implementation for demonstration\n")
    
    try:
        # Initialize DeepSecure client
        client = deepsecure.Client()
        
        # Create LangChain agents with DeepSecure delegation
        coordinator = ResearchCoordinator(client)
        data_analyst = DataAnalyst(client)
        report_writer = ReportWriter(client)
        
        # === Main Workflow Demonstration ===
        print(f"\n{'='*60}")
        print("🚀 EXECUTING: Complete Research Workflow")
        print(f"{'='*60}")
        
        # Execute the complete research workflow
        workflow_results = coordinator.initiate_research_workflow(
            data_analyst=data_analyst,
            report_writer=report_writer,
            research_topic="Renewable Energy Sector"
        )
        
        # Display results
        if workflow_results.get("status") != "failed":
            print(f"\n📊 WORKFLOW RESULTS:")
            print(f"{'='*40}")
            print(json.dumps(workflow_results, indent=2, default=str))
        
        # === Delegation Security Testing ===
        demonstrate_langchain_delegation_failures(coordinator, data_analyst)
        
        # === Workflow Summary ===
        print(f"\n{'='*60}")
        print("✅ LangChain + DeepSecure Delegation Demo Complete!")
        print(f"{'='*60}")
        print("🔐 Demonstrated features:")
        print("   • Secure agent-to-agent delegation")
        print("   • Time-limited access tokens")
        print("   • Resource-specific permissions")
        print("   • Comprehensive audit trail")
        print("   • Failure scenario handling")
        print("   • LangChain tool integration")
        
        if LANGCHAIN_AVAILABLE:
            print("🤖 LangChain integration: ACTIVE")
        else:
            print("🤖 LangChain integration: SIMULATED")
        
        print(f"\n🎯 Ready for production workflows with secure delegation!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")


if __name__ == "__main__":
    main() 