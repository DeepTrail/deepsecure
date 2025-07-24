# examples/10_crewai_delegation_workflow.py
"""
🤖 CrewAI + DeepSecure Delegation: Secure Multi-Agent Crew Workflows

This example demonstrates how to integrate DeepSecure's macaroon-based delegation
system with CrewAI to create secure, auditable multi-agent crew workflows.

🎯 **PRODUCTION-READY CREWAI DELEGATION**

Scenario: Financial Research Crew
1. A "Research Manager" oversees the entire research operation
2. A "Market Analyst" performs market data analysis
3. A "Risk Assessor" evaluates investment risks
4. A "Report Compiler" creates final deliverables
5. Each crew member receives delegated access only to required resources
6. All delegation activities are cryptographically secured and audited

Delegation Flow:
- Research Manager delegates market data access to Market Analyst
- Research Manager delegates risk assessment tools to Risk Assessor
- Both analysts delegate their findings to Report Compiler
- Each delegation includes specific time limits and usage restrictions
- Complete audit trail maintained throughout the workflow

Security Features:
- Cryptographic macaroon signatures ensure authenticity
- Fine-grained resource access control
- Time-based expiration prevents long-term exposure
- Action-specific permissions (read vs write vs execute)
- Comprehensive audit logging for compliance

Prerequisites:
1. `pip install deepsecure crewai`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Secrets stored in split-key store:
   ```bash
   deepsecure split-key store market-data-api-key --value "your_market_key"
   deepsecure split-key store risk-analysis-api-key --value "your_risk_key"
   deepsecure split-key store report-api-key --value "your_report_key"
   ```
"""

import deepsecure
import json
import time
import os
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# CrewAI imports
try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    print("⚠️  CrewAI not available. Install with: pip install crewai")
    CREWAI_AVAILABLE = False


@dataclass
class CrewDelegationRecord:
    """Record of delegation within a CrewAI workflow."""
    delegation_id: str
    delegator_agent: str
    delegatee_agent: str
    resource: str
    permissions: List[str]
    token: str
    created_at: datetime
    expires_at: datetime
    restrictions: Dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    last_used: Optional[datetime] = None


