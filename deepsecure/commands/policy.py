'''Policy enforcement command implementations.'''

import typer
from rich.console import Console
from rich.table import Table
from typing import List, Optional
import uuid

from deepsecure.policy import policy as policy_client
from deepsecure.utils import handle_api_error

app = typer.Typer(help="Manage policies for agents.")
console = Console()

@app.command("create")
@handle_api_error
def policy_create(
    name: str = typer.Option(..., "--name", help="The name of the policy."),
    agent_id: str = typer.Option(..., "--agent-id", help="The UUID of the agent this policy applies to."),
    actions: List[str] = typer.Option(..., "--action", help="Action to allow (e.g., 'secret:read'). Can be specified multiple times."),
    resources: List[str] = typer.Option(..., "--resource", help="Resource ARN the policy applies to. Can be specified multiple times."),
    effect: str = typer.Option("allow", "--effect", help="The effect of the policy ('allow' or 'deny')."),
    description: Optional[str] = typer.Option(None, "--description", help="A description for the policy."),
):
    """
    Create a new policy to grant permissions to an agent.
    """
    # The SDK's PolicyClient doesn't currently support description, so we ignore it for now.
    # This can be added later.
    new_policy = policy_client.create(
        name=name,
        agent_id=agent_id,
        actions=actions,
        resources=resources,
        effect=effect,
    )
    console.print(f"Policy '{new_policy.name}' created with ID: {new_policy.id}")
    console.print(new_policy.dict())

@app.command("list")
@handle_api_error
def policy_list():
    """
    List all policies.
    """
    policies = policy_client.list()
    if not policies:
        console.print("No policies found.")
        return

    table = Table(title="Policies")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Agent ID")
    table.add_column("Effect")
    table.add_column("Actions")
    table.add_column("Resources")

    for p in policies:
        table.add_row(
            p.id,
            p.name,
            p.agent_id,
            p.effect,
            ", ".join(p.actions),
            ", ".join(p.resources),
        )
    console.print(table)


@app.command("get")
@handle_api_error
def policy_get(
    policy_id: str = typer.Argument(..., help="The ID of the policy to retrieve.")
):
    """
    Get details for a specific policy.
    """
    p = policy_client.get(policy_id)
    console.print(p.dict())

@app.command("delete")
@handle_api_error
def policy_delete(
    policy_id: str = typer.Argument(..., help="The ID of the policy to delete.")
):
    """
    Delete a policy.
    """
    result = policy_client.delete(policy_id)
    console.print(result.get("message", f"Policy {policy_id} deleted successfully."))


# Attestation Policy Subcommand Group
attestation_app = typer.Typer(help="Manage attestation policies for agent identity bootstrapping.")
app.add_typer(attestation_app, name="attestation")

@attestation_app.command("create-k8s")
@handle_api_error
def attestation_create_k8s(
    agent_name: str = typer.Option(..., "--agent-name", help="The name of the agent to associate with this policy."),
    namespace: str = typer.Option(..., "--namespace", help="The Kubernetes namespace."),
    service_account: str = typer.Option(..., "--service-account", help="The Kubernetes service account name."),
    description: Optional[str] = typer.Option(None, "--description", help="A description for the policy."),
):
    """
    Create a Kubernetes attestation policy.
    """
    policy_data = {
        "platform": "kubernetes",
        "agent_name": agent_name,
        "description": description or f"K8s attestation policy for {agent_name}",
        "k8s_namespace": namespace,
        "k8s_service_account": service_account,
    }
    new_policy = policy_client.create_attestation_policy(policy_data)
    console.print("Kubernetes attestation policy created successfully:")
    console.print(new_policy)

@attestation_app.command("create-aws")
@handle_api_error
def attestation_create_aws(
    agent_name: str = typer.Option(..., "--agent-name", help="The name of the agent to associate with this policy."),
    role_arn: str = typer.Option(..., "--role-arn", help="The AWS IAM role ARN."),
    description: Optional[str] = typer.Option(None, "--description", help="A description for the policy."),
):
    """
    Create an AWS attestation policy.
    """
    policy_data = {
        "platform": "aws",
        "agent_name": agent_name,
        "description": description or f"AWS attestation policy for {agent_name}",
        "policy_data": {
            "role_arn": role_arn,
        },
    }
    new_policy = policy_client.create_attestation_policy(policy_data)
    console.print("AWS attestation policy created successfully:")
    console.print(new_policy)

@attestation_app.command("create-azure")
@handle_api_error
def attestation_create_azure(
    agent_name: str = typer.Option(..., "--agent-name", help="The name of the agent to associate with this policy."),
    subscription_id: str = typer.Option(..., "--subscription-id", help="The Azure subscription ID."),
    resource_group: str = typer.Option(..., "--resource-group", help="The Azure resource group name."),
    vm_name: Optional[str] = typer.Option(None, "--vm-name", help="The Azure VM name (optional)."),
    description: Optional[str] = typer.Option(None, "--description", help="A description for the policy."),
):
    """
    Create an Azure managed identity attestation policy.
    """
    policy_data = {
        "platform": "azure_managed_identity",
        "agent_name": agent_name,
        "description": description or f"Azure attestation policy for {agent_name}",
        "policy_data": {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "vm_name": vm_name,
        },
    }
    new_policy = policy_client.create_attestation_policy(policy_data)
    console.print("Azure attestation policy created successfully:")
    console.print(new_policy)

