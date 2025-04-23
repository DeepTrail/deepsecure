# DeepSecure CLI

CLI for secure AI agent development, credential management, policy enforcement, and runtime protection.

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

```bash
# Install from PyPI
pip install deepsecure-cli

# Or install in development mode from source
git clone https://github.com/yourusername/deepsecure-cli
cd deepsecure-cli
pip install -e .
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

| Command Group | Description |
|---------------|-------------|
| vault         | Credential management |
| audit         | Behavior monitoring |
| risk          | Risk assessment |
| policy        | Policy management |
| sandbox       | Secure execution |
| scan          | Credential scanning |
| harden        | Server hardening |
| deploy        | Secure deployment |
| scorecard     | Security assessment |
| inventory     | Resource tracking |
| ide           | Development tools |

See [DeepSecure Documentation](https://example.com) for complete usage details.

## Development

```bash
# Setup development environment
pip install -e ".[dev]"

# Run tests
pytest

# Build package
python -m build
```

## License

MIT License - See LICENSE file for details.