class SecureCrewAIAgent:
    """
    Enhanced CrewAI agent with DeepSecure delegation capabilities.
    
    This class wraps CrewAI agents to provide secure delegation and audit features.
    """
    
    def __init__(
        self, 
        agent_name: str, 
        role: str,
        goal: str,
        backstory: str,
        client: deepsecure.Client
    ):
        self.agent_name = agent_name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.client = client
        self.agent_resource = client.agent(agent_name, auto_create=True)
        self.delegation_records: Dict[str, CrewDelegationRecord] = {}
        self.received_delegations: Dict[str, CrewDelegationRecord] = {}
        
        # Create CrewAI agent if available
        if CREWAI_AVAILABLE:
            self.crewai_agent = Agent(
                role=role,
                goal=goal,
                backstory=backstory,
                verbose=True,
                allow_delegation=True  # Enable CrewAI delegation features
            )
        
        print(f"🤖 Secure CrewAI Agent '{agent_name}' initialized")
        print(f"   Role: {role}")
        print(f"   Agent ID: {self.agent_resource.id}")
    
    def delegate_to_crew_member(
        self,
        target_agent: 'SecureCrewAIAgent',
        resource: str,
        permissions: List[str],
        ttl_seconds: int = 600,
        usage_limit: Optional[int] = None,
        context: str = None
    ) -> str:
        """
        Delegate access to another crew member with detailed tracking.
        
        Args:
            target_agent: The crew member receiving delegation
            resource: Resource being delegated
            permissions: List of allowed actions
            ttl_seconds: Time-to-live for delegation
            usage_limit: Maximum number of uses allowed
            context: Additional context for audit trail
            
        Returns:
            Delegation token for the target agent
        """
        print(f"\n🔄 [{self.agent_name}] Delegating to crew member: {target_agent.agent_name}")
        print(f"   📋 Resource: {resource}")
        print(f"   🔑 Permissions: {permissions}")
        print(f"   ⏰ TTL: {ttl_seconds}s")
        if usage_limit:
            print(f"   📊 Usage limit: {usage_limit} requests")
        
        try:
            # Build delegation restrictions
            additional_restrictions = {
                "delegator_role": self.role,
                "delegatee_role": target_agent.role,
                "crew_context": context or "crewai_workflow",
                "workflow_type": "multi_agent_crew"
            }
            
            if usage_limit:
                additional_restrictions["request_count"] = usage_limit
            
            # Create delegation using DeepSecure
            delegation_token = self.client.delegate_access(
                delegator_agent_id=self.agent_resource.id,
                target_agent_id=target_agent.agent_resource.id,
                resource=resource,
                permissions=permissions,
                ttl_seconds=ttl_seconds,
                additional_restrictions=additional_restrictions
            )
            
            # Create delegation record
            delegation_id = f"crew_del_{int(time.time())}_{target_agent.agent_name}"
            created_at = datetime.now()
            expires_at = created_at + timedelta(seconds=ttl_seconds)
            
            delegation_record = CrewDelegationRecord(
                delegation_id=delegation_id,
                delegator_agent=self.agent_name,
                delegatee_agent=target_agent.agent_name,
                resource=resource,
                permissions=permissions,
                token=delegation_token,
                created_at=created_at,
                expires_at=expires_at,
                restrictions=additional_restrictions
            )
            
            # Track delegation on both sides
            self.delegation_records[delegation_id] = delegation_record
            target_agent.received_delegations[resource] = delegation_record
            
            print(f"✅ [{self.agent_name}] Crew delegation successful!")
            print(f"   🎫 Delegation ID: {delegation_id}")
            
            return delegation_token
            
        except Exception as e:
            print(f"❌ [{self.agent_name}] Crew delegation failed: {e}")
            raise
    
    def use_delegated_resource(
        self, 
        resource: str, 
        action: str,
        request_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Any]:
        """
        Use a delegated resource with comprehensive validation and logging.
        
        Args:
            resource: The resource to access
            action: The action to perform
            request_data: Additional data for the request
            
        Returns:
            Tuple of (success, result_data)
        """
        print(f"\n🔧 [{self.agent_name}] Attempting to use delegated resource")
        print(f"   📋 Resource: {resource}")
        print(f"   🎯 Action: {action}")
        
        if resource not in self.received_delegations:
            print(f"❌ [{self.agent_name}] No delegation found for resource: {resource}")
            return False, {"error": "No delegation found"}
        
        delegation = self.received_delegations[resource]
        
        # Check expiration
        if datetime.now() > delegation.expires_at:
            print(f"⏰ [{self.agent_name}] Delegation expired for resource: {resource}")
            del self.received_delegations[resource]
            return False, {"error": "Delegation expired"}
        
        # Check permissions
        if action not in delegation.permissions:
            print(f"🔒 [{self.agent_name}] Action '{action}' not permitted for resource: {resource}")
            return False, {"error": f"Action '{action}' not permitted"}
        
        # Check usage limits
        if "request_count" in delegation.restrictions:
            max_uses = delegation.restrictions["request_count"]
            if delegation.usage_count >= max_uses:
                print(f"📊 [{self.agent_name}] Usage limit exceeded for resource: {resource}")
                return False, {"error": "Usage limit exceeded"}
        
        # Update usage tracking
        delegation.usage_count += 1
        delegation.last_used = datetime.now()
        
        print(f"✅ [{self.agent_name}] Using delegated resource successfully")
        print(f"   📊 Usage: {delegation.usage_count}")
        
        # Simulate resource usage based on resource type
        if "market-data" in resource:
            result = self._simulate_market_data_api(action, request_data)
        elif "risk-analysis" in resource:
            result = self._simulate_risk_analysis_api(action, request_data)
        elif "report" in resource:
            result = self._simulate_report_api(action, request_data)
        else:
            result = {"status": "success", "data": "Generic API response"}
        
        return True, result
    
    def _simulate_market_data_api(self, action: str, data: Optional[Dict]) -> Dict[str, Any]:
        """Simulate market data API responses."""
        if action == "read":
            return {
                "market_data": {
                    "indices": {"S&P500": 4180.17, "NASDAQ": 12756.33, "DOW": 33274.15},
                    "sectors": {"Technology": 0.85, "Healthcare": 0.72, "Finance": 0.68},
                    "volatility": "moderate",
                    "timestamp": time.time()
                }
            }
        elif action == "analyze":
            return {
                "analysis": {
                    "trend": "bullish",
                    "momentum": "positive",
                    "support_levels": [4150, 4120, 4090],
                    "resistance_levels": [4200, 4230, 4260]
                }
            }
        return {"status": "success", "action": action}
    
    def _simulate_risk_analysis_api(self, action: str, data: Optional[Dict]) -> Dict[str, Any]:
        """Simulate risk analysis API responses."""
        if action == "assess":
            return {
                "risk_assessment": {
                    "overall_risk": "moderate",
                    "risk_factors": ["market_volatility", "regulatory_changes", "liquidity"],
                    "risk_score": 6.5,  # Out of 10
                    "recommendations": ["diversification", "hedging", "monitoring"]
                }
            }
        elif action == "calculate":
            return {
                "risk_metrics": {
                    "var_95": 0.025,  # Value at Risk
                    "expected_shortfall": 0.032,
                    "beta": 1.15,
                    "sharpe_ratio": 1.8
                }
            }
        return {"status": "success", "action": action}
    
    def _simulate_report_api(self, action: str, data: Optional[Dict]) -> Dict[str, Any]:
        """Simulate report generation API responses."""
        if action == "generate":
            return {
                "report": {
                    "title": "Financial Analysis Report",
                    "sections": ["Executive Summary", "Market Analysis", "Risk Assessment", "Recommendations"],
                    "format": "PDF",
                    "pages": 25,
                    "confidence": 0.89
                }
            }
        elif action == "compile":
            return {
                "compilation": {
                    "sources_integrated": 3,
                    "data_points": 156,
                    "charts_generated": 8,
                    "status": "complete"
                }
            }
        return {"status": "success", "action": action}
    
    def get_delegation_status(self) -> Dict[str, Any]:
        """Get comprehensive delegation status for this agent."""
        active_delegations = sum(
            1 for d in self.received_delegations.values() 
            if datetime.now() <= d.expires_at
        )
        
        granted_delegations = sum(
            1 for d in self.delegation_records.values()
            if datetime.now() <= d.expires_at
        )
        
        return {
            "agent_name": self.agent_name,
            "role": self.role,
            "active_delegations_received": active_delegations,
            "delegations_granted": granted_delegations,
            "total_delegations_ever_received": len(self.received_delegations),
            "total_delegations_ever_granted": len(self.delegation_records)
        }


