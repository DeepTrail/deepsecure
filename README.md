# DeepSecure CLI

DeepSecure CLI is the command-line security control plane for developers and security engineers building secure AI agents, MCP servers, and applications.

[![PyPI version](https://badge.fury.io/py/deepsecure-cli.svg)](https://badge.fury.io/py/deepsecure-cli)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Features

DeepSecure CLI offers a comprehensive suite of tools for securing AI agents, MCP servers, and applications:

- **🤖 Agent Identity Management:** Explicitly register, list, describe, and manage the lifecycle of AI agents.
- **🔐 Credential Management:** Issue, revoke, and rotate secure credentials
- **🧠 Identity Risk & Behavior Monitoring:** Audit trails and risk scoring
- **🛡️ Policy Enforcement:** Runtime policy application and sandboxing
- **🔎 Credential Scanning:** Detect leaks in code, configs, or memory
- **🧰 Server Hardening:** Secure MCP servers and deployment
- **📊 Security Scorecard:** Visibility and inventory management
- **🧩 IDE Integration:** Development workflow tools

## Installation

### From PyPI (Recommended)

The easiest way to install DeepSecure CLI is from PyPI:

```bash
pip install deepsecure-cli
```

To verify installation:

```bash
deepsecure version
```

### From Source

For development or to get the latest features:

```bash
git clone https://github.com/deepsecure/deepsecure-cli
cd deepsecure-cli
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

A typical workflow might involve registering an agent, then using its ID for other operations:

```bash
# Show CLI version
deepsecure version

# 1. Register a new AI agent (this will generate local keys if no public key is provided)
deepsecure agent register --name "MyWorkflowAgent" --description "Agent for automated tasks"
# (Note the agent-id output by this command, let's assume it's AGENT_ID_HERE)

# 2. List registered agents to see your new agent
deepsecure agent list

# 3. Issue a credential for the specific agent
# Replace AGENT_ID_HERE with the actual ID from the register command
deepsecure vault issue --agent-id "AGENT_ID_HERE" --scope="database:read" --ttl="10m"

# 4. Apply a policy to the agent (example)
# Replace AGENT_ID_HERE with the actual ID
deepsecure policy apply --agent-id "AGENT_ID_HERE" --policy-file "./path/to/agent_policy.yaml"

# 5. Get a risk score for the agent (example)
# Replace AGENT_ID_HERE with the actual ID
deepsecure risk score --agent-id "AGENT_ID_HERE"
```

## Command Overview

| Command Group | Description | Commands | Responsibilities |
|---------------|-------------|----------|------------------|
| agent     | Manage AI agent identities & lifecycle        | register, list, describe, delete| • Explicitly register agents with `credservice`<br>• Manage local agent identity keys<br>• List & describe agents<br>• Deactivate (soft delete) agents |
| vault | Credential management | issue, revoke, rotate | • Integrate with secrets backend (e.g. Vault API)<br>• Enforce TTL, scoping, audit logging |
| audit | Behavior monitoring | start, tail | • Launch or attach to audit service<br>• Stream & filter logs |
| risk | Risk assessment | score, list | • Compute/lookup risk profiles<br>• Format output (color-coded) |
| policy | Policy management | init, apply | • Generate policy templates<br>• Validate & push policies |
| sandbox | Secure execution | run | • Spin up isolated execution environment<br>• Enforce policy at runtime |
| scan | Credential scanning | local, live | • Static secret scanning<br>• In-memory/process scanning |
| harden | Server hardening | server | • Wrap existing MCP server binaries<br>• Inject TLS/auth middleware |
| deploy | Secure deployment | secure | • Build and push container images<br>• Auto-configure secure defaults |
| scorecard | Security assessment | — | • Evaluate project/agent against checklist<br>• Export report |
| inventory | Resource tracking | list | • Discover active AI services<br>• Highlight orphaned/serverless agents |
| ide | Development tools | init, suggest | • Scaffold IDE config (Cursor/VSCode)<br>• Lint & suggest best practices |

See [DeepSecure Documentation](https://deepsecure.dev/docs) for complete usage details.

## Development

```bash
# Setup development environment
pip install -e ".[dev]"

# Run tests
pytest

# Build package
python -m build

# Check package
twine check dist/*

# Upload to PyPI (maintainers only)
twine upload dist/*
```

## License

Apache License 2.0 - See LICENSE file for details.