@attestation_app.command("create-docker")
@handle_api_error
def attestation_create_docker(
    agent_name: str = typer.Option(..., "--agent-name", help="The name of the agent to associate with this policy."),
    image_name: str = typer.Option(..., "--image-name", help="The Docker image name."),
    image_digest: Optional[str] = typer.Option(None, "--image-digest", help="The Docker image digest (optional but recommended)."),
    container_name: Optional[str] = typer.Option(None, "--container-name", help="The container name pattern (optional)."),
    description: Optional[str] = typer.Option(None, "--description", help="A description for the policy."),
):
    """
    Create a Docker container attestation policy.
    """
    policy_data = {
        "platform": "docker_container",
        "agent_name": agent_name,
        "description": description or f"Docker attestation policy for {agent_name}",
        "policy_data": {
            "image_name": image_name,
            "image_digest": image_digest,
            "container_name": container_name,
        },
    }
    new_policy = policy_client.create_attestation_policy(policy_data)
    console.print("Docker attestation policy created successfully:")
    console.print(new_policy)

@attestation_app.command("list")
@handle_api_error
def attestation_list():
    """
    List all attestation policies.
    """
    policies = policy_client.list_attestation_policies()
    if not policies:
        console.print("No attestation policies found.")
        return

    table = Table(title="Attestation Policies")
    table.add_column("ID", style="cyan")
    table.add_column("Platform", style="green")
    table.add_column("Agent Name", style="yellow")
    table.add_column("Description")
    table.add_column("Policy Data")

    for p in policies:
        # Format policy data for display
        policy_data_str = ""
        if hasattr(p, 'policy_data') and p.policy_data:
            data_parts = []
            for key, value in p.policy_data.items():
                if value:  # Only show non-empty values
                    data_parts.append(f"{key}={value}")
            policy_data_str = ", ".join(data_parts)
        
        table.add_row(
            str(p.id),
            p.platform,
            p.agent_name,
            p.description or "N/A",
            policy_data_str,
        )
    console.print(table)

@attestation_app.command("get")
@handle_api_error
def attestation_get(
    policy_id: str = typer.Argument(..., help="The ID of the attestation policy to retrieve.")
):
    """
    Get details for a specific attestation policy.
    """
    policy = policy_client.get_attestation_policy(policy_id)
    console.print(f"Attestation Policy ID: {policy.id}")
    console.print(f"Platform: {policy.platform}")
    console.print(f"Agent Name: {policy.agent_name}")
    console.print(f"Description: {policy.description or 'N/A'}")
    
    if hasattr(policy, 'policy_data') and policy.policy_data:
        console.print("Policy Data:")
        for key, value in policy.policy_data.items():
            console.print(f"  {key}: {value}")
    
    if hasattr(policy, 'created_at') and policy.created_at:
        console.print(f"Created: {policy.created_at}")

@attestation_app.command("update")
@handle_api_error
def attestation_update(
    policy_id: str = typer.Argument(..., help="The ID of the attestation policy to update."),
    agent_name: Optional[str] = typer.Option(None, "--agent-name", help="New agent name."),
    description: Optional[str] = typer.Option(None, "--description", help="New description."),
):
    """
    Update an attestation policy.
    Note: Platform and core policy data cannot be changed. Create a new policy if needed.
    """
    update_data = {}
    if agent_name is not None:
        update_data["agent_name"] = agent_name
    if description is not None:
        update_data["description"] = description
    
    if not update_data:
        console.print("No updates specified. Use --agent-name or --description to update fields.")
        return
    
    updated_policy = policy_client.update_attestation_policy(policy_id, update_data)
    console.print("Attestation policy updated successfully:")
    console.print(updated_policy)

@attestation_app.command("delete")
@handle_api_error
def attestation_delete(
    policy_id: str = typer.Argument(..., help="The ID of the attestation policy to delete.")
):
    """
    Delete an attestation policy.
    """
    result = policy_client.delete_attestation_policy(policy_id)
    console.print(result.get("message", f"Attestation policy {policy_id} deleted successfully."))

@attestation_app.command("validate")
@handle_api_error
def attestation_validate(
    platform: str = typer.Option(..., "--platform", help="Platform to validate (kubernetes, aws, azure_managed_identity, docker_container)."),
    agent_name: str = typer.Option(..., "--agent-name", help="Agent name to check policy for."),
):
    """
    Validate that an attestation policy exists for the specified platform and agent.
    This helps verify bootstrap configuration before deployment.
    """
    console.print(f"Validating attestation policy for platform '{platform}' and agent '{agent_name}'...")
    
    # List all policies and check for matches
    policies = policy_client.list_attestation_policies()
    
    matching_policies = [
        p for p in policies 
        if p.platform == platform and p.agent_name == agent_name
    ]
    
    if matching_policies:
        console.print(f"✅ Found {len(matching_policies)} matching attestation policy(ies):")
        for policy in matching_policies:
            console.print(f"  - Policy ID: {policy.id}")
            console.print(f"    Description: {policy.description or 'N/A'}")
            if hasattr(policy, 'policy_data') and policy.policy_data:
                console.print("    Policy Data:")
                for key, value in policy.policy_data.items():
                    if value:
                        console.print(f"      {key}: {value}")
    else:
        console.print(f"❌ No attestation policy found for platform '{platform}' and agent '{agent_name}'")
        console.print("Available policies:")
        
        if policies:
            table = Table()
            table.add_column("Platform", style="green")
            table.add_column("Agent Name", style="yellow")
            table.add_column("ID", style="cyan")
            
            for p in policies:
                table.add_row(p.platform, p.agent_name, str(p.id))
            console.print(table)
        else:
            console.print("  No attestation policies configured.")
        
        console.print(f"\nTo create a policy for this configuration, use:")
        console.print(f"  deepsecure policy attestation create-{platform.replace('_', '-')} --agent-name {agent_name} [other options]") 