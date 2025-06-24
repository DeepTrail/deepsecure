#!/bin/bash
# Build script for deepsecure package

set -e  # Exit on any error

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to ensure build tools are available
ensure_build_tools() {
    echo "Checking build tools..."
    
    # Check if build tools are available
    if ! python -c "import build" 2>/dev/null; then
        echo "Installing build tools..."
        pip install build
    fi
    
    if ! python -c "import twine" 2>/dev/null; then
        echo "Installing twine..."
        pip install twine
    fi
    
    echo "✅ Build tools are available"
}

# Function to install dependencies (supports both methods)
install_dependencies() {
    echo "Installing dependencies..."
    
    # Try modern approach first (pyproject.toml optional dependencies)
    if pip install -e ".[dev,test,build]" --quiet 2>/dev/null; then
        echo "✅ Installed using modern optional dependencies"
    # Fallback to traditional requirements files
    elif [ -f "requirements/dev.txt" ]; then
        pip install -r requirements/dev.txt --quiet
        echo "✅ Installed using traditional requirements files"
    else
        echo "❌ Could not find dependency specifications"
        exit 1
    fi
}

# Clean old builds
echo "Cleaning old build artifacts..."
rm -rf build/ dist/ *.egg-info/ deepsecure.egg-info/ || true
echo "✅ Cleaned old builds"

# Ensure build tools are available
ensure_build_tools

# Install dependencies
install_dependencies

# Run tests
echo "Running tests..."
python -m pytest || { echo "❌ Tests failed"; exit 1; }
echo "✅ Tests passed"

# Build package
echo "Building package..."
python -m build || { echo "❌ Build failed"; exit 1; }
echo "✅ Built package"

# Check package
echo "Checking package with twine..."
twine check dist/* || { echo "❌ Package check failed"; exit 1; }
echo "✅ Package check passed"

echo "============================="
echo "Package is ready for upload!"
echo "To upload to PyPI, run:"
echo "twine upload dist/*"
echo "=============================" 