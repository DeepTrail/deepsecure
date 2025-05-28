"""Test for the version command."""

import re
from unittest.mock import patch
import importlib.metadata

from deepsecure.main import version

def test_version_command():
    """Test that the version command displays the package version."""
    with patch('builtins.print') as mock_print:
        # Try to get the version using importlib.metadata
        try:
            expected_version = importlib.metadata.version("deepsecure")
            expected_output = f"DeepSecure CLI version: {expected_version}"
        except importlib.metadata.PackageNotFoundError:
            # For development/testing when package isn't installed
            expected_output = "DeepSecure CLI version: 0.0.2 (development)"
        
        # Call the version function
        version()
        
        # Verify the output
        mock_print.assert_called_once_with(expected_output) 