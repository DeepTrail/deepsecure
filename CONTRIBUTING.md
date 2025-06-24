# Contributing to DeepSecure

Thank you for your interest in contributing to DeepSecure! This guide will help you get started with development.

## Development Setup

DeepSecure supports multiple ways to set up your development environment. Choose the approach that best fits your workflow:

### 🚀 Quick Setup (Recommended)

For the fastest setup, use our automated script:

```bash
# Automated setup with modern dependencies
./scripts/setup_dev.sh

# OR using Make
make dev-setup
```

### 📦 Modern Approach (pyproject.toml)

Install using our modern optional dependency groups:

```bash
# Everything you need for development
pip install -e ".[all-dev]"

# OR install specific groups as needed
pip install -e ".[lint,test]"      # Just linting and testing
pip install -e ".[docs,build]"     # Documentation and building
pip install -e ".[frameworks]"     # Framework integrations
```

**Available dependency groups:**
- `lint` - Code quality tools (black, ruff, mypy)
- `test` - Testing framework and utilities
- `docs` - Documentation generation tools
- `build` - Package building and publishing tools
- `security` - Security scanning tools
- `frameworks` - Optional framework integrations
- `all-dev` - All development dependencies

### 📋 Traditional Approach (requirements files)

If you prefer requirements files:

```bash
# Full development environment
pip install -r requirements/dev.txt

# OR install specific components
pip install -r requirements/base.txt    # Core dependencies
pip install -r requirements/test.txt    # Testing only
pip install -r requirements/docs.txt    # Documentation only
```

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_specific.py
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Run security checks
make security
```

### Building and Testing the Package

```bash
# Build the package
make build

# Run the full build script (tests + build)
./scripts/build_package.sh
```

### Documentation

```bash
# Serve documentation locally
make docs-serve

# Build documentation
make docs-build
```

## Making Changes

1. **Fork the repository** and create a new branch for your feature
2. **Set up your development environment** using one of the methods above
3. **Make your changes** following our coding standards
4. **Add tests** for any new functionality
5. **Run the test suite** to ensure everything works
6. **Submit a pull request** with a clear description of your changes

## Code Standards

- **Formatting**: We use `black` for code formatting
- **Linting**: We use `ruff` for fast linting
- **Type Checking**: We use `mypy` for static type checking
- **Testing**: We use `pytest` for testing
- **Documentation**: We use `mkdocs` for documentation

Run `make lint` to check your code against our standards.

## Need Help?

- Check our [documentation](docs/)
- Look at existing [examples](examples/)
- Open an issue for questions or problems
- Join our community discussions

We appreciate your contributions! 🎉 