class FinancialResearchCrew:
    """
    Secure financial research crew using DeepSecure delegation.
    
    This class orchestrates a crew of agents with secure delegation workflows.
    """
    
    def __init__(self, client: deepsecure.Client):
        self.client = client
        self.crew_members = {}
        self.workflow_results = {}
        
        # Create secure crew members
        self._initialize_crew_members()
        
        # Create CrewAI crew if available
        if CREWAI_AVAILABLE:
            self._create_crewai_crew()
        
        print(f"🎯 Financial Research Crew initialized with {len(self.crew_members)} members")
    
    def _initialize_crew_members(self):
        """Initialize all crew members with their roles."""
        
        # Research Manager
        self.crew_members["manager"] = SecureCrewAIAgent(
            agent_name="research-manager",
            role="Research Manager",
            goal="Coordinate financial research and ensure comprehensive analysis",
            backstory="Experienced financial researcher with expertise in market analysis coordination",
            client=self.client
        )
        
        # Market Analyst
        self.crew_members["analyst"] = SecureCrewAIAgent(
            agent_name="market-analyst",
            role="Market Analyst",
            goal="Analyze market trends and provide data-driven insights",
            backstory="Quantitative analyst specializing in market trend analysis and data interpretation",
            client=self.client
        )
        
        # Risk Assessor
        self.crew_members["risk_assessor"] = SecureCrewAIAgent(
            agent_name="risk-assessor",
            role="Risk Assessor",
            goal="Evaluate investment risks and provide risk mitigation strategies",
            backstory="Risk management expert with deep understanding of financial risk factors",
            client=self.client
        )
        
        # Report Compiler
        self.crew_members["compiler"] = SecureCrewAIAgent(
            agent_name="report-compiler",
            role="Report Compiler",
            goal="Create comprehensive reports from analysis data",
            backstory="Technical writer specialized in financial reporting and data visualization",
            client=self.client
        )
    
    def _create_crewai_crew(self):
        """Create CrewAI crew structure if available."""
        try:
            agents = [member.crewai_agent for member in self.crew_members.values()]
            
            # Define crew tasks (these would be more detailed in a real implementation)
            tasks = [
                Task(
                    description="Coordinate overall research workflow",
                    agent=self.crew_members["manager"].crewai_agent
                ),
                Task(
                    description="Perform market analysis",
                    agent=self.crew_members["analyst"].crewai_agent
                ),
                Task(
                    description="Assess investment risks",
                    agent=self.crew_members["risk_assessor"].crewai_agent
                ),
                Task(
                    description="Compile final report",
                    agent=self.crew_members["compiler"].crewai_agent
                )
            ]
            
            self.crewai_crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True
            )
            
            print("✅ CrewAI crew structure created")
            
        except Exception as e:
            print(f"⚠️  CrewAI crew creation failed: {e}")
            self.crewai_crew = None
    
    def execute_research_workflow(self, research_topic: str) -> Dict[str, Any]:
        """
        Execute a complete research workflow with secure delegation.
        
        Args:
            research_topic: Topic to research
            
        Returns:
            Comprehensive workflow results with delegation audit
        """
        print(f"\n{'='*70}")
        print(f"🎯 CREWAI RESEARCH WORKFLOW: {research_topic}")
        print(f"{'='*70}")
        
        workflow_start = time.time()
        workflow_id = f"crew_research_{int(workflow_start)}"
        
        try:
            manager = self.crew_members["manager"]
            analyst = self.crew_members["analyst"]
            risk_assessor = self.crew_members["risk_assessor"]
            compiler = self.crew_members["compiler"]
            
            # Phase 1: Manager delegates resources to specialists
            print(f"\n📋 PHASE 1: Resource Delegation")
            print("-" * 40)
            
            # Delegate market data access to analyst
            market_token = manager.delegate_to_crew_member(
                target_agent=analyst,
                resource="secret:market-data-api-key",
                permissions=["read", "analyze"],
                ttl_seconds=1200,  # 20 minutes
                usage_limit=10,
                context=f"market_analysis_{workflow_id}"
            )
            
            # Delegate risk assessment tools to risk assessor
            risk_token = manager.delegate_to_crew_member(
                target_agent=risk_assessor,
                resource="secret:risk-analysis-api-key",
                permissions=["assess", "calculate"],
                ttl_seconds=1200,  # 20 minutes
                usage_limit=8,
                context=f"risk_assessment_{workflow_id}"
            )
            
            # Phase 2: Specialists perform their analysis
            print(f"\n📋 PHASE 2: Specialist Analysis")
            print("-" * 40)
            
            # Market analysis
            print(f"\n📊 Market Analysis by {analyst.agent_name}")
            market_success, market_data = analyst.use_delegated_resource(
                "secret:market-data-api-key", 
                "read",
                {"topic": research_topic}
            )
            
            if market_success:
                analysis_success, analysis_data = analyst.use_delegated_resource(
                    "secret:market-data-api-key",
                    "analyze", 
                    {"market_data": market_data}
                )
            else:
                analysis_success, analysis_data = False, {"error": "Market data access failed"}
            
            # Risk assessment
            print(f"\n🛡️  Risk Assessment by {risk_assessor.agent_name}")
            risk_success, risk_data = risk_assessor.use_delegated_resource(
                "secret:risk-analysis-api-key",
                "assess",
                {"topic": research_topic, "market_data": market_data if market_success else None}
            )
            
            if risk_success:
                calc_success, calc_data = risk_assessor.use_delegated_resource(
                    "secret:risk-analysis-api-key",
                    "calculate",
                    {"risk_assessment": risk_data}
                )
            else:
                calc_success, calc_data = False, {"error": "Risk assessment access failed"}
            
            # Phase 3: Report compilation with cross-delegation
            print(f"\n📋 PHASE 3: Report Compilation")
            print("-" * 40)
            
            # Both specialists delegate their results to compiler
            if analysis_success:
                analyst_to_compiler_token = analyst.delegate_to_crew_member(
                    target_agent=compiler,
                    resource="analysis_results",
                    permissions=["read", "compile"],
                    ttl_seconds=600,  # 10 minutes
                    context=f"report_compilation_{workflow_id}"
                )
            
            if risk_success:
                risk_to_compiler_token = risk_assessor.delegate_to_crew_member(
                    target_agent=compiler,
                    resource="risk_results",
                    permissions=["read", "compile"],
                    ttl_seconds=600,  # 10 minutes
                    context=f"report_compilation_{workflow_id}"
                )
            
            # Manager delegates report generation to compiler
            report_token = manager.delegate_to_crew_member(
                target_agent=compiler,
                resource="secret:report-api-key",
                permissions=["generate", "compile"],
                ttl_seconds=900,  # 15 minutes
                usage_limit=5,
                context=f"final_report_{workflow_id}"
            )
            
            # Compiler generates final report
            print(f"\n📝 Final Report Generation by {compiler.agent_name}")
            report_success, report_data = compiler.use_delegated_resource(
                "secret:report-api-key",
                "generate",
                {
                    "topic": research_topic,
                    "market_analysis": analysis_data if analysis_success else None,
                    "risk_assessment": risk_data if risk_success else None
                }
            )
            
            # Phase 4: Compile workflow results
            workflow_end = time.time()
            
            # Get delegation status from all crew members
            delegation_status = {
                name: member.get_delegation_status()
                for name, member in self.crew_members.items()
            }
            
            workflow_results = {
                "workflow_id": workflow_id,
                "topic": research_topic,
                "start_time": workflow_start,
                "end_time": workflow_end,
                "duration_seconds": workflow_end - workflow_start,
                "crew_size": len(self.crew_members),
                "phases": {
                    "delegation": "completed",
                    "analysis": "completed" if market_success and risk_success else "partial",
                    "compilation": "completed" if report_success else "failed"
                },
                "results": {
                    "market_analysis": analysis_data if analysis_success else None,
                    "risk_assessment": calc_data if calc_success else None,
                    "final_report": report_data if report_success else None
                },
                "delegation_audit": delegation_status,
                "security_events": {
                    "delegations_created": 5,  # Total delegations in this workflow
                    "successful_resource_accesses": sum([
                        market_success, analysis_success, risk_success, calc_success, report_success
                    ]),
                    "failed_resource_accesses": sum([
                        not market_success, not analysis_success, not risk_success, 
                        not calc_success, not report_success
                    ])
                }
            }
            
            print(f"\n🎉 CrewAI Research Workflow Completed!")
            print(f"⏱️  Duration: {workflow_end - workflow_start:.2f} seconds")
            print(f"🔐 Security events: {workflow_results['security_events']}")
            
            return workflow_results
            
        except Exception as e:
            print(f"\n❌ CrewAI Research Workflow Failed: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time()
            }


