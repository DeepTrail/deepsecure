# DeepSecure CLI

DeepSecure CLI is the command-line security control plane for developers and security engineers building secure AI agents, MCP servers, and applications.

[![PyPI version](https://badge.fury.io/py/deepsecure-cli.svg)](https://badge.fury.io/py/deepsecure-cli)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Features

DeepSecure CLI offers a comprehensive suite of tools for securing AI agents, MCP servers, and applications:

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

```bash
# Show version
deepsecure version

# Issue a credential
deepsecure vault issue --scope=db:readonly --ttl=5m

# Apply a policy
deepsecure policy apply --identity=agent1 --policy=./policy.yaml

# Get a risk score
deepsecure risk score --identity=agent1
```

## Command Overview

| Command Group | Description | Commands | Responsibilities |
|---------------|-------------|----------|------------------|
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
