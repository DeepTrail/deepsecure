#!/bin/bash
# Development setup script for deepsecure

set -e  # Exit on any error

echo "🚀 Setting up DeepSecure development environment..."

# Function to display usage
usage() {
    echo "Usage: $0 [modern|traditional]"
    echo ""
    echo "  modern      - Use pyproject.toml optional dependencies (recommended)"
    echo "  traditional - Use requirements/ files"
    echo ""
    echo "If no argument is provided, will try modern first, then fallback to traditional."
    exit 1
}

# Function to setup using modern approach
setup_modern() {
    echo "📦 Setting up using modern pyproject.toml approach..."
    
    # Install in editable mode with all development dependencies
    pip install -e ".[all-dev]"
    
    echo "✅ Modern setup complete!"
    echo ""
    echo "Available dependency groups:"
    echo "  pip install -e .[lint]      # Code quality tools"
    echo "  pip install -e .[test]      # Testing tools"
    echo "  pip install -e .[docs]      # Documentation tools"
    echo "  pip install -e .[build]     # Build tools"
    echo "  pip install -e .[security]  # Security scanning"
    echo "  pip install -e .[all-dev]   # Everything"
}

# Function to setup using traditional approach
setup_traditional() {
    echo "📋 Setting up using traditional requirements files..."
    
    # Install development requirements
    pip install -r requirements/dev.txt
    
    echo "✅ Traditional setup complete!"
    echo ""
    echo "Available requirements files:"
    echo "  pip install -r requirements/base.txt       # Core dependencies"
    echo "  pip install -r requirements/dev.txt        # Development tools"
    echo "  pip install -r requirements/test.txt       # Testing only"
    echo "  pip install -r requirements/docs.txt       # Documentation"
    echo "  pip install -r requirements/frameworks.txt # Framework integrations"
}

# Function to verify setup
verify_setup() {
    echo "🔍 Verifying setup..."
    
    # Check if key tools are available
    python -c "import pytest; print('✅ pytest available')"
    python -c "import black; print('✅ black available')"
    python -c "import ruff; print('✅ ruff available')"
    python -c "import deepsecure; print('✅ deepsecure package available')"
    
    echo ""
    echo "🎉 Setup verification complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Run tests: pytest"
    echo "  2. Format code: black ."
    echo "  3. Lint code: ruff check ."
    echo "  4. Build package: ./scripts/build_package.sh"
}

# Main script logic
case "${1:-auto}" in
    "modern")
        setup_modern
        ;;
    "traditional")
        setup_traditional
        ;;
    "auto")
        echo "🔄 Attempting modern setup first..."
        if setup_modern 2>/dev/null; then
            echo "✅ Modern setup successful"
        else
            echo "⚠️  Modern setup failed, trying traditional..."
            setup_traditional
        fi
        ;;
    "-h"|"--help"|"help")
        usage
        ;;
    *)
        echo "❌ Unknown option: $1"
        usage
        ;;
esac

# Verify the setup worked
verify_setup 