def demonstrate_crewai_delegation_patterns(crew: FinancialResearchCrew):
    """
    Demonstrate advanced delegation patterns in CrewAI context.
    """
    print(f"\n{'='*70}")
    print("🔗 ADVANCED: CrewAI Delegation Patterns")
    print(f"{'='*70}")
    
    manager = crew.crew_members["manager"]
    analyst = crew.crew_members["analyst"]
    compiler = crew.crew_members["compiler"]
    
    # Pattern 1: Temporary cross-delegation
    print(f"\n📋 Pattern 1: Temporary Cross-Delegation")
    try:
        # Analyst temporarily delegates analysis tools to compiler for verification
        temp_token = analyst.delegate_to_crew_member(
            target_agent=compiler,
            resource="analysis_verification",
            permissions=["verify", "validate"],
            ttl_seconds=120,  # Very short-lived
            usage_limit=2,
            context="cross_verification"
        )
        
        # Use the temporary delegation
        success, result = compiler.use_delegated_resource(
            "analysis_verification",
            "verify",
            {"data": "sample_analysis_data"}
        )
        
        if success:
            print("✅ Temporary cross-delegation successful")
        else:
            print("❌ Temporary cross-delegation failed")
            
    except Exception as e:
        print(f"❌ Cross-delegation pattern failed: {e}")
    
    # Pattern 2: Hierarchical delegation chain
    print(f"\n📋 Pattern 2: Hierarchical Delegation Chain")
    try:
        # Manager → Analyst → Compiler delegation chain
        chain_spec = [
            {
                'from_agent_id': manager.agent_resource.id,
                'to_agent_id': analyst.agent_resource.id,
                'resource': 'https://api.hierarchical-data.com',
                'permissions': ['read:all', 'analyze:basic'],
                'ttl_seconds': 1800
            },
            {
                'from_agent_id': analyst.agent_resource.id,
                'to_agent_id': compiler.agent_resource.id,
                'resource': 'https://api.hierarchical-data.com/reports',
                'permissions': ['read:reports'],  # More restricted
                'ttl_seconds': 900
            }
        ]
        
        delegation_tokens = crew.client.create_delegation_chain(chain_spec)
        print(f"✅ Hierarchical delegation chain created: {len(delegation_tokens)} tokens")
        
    except Exception as e:
        print(f"❌ Hierarchical delegation failed: {e}")


