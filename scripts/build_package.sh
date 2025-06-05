#!/bin/bash
# Build script for deepsecure package

set -e  # Exit on any error

# Clean old builds
echo "Cleaning old build artifacts..."
rm -rf build/ dist/ *.egg-info/ deepsecure.egg-info/ || true
echo "✅ Cleaned old builds"

# Ensure current version is installed in editable mode for testing
echo "Installing/updating editable version for testing..."
pip install -e ".[dev,test]" --quiet
echo "✅ Editable version updated"

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