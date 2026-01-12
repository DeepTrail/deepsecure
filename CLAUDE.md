# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeepSecure is a security platform that provides Identity-as-Code for AI agents, enabling them to fetch their own ephemeral credentials programmatically instead of using static API keys. The project consists of a Python CLI/SDK and backend services that implement a dual-service gateway architecture.

## Development Commands

### Environment Setup
```bash
# Install development dependencies
make install-dev
# or traditionally
make install-traditional

# Setup development environment
make setup
```

### Testing
```bash
# Run all tests
make test
pytest

# Run tests with coverage
make test-cov
pytest --cov=deepsecure --cov-report=html --cov-report=term

# Run specific test markers
pytest -m e2e          # End-to-end tests (require live backend)
pytest -m integration  # Integration tests
```

### Code Quality
```bash
# Run linting
make lint
ruff check .
mypy deepsecure/

# Format code
make format
black .
isort .

# Security scanning
make security
bandit -r deepsecure/
safety check

# Run all quality checks
make check-all
```

### Build and Package
```bash
# Build package
make build
./scripts/build_package.sh

# Clean build artifacts
make clean
```

## Architecture Overview

### Core Module Structure
- **`deepsecure/_core/`**: Internal implementation modules
  - `client.py`: High-level client services wrapping core functionalities
  - `base_client.py`: Base HTTP client with authentication
  - `vault_client.py`: Secret management operations
  - `agent_client.py`: Agent identity management
  - `identity_manager.py`: Agent identity and key management
  - `crypto/key_manager.py`: Cryptographic key operations
  - `config.py`: Configuration management

- **`deepsecure/`**: Public API layer
  - `client.py`: Main SDK client (uses _core modules)
  - `commands/`: CLI command implementations
  - `integrations/`: Framework integrations (LangChain, CrewAI)
  - `resources/`: Resource objects (Agent, Secret)

### Backend Services
- **`deeptrail-control/`**: Control plane (agent management, authentication, policies)
- **`deeptrail-gateway/`**: Data plane (API proxy with secret injection)

### Key Patterns
1. **Dual Client Architecture**: 
   - `deepsecure.Client` (public SDK) wraps `deepsecure._core.client` (internal)
   - Core modules handle low-level operations, public client provides clean API

2. **Identity Provider Pattern**:
   - Multiple identity providers (Keyring, Kubernetes, AWS)
   - Agents bootstrap identity from platform-native mechanisms

3. **Gateway Architecture**:
   - External API calls routed through gateway with automatic secret injection
   - JWT-based authentication between services

## Testing Strategy

### Test Organization
- **`tests/_core/`**: Core module unit tests (client, identity_manager, environment_detection)
- **`tests/commands/`**: CLI command tests (agent, auth, policy, vault)
- **`tests/sdk/`**: SDK-level tests (gateway requests, client properties, credentials)
- **`tests/test_examples.py`**: Example script validation
- **`tests/docs/`**: Documentation validation (README snippets)
- **End-to-end tests**: Marked with `@pytest.mark.e2e`, require live backend
- **Integration tests**: Marked with `@pytest.mark.integration`

### Running Specific Tests
```bash
# Run single test file
pytest tests/test_sdk_client.py

# Run tests by marker
pytest -m e2e -v          # End-to-end tests only
pytest -m integration -v  # Integration tests only

# Run tests with specific patterns
pytest -k "test_agent" -v  # All tests with 'agent' in name
```

### Backend Dependencies
Many tests require the backend services running:
```bash
# Start backend services (includes PostgreSQL and Redis dependencies)
docker compose up deeptrail-control deeptrail-gateway -d

# Start with dependencies (full stack)
docker compose up db redis deeptrail-control deeptrail-gateway -d

# Verify services
curl http://localhost:8000/health  # Control plane
curl http://localhost:8002/health  # Gateway

# View service logs
docker compose logs deeptrail-control  # Control plane logs
docker compose logs deeptrail-gateway  # Gateway logs
```

## Configuration

### Environment Variables
```bash
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEBUG=true  # Enable verbose logging
```

### CLI Configuration
```bash
deepsecure configure set-url http://127.0.0.1:8001
deepsecure configure set-gateway-url http://localhost:8002
deepsecure configure set-token  # Prompts for token
```

## Development Workflow

### Making Changes
1. Core functionality changes go in `deepsecure/_core/`
2. Public API changes go in `deepsecure/client.py` or `deepsecure/`
3. CLI changes go in `deepsecure/commands/`
4. Always run `make check-all` before committing

### Adding New Features
1. Start with tests (TDD approach preferred)
2. Implement in appropriate core module
3. Expose through public client if needed
4. Add CLI commands if applicable
5. Update examples in `examples/` directory

### Security Considerations
- Never commit secrets or private keys
- All crypto operations use `ed25519` signatures
- Agent private keys stored in OS keyring by default
- JWT tokens used for service-to-service authentication
- Split-key architecture: client holds partial key, gateway holds partial key
- Redis used for gateway-side key storage in development

## Key File Locations

### Configuration Files
- `pyproject.toml`: Project metadata, dependencies, and tool configurations
- `docker-compose.yml`: Backend services orchestration (PostgreSQL, Redis, Control, Gateway)
- `pytest.ini`: Test configuration and markers
- `Makefile`: Development workflow automation

### Core Implementation
- `deepsecure/client.py`: Main public SDK client
- `deepsecure/_core/client.py`: Internal high-level client implementation
- `deepsecure/_core/base_client.py`: Base HTTP client with authentication
- `deepsecure/_core/identity_manager.py`: Agent identity and cryptographic operations
- `deepsecure/_core/crypto/key_manager.py`: Ed25519 key operations

### Service Ports (Development)
- **Control Plane**: http://localhost:8000 (mapped from container port 8001)
- **Gateway**: http://localhost:8002 (mapped from container port 8001)
- **PostgreSQL**: localhost:5434 (mapped from container port 5432)
- **Redis**: localhost:6380 (mapped from container port 6379)

### Common Debugging
```bash
# Check service status
docker compose ps

# Restart services if needed
docker compose restart deeptrail-control deeptrail-gateway

# Clean restart (removes volumes)
docker compose down -v && docker compose up -d

# Database access for debugging
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb

# Redis access for debugging
docker compose exec redis redis-cli
```