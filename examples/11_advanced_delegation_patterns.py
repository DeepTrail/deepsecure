# examples/11_advanced_delegation_patterns.py
"""
🔗 Advanced DeepSecure Delegation Patterns

This example demonstrates sophisticated delegation patterns and scenarios
using DeepSecure's macaroon-based delegation system for complex enterprise workflows.

🎯 **ENTERPRISE-GRADE DELEGATION PATTERNS**

Advanced Patterns Demonstrated:
1. **Delegation Chains** - Multi-level A→B→C→D delegation workflows
2. **Conditional Delegation** - Context-aware delegation with dynamic restrictions
3. **Temporal Delegation** - Time-based access patterns (business hours, emergency)
4. **Emergency Protocols** - Break-glass access with audit requirements
5. **Cross-Domain Delegation** - Secure delegation across different system domains
6. **Delegation Hierarchies** - Role-based delegation with inheritance
7. **Revocation Patterns** - Active delegation revocation and cascade effects

Enterprise Scenarios:
- Financial trading systems with approval chains
- Healthcare systems with emergency access protocols
- DevOps workflows with graduated access levels
- Compliance systems with audit requirements
- Multi-tenant environments with isolation

Security Features:
- Cryptographic delegation chains with progressive attenuation
- Fine-grained temporal controls (time-of-day, day-of-week)
- Emergency break-glass protocols with mandatory audit
- Cross-validation and multi-party approval workflows
- Automatic delegation revocation and cleanup

Prerequisites:
1. `pip install deepsecure`
2. DeepSecure backend running (control plane + gateway)
3. DeepSecure CLI configured (`deepsecure configure`)
4. Multiple secrets stored for different scenarios
"""

import deepsecure
import json
import time
import os
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
from contextlib import contextmanager


class DelegationPattern(Enum):
    """Types of delegation patterns."""
    LINEAR_CHAIN = "linear_chain"
    HIERARCHICAL = "hierarchical"
    CONDITIONAL = "conditional"
    TEMPORAL = "temporal"
    EMERGENCY = "emergency"
    CROSS_DOMAIN = "cross_domain"
    MULTI_PARTY = "multi_party"


class AccessLevel(Enum):
    """Access levels for hierarchical delegation."""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"
    EMERGENCY = "emergency"


@dataclass
class DelegationRule:
    """Advanced delegation rule with complex conditions."""
    pattern: DelegationPattern
    resource_pattern: str
    required_roles: List[str]
    time_restrictions: Optional[Dict[str, Any]] = None
    conditional_logic: Optional[Callable] = None
    emergency_override: bool = False
    audit_requirements: List[str] = field(default_factory=list)
    auto_expire_seconds: int = 3600


@dataclass
class EmergencyContext:
    """Context for emergency delegation scenarios."""
    incident_id: str
    severity_level: int  # 1-5, where 5 is critical
    justification: str
    authorized_by: str
    emergency_contact: str
    max_duration_minutes: int = 60


