# DeepSecure CLI Architecture

## Project Structure

```
deepsecure/
├── pyproject.toml
├── setup.py
├── deepsecure/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py               # Entry point and CLI app definition
│   │   ├── commands/             # Command group implementations
│   │   │   ├── __init__.py
│   │   │   ├── vault.py          # Vault management commands
│   │   │   ├── audit.py          # Audit-related commands
│   │   │   ├── policy.py         # Policy definition and enforcement
│   │   │   ├── risk.py           # Risk assessment commands
│   │   │   ├── scan.py           # Scanner orchestration
│   │   │   ├── sandbox.py        # Secure execution environment
│   │   │   └── ...
│   │   └── utils/                # CLI-specific utilities
│   │       ├── __init__.py
│   │       ├── config.py         # Configuration loading/management
│   │       ├── output.py         # Output formatting
│   │       └── errors.py         # Error handling and custom exceptions
│   ├── core/                     # Core business logic
│   │   ├── __init__.py
│   │   ├── vault/                # Credential management services
│   │   ├── audit/                # Audit logging implementation
│   │   ├── policy/               # Policy enforcement engine
│   │   ├── risk/                 # Risk scoring services
│   │   └── ...
│   └── config/                   # Default configurations
│       ├── default_config.yaml
│       └── schemas/              # JSON schemas for validation
└── tests/
    ├── unit/                     # Unit tests
    ├── integration/              # Integration tests
    └── e2e/                      # End-to-end CLI tests
```

## Key Components

### 1. Entry Point (main.py)
```python
import typer
from deepsecure.cli.commands import vault, audit, policy, risk, scan

app = typer.Typer(name="deepsecure", help="DeepSecure CLI for AI agent security")

# Mount subcommands
app.add_typer(vault.app, name="vault")
app.add_typer(audit.app, name="audit")
app.add_typer(policy.app, name="policy")
app.add_typer(risk.app, name="risk")
app.add_typer(scan.app, name="scan")
# ...others

if __name__ == "__main__":
    app()
```

### 2. Command Implementation (vault.py)
```python
import typer
from typing import Optional
from deepsecure.core.vault import VaultClient
from deepsecure.cli.utils.config import get_config
from deepsecure.cli.utils.output import output_formatter

app = typer.Typer(help="Manage secure credentials for AI agents")

@app.command("issue")
def issue_credential(
    agent_id: str = typer.Argument(..., help="Agent identifier"),
    scope: str = typer.Option("default", help="Credential scope"),
    expiry: Optional[str] = typer.Option(None, help="Expiry time (e.g. 30d, 24h)"),
    output_format: str = typer.Option("text", help="Output format (text|json)")
):
    """Issue a new credential for an AI agent."""
    config = get_config()
    vault_client = VaultClient(config.vault)
    
    try:
        credential = vault_client.issue_credential(agent_id, scope, expiry)
        output_formatter(credential, output_format)
    except Exception as e:
        typer.echo(f"Error issuing credential: {str(e)}", err=True)
        raise typer.Exit(code=1)
```

### 3. Configuration Management (config.py)
```python
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel

class VaultConfig(BaseModel):
    address: str
    token: str = ""
    ca_cert: str = ""

class Config(BaseModel):
    vault: VaultConfig
    audit_log: str = "~/.deepsecure/audit.log"
    policy_dir: str = "~/.deepsecure/policies"
    # ... other config sections

def get_config() -> Config:
    """Load configuration from multiple sources in priority order."""
    config_data = {}
    
    # 1. Default config
    default_config_path = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
    if default_config_path.exists():
        with open(default_config_path) as f:
            config_data.update(yaml.safe_load(f))
    
    # 2. Global config file
    global_config_path = Path.home() / ".deepsecure" / "config.yaml"
    if global_config_path.exists():
        with open(global_config_path) as f:
            config_data.update(yaml.safe_load(f))
    
    # 3. Project config (if exists)
    project_config_path = Path.cwd() / ".deepsecure" / "config.yaml"
    if project_config_path.exists():
        with open(project_config_path) as f:
            config_data.update(yaml.safe_load(f))
    
    # 4. Environment variables (e.g., DEEPSECURE_VAULT_ADDRESS)
    for key, value in os.environ.items():
        if key.startswith("DEEPSECURE_"):
            parts = key[11:].lower().split("_")
            current = config_data
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
    
    return Config(**config_data)
```

### 4. Core Service Implementation (VaultClient)
```python
from typing import Optional, Dict, Any
import requests

class VaultClient:
    def __init__(self, config):
        self.address = config.address
        self.token = config.token
        self.ca_cert = config.ca_cert
    
    def issue_credential(self, agent_id: str, scope: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Issue a new credential for an agent."""
        # Implementation depends on backend (local file, HashiCorp Vault, etc.)
        # This is just a placeholder for the real implementation
        headers = {"X-Vault-Token": self.token} if self.token else {}
        data = {
            "agent_id": agent_id,
            "scope": scope
        }
        if expiry:
            data["expiry"] = expiry
            
        response = requests.post(
            f"{self.address}/v1/deepsecure/issue",
            headers=headers,
            json=data,
            verify=self.ca_cert if self.ca_cert else True
        )
        response.raise_for_status()
        return response.json()
```

## Implementation Strategy

1. **Phase 1: Core Framework**
   - Setup project structure and CLI framework
   - Implement configuration management
   - Create simple versions of key command groups (vault, scan)
   - Add proper error handling and output formatting

2. **Phase 2: Security Features**
   - Implement policy engine with validation
   - Add audit logging capabilities
   - Develop risk scoring module

3. **Phase 3: Advanced Features**
   - Sandbox environment for secure execution
   - Server hardening utilities
   - Deployment assistance tools

4. **Phase 4: Integration**
   - Connect with external services (e.g., HashiCorp Vault)
   - IDE integration utilities
   - Real-time scanning capabilities

## Security Considerations

- Store sensitive configs (vault tokens) in secure storage
- Use environment variables for sensitive data in CI/CD
- Implement proper permission checks before operations
- Validate all inputs, especially when parsing user config
- Securely handle credentials (avoid logging, clear from memory)
- Use TLS for all external API connections