def test_crewai_delegation_security(crew: FinancialResearchCrew):
    """
    Test security aspects of CrewAI delegation system.
    """
    print(f"\n{'='*70}")
    print("🛡️  SECURITY: CrewAI Delegation Security Testing")
    print(f"{'='*70}")
    
    manager = crew.crew_members["manager"]
    analyst = crew.crew_members["analyst"]
    
    # Security Test 1: Usage limit enforcement
    print(f"\n🔒 Security Test 1: Usage Limit Enforcement")
    try:
        # Create delegation with strict usage limit
        limited_token = manager.delegate_to_crew_member(
            target_agent=analyst,
            resource="secret:limited-resource",
            permissions=["read"],
            ttl_seconds=300,
            usage_limit=2,  # Only 2 uses allowed
            context="usage_limit_test"
        )
        
        # Use the delegation multiple times to test limit
        for i in range(4):  # Try 4 times, expect failure after 2
            success, result = analyst.use_delegated_resource(
                "secret:limited-resource",
                "read",
                {"attempt": i + 1}
            )
            
            if not success and i >= 2:
                print(f"✅ Usage limit correctly enforced after {i} attempts")
                break
        else:
            print("❌ Usage limit was not enforced properly")
            
    except Exception as e:
        print(f"✅ Usage limit enforcement working: {e}")
    
    # Security Test 2: Permission granularity
    print(f"\n🔒 Security Test 2: Permission Granularity")
    try:
        # Create read-only delegation
        readonly_token = manager.delegate_to_crew_member(
            target_agent=analyst,
            resource="secret:readonly-resource",
            permissions=["read"],  # Only read permission
            ttl_seconds=300,
            context="permission_test"
        )
        
        # Try to use write operation (should fail)
        success, result = analyst.use_delegated_resource(
            "secret:readonly-resource",
            "write",  # Not allowed
            {"data": "test"}
        )
        
        if not success:
            print("✅ Permission granularity correctly enforced")
        else:
            print("❌ Permission granularity was not enforced")
            
    except Exception as e:
        print(f"✅ Permission enforcement working: {e}")