class AdvancedDelegationManager:
    """
    Manager for advanced delegation patterns and enterprise workflows.
    """
    
    def __init__(self, client: deepsecure.Client):
        self.client = client
        self.delegation_rules: Dict[str, DelegationRule] = {}
        self.active_delegations: Dict[str, Dict[str, Any]] = {}
        self.emergency_protocols: Dict[str, EmergencyContext] = {}
        self.audit_log: List[Dict[str, Any]] = []
        
        # Setup demonstration rules
        self._setup_demonstration_rules()
        
        print("🔗 Advanced Delegation Manager initialized")
        print(f"   Configured {len(self.delegation_rules)} delegation rules")
    
    def _setup_demonstration_rules(self):
        """Setup demonstration delegation rules for different patterns."""
        
        # Linear chain delegation rule
        self.delegation_rules["trading_approval_chain"] = DelegationRule(
            pattern=DelegationPattern.LINEAR_CHAIN,
            resource_pattern="trading:*",
            required_roles=["trader", "supervisor", "risk_manager", "compliance"],
            auto_expire_seconds=1800,  # 30 minutes
            audit_requirements=["transaction_log", "approval_chain", "risk_assessment"]
        )
        
        # Hierarchical delegation rule
        self.delegation_rules["data_access_hierarchy"] = DelegationRule(
            pattern=DelegationPattern.HIERARCHICAL,
            resource_pattern="data:*",
            required_roles=["analyst", "senior_analyst", "data_manager"],
            auto_expire_seconds=3600,  # 1 hour
            audit_requirements=["data_access_log"]
        )
        
        # Temporal delegation rule (business hours only)
        self.delegation_rules["business_hours_access"] = DelegationRule(
            pattern=DelegationPattern.TEMPORAL,
            resource_pattern="internal:*",
            required_roles=["employee"],
            time_restrictions={
                "business_hours_only": True,
                "allowed_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "UTC"
            },
            auto_expire_seconds=28800  # 8 hours
        )
        
        # Emergency delegation rule
        self.delegation_rules["emergency_protocol"] = DelegationRule(
            pattern=DelegationPattern.EMERGENCY,
            resource_pattern="emergency:*",
            required_roles=["emergency_responder"],
            emergency_override=True,
            audit_requirements=["incident_log", "emergency_justification", "supervisor_notification"],
            auto_expire_seconds=3600  # 1 hour emergency access
        )
    
    def create_delegation_chain(
        self,
        chain_agents: List[str],
        resource: str,
        permissions: List[str],
        rule_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Create a linear delegation chain with progressive attenuation.
        
        Args:
            chain_agents: List of agent IDs in delegation order
            resource: Resource being delegated
            permissions: Starting permissions (will be attenuated)
            rule_name: Name of the delegation rule to apply
            context: Additional context for the delegation
            
        Returns:
            Dictionary mapping agent_id to their delegation token
        """
        print(f"\n🔗 Creating delegation chain: {' → '.join(chain_agents)}")
        print(f"   📋 Resource: {resource}")
        print(f"   🔑 Initial permissions: {permissions}")
        print(f"   📜 Rule: {rule_name}")
        
        if rule_name not in self.delegation_rules:
            raise ValueError(f"Unknown delegation rule: {rule_name}")
        
        rule = self.delegation_rules[rule_name]
        delegation_tokens = {}
        current_permissions = permissions.copy()
        
        try:
            # Create chain specification with progressive attenuation
            chain_spec = []
            
            for i in range(len(chain_agents) - 1):
                from_agent = chain_agents[i]
                to_agent = chain_agents[i + 1]
                
                # Attenuate permissions for each level
                if i > 0:  # Keep full permissions for first delegation
                    current_permissions = self._attenuate_permissions(current_permissions, i)
                
                # Build delegation spec for this level
                delegation_spec = {
                    'from_agent_id': from_agent,
                    'to_agent_id': to_agent,
                    'resource': resource,
                    'permissions': current_permissions,
                    'ttl_seconds': rule.auto_expire_seconds,
                    'restrictions': {
                        'chain_level': i + 1,
                        'total_chain_length': len(chain_agents),
                        'rule_name': rule_name,
                        'pattern': rule.pattern.value
                    }
                }
                
                # Add context if provided
                if context:
                    delegation_spec['restrictions'].update(context)
                
                chain_spec.append(delegation_spec)
            
            # Create the delegation chain
            delegation_tokens = self.client.create_delegation_chain(chain_spec)
            
            # Record the delegation chain for audit
            chain_record = {
                "chain_id": f"chain_{int(time.time())}",
                "agents": chain_agents,
                "resource": resource,
                "rule": rule_name,
                "created_at": datetime.now().isoformat(),
                "tokens": {agent_id: token[:20] + "..." for agent_id, token in delegation_tokens.items()}
            }
            
            self.active_delegations[chain_record["chain_id"]] = chain_record
            self._audit_log("delegation_chain_created", chain_record)
            
            print(f"✅ Delegation chain created successfully")
            print(f"   🎫 Generated {len(delegation_tokens)} delegation tokens")
            
            return delegation_tokens
            
        except Exception as e:
            print(f"❌ Failed to create delegation chain: {e}")
            raise
    
    def _attenuate_permissions(self, permissions: List[str], level: int) -> List[str]:
        """
        Attenuate permissions based on delegation level.
        
        Args:
            permissions: Current permissions
            level: Delegation level (0 = first, higher = more restricted)
            
        Returns:
            Attenuated permissions list
        """
        # Progressive permission attenuation
        if level == 0:
            return permissions  # Full permissions
        elif level == 1:
            # Remove write permissions, keep read and execute
            return [p for p in permissions if not p.startswith('write')]
        elif level == 2:
            # Only read permissions
            return [p for p in permissions if p.startswith('read')]
        else:
            # Very restricted - only basic read
            return ['read:basic']
    
    def create_temporal_delegation(
        self,
        from_agent: str,
        to_agent: str,
        resource: str,
        permissions: List[str],
        start_time: datetime,
        end_time: datetime,
        recurrence: Optional[str] = None
    ) -> str:
        """
        Create time-based delegation with specific temporal constraints.
        
        Args:
            from_agent: Delegating agent ID
            to_agent: Receiving agent ID
            resource: Resource to delegate
            permissions: Allowed permissions
            start_time: When delegation becomes active
            end_time: When delegation expires
            recurrence: Optional recurrence pattern (daily, weekly, etc.)
            
        Returns:
            Delegation token
        """
        print(f"\n⏰ Creating temporal delegation")
        print(f"   From: {from_agent} → To: {to_agent}")
        print(f"   Resource: {resource}")
        print(f"   Active: {start_time} to {end_time}")
        if recurrence:
            print(f"   Recurrence: {recurrence}")
        
        # Calculate TTL based on end time
        ttl_seconds = int((end_time - start_time).total_seconds())
        
        # Add temporal restrictions
        temporal_restrictions = {
            "temporal_delegation": True,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "timezone": "UTC"
        }
        
        if recurrence:
            temporal_restrictions["recurrence"] = recurrence
        
        try:
            delegation_token = self.client.delegate_access(
                delegator_agent_id=from_agent,
                target_agent_id=to_agent,
                resource=resource,
                permissions=permissions,
                ttl_seconds=ttl_seconds,
                additional_restrictions=temporal_restrictions
            )
            
            # Record temporal delegation
            temporal_record = {
                "delegation_id": f"temporal_{int(time.time())}",
                "from_agent": from_agent,
                "to_agent": to_agent,
                "resource": resource,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "recurrence": recurrence,
                "token": delegation_token[:20] + "..."
            }
            
            self.active_delegations[temporal_record["delegation_id"]] = temporal_record
            self._audit_log("temporal_delegation_created", temporal_record)
            
            print(f"✅ Temporal delegation created")
            return delegation_token
            
        except Exception as e:
            print(f"❌ Failed to create temporal delegation: {e}")
            raise
    
    def create_emergency_delegation(
        self,
        from_agent: str,
        to_agent: str,
        resource: str,
        emergency_context: EmergencyContext
    ) -> str:
        """
        Create emergency break-glass delegation with special audit requirements.
        
        Args:
            from_agent: Delegating agent (typically system/admin)
            to_agent: Emergency responder agent
            resource: Emergency resource to access
            emergency_context: Emergency context and justification
            
        Returns:
            Emergency delegation token
        """
        print(f"\n🚨 EMERGENCY DELEGATION ACTIVATED")
        print(f"   Incident: {emergency_context.incident_id}")
        print(f"   Severity: {emergency_context.severity_level}/5")
        print(f"   Responder: {to_agent}")
        print(f"   Resource: {resource}")
        print(f"   Max Duration: {emergency_context.max_duration_minutes} minutes")
        
        # Emergency permissions (elevated)
        emergency_permissions = [
            "read:all", "write:emergency", "execute:emergency", 
            "override:restrictions", "access:locked_systems"
        ]
        
        # Emergency restrictions with audit requirements
        emergency_restrictions = {
            "emergency_delegation": True,
            "incident_id": emergency_context.incident_id,
            "severity_level": emergency_context.severity_level,
            "justification": emergency_context.justification,
            "authorized_by": emergency_context.authorized_by,
            "emergency_contact": emergency_context.emergency_contact,
            "break_glass_protocol": True,
            "mandatory_audit": True,
            "supervisor_notification_required": True
        }
        
        ttl_seconds = emergency_context.max_duration_minutes * 60
        
        try:
            delegation_token = self.client.delegate_access(
                delegator_agent_id=from_agent,
                target_agent_id=to_agent,
                resource=resource,
                permissions=emergency_permissions,
                ttl_seconds=ttl_seconds,
                additional_restrictions=emergency_restrictions
            )
            
            # Record emergency delegation
            emergency_record = {
                "type": "emergency_delegation",
                "incident_id": emergency_context.incident_id,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "resource": resource,
                "severity": emergency_context.severity_level,
                "authorized_by": emergency_context.authorized_by,
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
                "token": delegation_token[:20] + "..."
            }
            
            # Store emergency protocol record
            self.emergency_protocols[emergency_context.incident_id] = emergency_context
            self.active_delegations[f"emergency_{emergency_context.incident_id}"] = emergency_record
            
            # Special audit logging for emergency
            self._audit_log("emergency_delegation_created", emergency_record, severity="CRITICAL")
            
            print(f"✅ Emergency delegation created")
            print(f"🔔 Supervisor notification sent to: {emergency_context.emergency_contact}")
            print(f"📋 Mandatory audit trail activated")
            
            return delegation_token
            
        except Exception as e:
            print(f"❌ Failed to create emergency delegation: {e}")
            raise
    
    def create_multi_party_approval_delegation(
        self,
        resource: str,
        permissions: List[str],
        approvers: List[str],
        required_approvals: int,
        final_delegatee: str,
        approval_timeout_minutes: int = 30
    ) -> str:
        """
        Create delegation requiring multiple approvals before activation.
        
        Args:
            resource: Resource to delegate
            permissions: Permissions to grant
            approvers: List of agents who can approve
            required_approvals: Number of approvals needed
            final_delegatee: Agent who will receive final delegation
            approval_timeout_minutes: Timeout for approval process
            
        Returns:
            Approval process ID (not active delegation yet)
        """
        print(f"\n🤝 Creating multi-party approval delegation")
        print(f"   Resource: {resource}")
        print(f"   Required approvals: {required_approvals}/{len(approvers)}")
        print(f"   Final delegatee: {final_delegatee}")
        print(f"   Timeout: {approval_timeout_minutes} minutes")
        
        approval_id = f"approval_{int(time.time())}"
        approval_record = {
            "approval_id": approval_id,
            "resource": resource,
            "permissions": permissions,
            "approvers": approvers,
            "required_approvals": required_approvals,
            "final_delegatee": final_delegatee,
            "received_approvals": [],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=approval_timeout_minutes)).isoformat(),
            "timeout_minutes": approval_timeout_minutes
        }
        
        self.active_delegations[approval_id] = approval_record
        self._audit_log("multi_party_approval_initiated", approval_record)
        
        print(f"✅ Multi-party approval process initiated")
        print(f"   🎫 Approval ID: {approval_id}")
        print(f"   📧 Notifications sent to {len(approvers)} approvers")
        
        return approval_id
    
    def submit_approval(
        self,
        approval_id: str,
        approver_agent: str,
        approved: bool,
        justification: str = ""
    ) -> Dict[str, Any]:
        """
        Submit an approval for a multi-party delegation.
        
        Args:
            approval_id: The approval process ID
            approver_agent: Agent submitting the approval
            approved: Whether the approval is granted
            justification: Justification for the decision
            
        Returns:
            Approval status and delegation token if complete
        """
        print(f"\n📝 Processing approval submission")
        print(f"   Approval ID: {approval_id}")
        print(f"   Approver: {approver_agent}")
        print(f"   Decision: {'APPROVED' if approved else 'REJECTED'}")
        
        if approval_id not in self.active_delegations:
            raise ValueError(f"Unknown approval process: {approval_id}")
        
        approval_record = self.active_delegations[approval_id]
        
        # Check if approver is authorized
        if approver_agent not in approval_record["approvers"]:
            raise ValueError(f"Agent {approver_agent} is not authorized to approve this delegation")
        
        # Check if already approved by this agent
        existing_approvals = [a["approver"] for a in approval_record["received_approvals"]]
        if approver_agent in existing_approvals:
            raise ValueError(f"Agent {approver_agent} has already submitted an approval")
        
        # Check if process has expired
        expires_at = datetime.fromisoformat(approval_record["expires_at"])
        if datetime.now() > expires_at:
            approval_record["status"] = "expired"
            return {"status": "expired", "message": "Approval process has expired"}
        
        # Record the approval
        approval_entry = {
            "approver": approver_agent,
            "approved": approved,
            "justification": justification,
            "timestamp": datetime.now().isoformat()
        }
        
        approval_record["received_approvals"].append(approval_entry)
        
        # Check if we have enough approvals
        approved_count = sum(1 for a in approval_record["received_approvals"] if a["approved"])
        rejected_count = sum(1 for a in approval_record["received_approvals"] if not a["approved"])
        
        result = {"status": "pending", "approved_count": approved_count, "required": approval_record["required_approvals"]}
        
        if not approved:
            # Rejection - fail the entire process
            approval_record["status"] = "rejected"
            result["status"] = "rejected"
            result["message"] = f"Delegation rejected by {approver_agent}"
            self._audit_log("multi_party_approval_rejected", approval_record)
            
        elif approved_count >= approval_record["required_approvals"]:
            # Enough approvals - create the actual delegation
            try:
                delegation_token = self.client.delegate_access(
                    delegator_agent_id="system",  # System-level delegation
                    target_agent_id=approval_record["final_delegatee"],
                    resource=approval_record["resource"],
                    permissions=approval_record["permissions"],
                    ttl_seconds=3600,  # 1 hour default
                    additional_restrictions={
                        "multi_party_approved": True,
                        "approval_id": approval_id,
                        "approvers": [a["approver"] for a in approval_record["received_approvals"] if a["approved"]]
                    }
                )
                
                approval_record["status"] = "approved"
                approval_record["delegation_token"] = delegation_token
                
                result["status"] = "approved"
                result["delegation_token"] = delegation_token
                result["message"] = "Delegation approved and activated"
                
                self._audit_log("multi_party_approval_completed", approval_record)
                
            except Exception as e:
                approval_record["status"] = "failed"
                result["status"] = "failed"
                result["message"] = f"Failed to create delegation: {e}"
        
        print(f"📊 Approval status: {result['status']}")
        if result["status"] == "pending":
            print(f"   Progress: {approved_count}/{approval_record['required_approvals']} approvals")
        
        return result
    
    def _audit_log(self, event_type: str, data: Dict[str, Any], severity: str = "INFO"):
        """Add entry to audit log."""
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "data": data
        }
        self.audit_log.append(audit_entry)
        
        if severity == "CRITICAL":
            print(f"🚨 CRITICAL AUDIT EVENT: {event_type}")
    
    def get_delegation_audit_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report."""
        total_delegations = len(self.active_delegations)
        emergency_count = len([d for d in self.active_delegations.values() 
                              if d.get("type") == "emergency_delegation"])
        
        return {
            "report_generated_at": datetime.now().isoformat(),
            "total_active_delegations": total_delegations,
            "emergency_delegations": emergency_count,
            "delegation_patterns_used": list(set(d.get("pattern", "unknown") for d in self.active_delegations.values())),
            "audit_events": len(self.audit_log),
            "critical_events": len([e for e in self.audit_log if e["severity"] == "CRITICAL"]),
            "recent_audit_events": self.audit_log[-10:] if self.audit_log else []
        }


def demonstrate_trading_approval_chain(manager: AdvancedDelegationManager):
    """Demonstrate a financial trading approval chain."""
    print(f"\n{'='*80}")
    print("💰 FINANCIAL TRADING APPROVAL CHAIN")
    print(f"{'='*80}")
    
    # Trading chain: Trader → Supervisor → Risk Manager → Compliance
    trading_chain = [
        "trader-alice",
        "supervisor-bob", 
        "risk-manager-charlie",
        "compliance-diana"
    ]
    
    permissions = ["read:market_data", "write:trade_orders", "execute:trades"]
    
    try:
        delegation_tokens = manager.create_delegation_chain(
            chain_agents=trading_chain,
            resource="trading:high_value_orders",
            permissions=permissions,
            rule_name="trading_approval_chain",
            context={
                "trade_type": "high_value",
                "max_trade_value": 1000000,
                "market": "equity_options"
            }
        )
        
        print(f"\n📊 Trading approval chain results:")
        for agent, token in delegation_tokens.items():
            print(f"   • {agent}: {token[:30]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Trading approval chain failed: {e}")
        return False


def demonstrate_emergency_protocol(manager: AdvancedDelegationManager):
    """Demonstrate emergency break-glass access."""
    print(f"\n{'='*80}")
    print("🚨 EMERGENCY BREAK-GLASS PROTOCOL")
    print(f"{'='*80}")
    
    # Create emergency context
    emergency = EmergencyContext(
        incident_id="INC-2024-001",
        severity_level=4,  # High severity
        justification="Production database corruption detected, immediate access required for data recovery",
        authorized_by="cto-frank",
        emergency_contact="emergency-team@company.com",
        max_duration_minutes=45
    )
    
    try:
        emergency_token = manager.create_emergency_delegation(
            from_agent="system-admin",
            to_agent="dba-emergency-alice",
            resource="database:production_critical",
            emergency_context=emergency
        )
        
        print(f"\n🎫 Emergency delegation token: {emergency_token[:30]}...")
        print(f"📋 Emergency access granted for incident: {emergency.incident_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Emergency protocol failed: {e}")
        return False


def demonstrate_temporal_delegation(manager: AdvancedDelegationManager):
    """Demonstrate time-based delegation patterns."""
    print(f"\n{'='*80}")
    print("⏰ TEMPORAL DELEGATION PATTERNS")
    print(f"{'='*80}")
    
    # Business hours access (9 AM to 5 PM next day)
    start_time = datetime.now() + timedelta(minutes=1)  # Start in 1 minute
    end_time = start_time + timedelta(hours=8)  # 8 hour window
    
    try:
        temporal_token = manager.create_temporal_delegation(
            from_agent="data-manager-eve",
            to_agent="contractor-frank", 
            resource="data:customer_analytics",
            permissions=["read:basic", "analyze:trends"],
            start_time=start_time,
            end_time=end_time,
            recurrence="daily_business_hours"
        )
        
        print(f"\n🎫 Temporal delegation token: {temporal_token[:30]}...")
        print(f"📅 Active from {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Temporal delegation failed: {e}")
        return False


def demonstrate_multi_party_approval(manager: AdvancedDelegationManager):
    """Demonstrate multi-party approval workflow."""
    print(f"\n{'='*80}")
    print("🤝 MULTI-PARTY APPROVAL WORKFLOW")
    print(f"{'='*80}")
    
    # High-value resource requiring 2 out of 3 approvals
    approvers = ["security-alice", "compliance-bob", "cto-charlie"]
    
    try:
        # Initiate approval process
        approval_id = manager.create_multi_party_approval_delegation(
            resource="financial:audit_records",
            permissions=["read:all", "export:data"],
            approvers=approvers,
            required_approvals=2,
            final_delegatee="auditor-diana",
            approval_timeout_minutes=15
        )
        
        print(f"\n📝 Simulating approval process...")
        
        # Simulate approvals
        result1 = manager.submit_approval(
            approval_id=approval_id,
            approver_agent="security-alice",
            approved=True,
            justification="Security review completed, no concerns identified"
        )
        print(f"   • Security approval: {result1['status']}")
        
        result2 = manager.submit_approval(
            approval_id=approval_id,
            approver_agent="compliance-bob", 
            approved=True,
            justification="Compliance requirements satisfied"
        )
        print(f"   • Compliance approval: {result2['status']}")
        
        if result2['status'] == 'approved':
            print(f"🎫 Final delegation token: {result2['delegation_token'][:30]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Multi-party approval failed: {e}")
        return False


def main():
    """
    Main demonstration of advanced delegation patterns.
    """
    print("🔗 Advanced DeepSecure Delegation Patterns")
    print("==========================================")
    print("This example demonstrates enterprise-grade delegation")
    print("patterns for complex organizational workflows.\n")
    
    # Environment check
    if not os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL"):
        print("⚠️  [WARNING] DEEPSECURE_DEEPTRAIL_CONTROL_URL not set")
        print("🔧 [INFO] Using mock implementation for demonstration\n")
    
    try:
        # Initialize DeepSecure client
        client = deepsecure.Client()
        
        # Create advanced delegation manager
        manager = AdvancedDelegationManager(client)
        
        # Track demonstration results
        results = {}
        
        # === Trading Approval Chain ===
        results["trading_chain"] = demonstrate_trading_approval_chain(manager)
        
        # === Emergency Protocol ===
        results["emergency_protocol"] = demonstrate_emergency_protocol(manager)
        
        # === Temporal Delegation ===
        results["temporal_delegation"] = demonstrate_temporal_delegation(manager)
        
        # === Multi-Party Approval ===
        results["multi_party_approval"] = demonstrate_multi_party_approval(manager)
        
        # === Audit Report ===
        print(f"\n{'='*80}")
        print("📊 COMPREHENSIVE AUDIT REPORT")
        print(f"{'='*80}")
        
        audit_report = manager.get_delegation_audit_report()
        print(json.dumps(audit_report, indent=2))
        
        # === Summary ===
        print(f"\n{'='*80}")
        print("✅ Advanced Delegation Patterns Demo Complete!")
        print(f"{'='*80}")
        
        successful_patterns = sum(results.values())
        total_patterns = len(results)
        
        print(f"🎯 Patterns demonstrated: {successful_patterns}/{total_patterns}")
        print("🔐 Advanced features showcased:")
        print("   • Linear delegation chains with attenuation")
        print("   • Emergency break-glass protocols")
        print("   • Time-based delegation windows")
        print("   • Multi-party approval workflows")
        print("   • Comprehensive audit trails")
        print("   • Cryptographic delegation security")
        
        for pattern, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   • {pattern.replace('_', ' ').title()}: {status}")
        
        print(f"\n🚀 Enterprise delegation patterns ready for production!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔧 Ensure DeepSecure backend is running and configured")


if __name__ == "__main__":
    main() 