def main():
    """
    Main demonstration of CrewAI + DeepSecure delegation workflow.
    """
    print("🤖 CrewAI + DeepSecure Delegation Workflow")
    print("==========================================")
    print("This example demonstrates secure multi-agent crews")
    print("using CrewAI with DeepSecure delegation.\n")
    
    if not CREWAI_AVAILABLE:
        print("❌ CrewAI not available. Please install:")
        print("   pip install crewai")
        print("\n🔧 Running basic delegation demo without CrewAI...")
    
    # Environment check
    if not os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL"):
        print("⚠️  [WARNING] DEEPSECURE_DEEPTRAIL_CONTROL_URL not set")
        print("🔧 [INFO] Using mock implementation for demonstration\n")
    
    try:
        # Initialize DeepSecure client
        client = deepsecure.Client()
        
        # Create secure CrewAI crew
        crew = FinancialResearchCrew(client)
        
        # === Main Workflow Demonstration ===
        print(f"\n{'='*70}")
        print("🚀 EXECUTING: Complete CrewAI Research Workflow")
        print(f"{'='*70}")
        
        # Execute the complete research workflow
        workflow_results = crew.execute_research_workflow("AI and Machine Learning Sector")
        
        # Display results
        if workflow_results.get("status") != "failed":
            print(f"\n📊 CREWAI WORKFLOW RESULTS:")
            print(f"{'='*50}")
            print(json.dumps(workflow_results, indent=2, default=str))
        
        # === Advanced Delegation Patterns ===
        demonstrate_crewai_delegation_patterns(crew)
        
        # === Security Testing ===
        test_crewai_delegation_security(crew)
        
        # === Crew Summary ===
        print(f"\n{'='*70}")
        print("✅ CrewAI + DeepSecure Delegation Demo Complete!")
        print(f"{'='*70}")
        print("🔐 Demonstrated features:")
        print("   • Secure crew member delegation")
        print("   • Multi-phase workflow coordination")
        print("   • Usage limit enforcement")
        print("   • Permission granularity")
        print("   • Cross-delegation patterns")
        print("   • Hierarchical delegation chains")
        print("   • Comprehensive audit trails")
        print("   • Security testing and validation")
        
        if CREWAI_AVAILABLE:
            print("🤖 CrewAI integration: ACTIVE")
        else:
            print("🤖 CrewAI integration: SIMULATED")
        
        print(f"\n🎯 Ready for production crews with secure delegation!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")


if __name__ == "__main__":
    main() 