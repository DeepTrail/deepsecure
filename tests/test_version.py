"""Test for the version consistency."""

import importlib.metadata
import toml # type: ignore

# Import __version__ directly from the package
from deepsecure import __version__ as package_init_version

def test_version_consistency():
    """
    Tests that __version__ in deepsecure/__init__.py is consistent
    with pyproject.toml and with importlib.metadata if the package is installed.
    """
    # 1. Get version from pyproject.toml
    #    Assumes tests are run from the project root or pyproject.toml is in a discoverable path.
    #    For robustness, consider constructing path relative to this test file if needed.
    pyproject_path = "pyproject.toml" 
    try:
        with open(pyproject_path, "r") as f:
            data = toml.load(f)
        pyproject_version = data["project"]["version"]
    except FileNotFoundError:
        assert False, f"Could not find {pyproject_path}. Ensure tests are run from project root."
    except KeyError:
        assert False, f"Could not find project.version in {pyproject_path}."


    # 2. Assert that deepsecure.__version__ (from __init__.py) matches pyproject.toml
    # This is the most crucial check for development consistency.
    assert package_init_version == pyproject_version, \
        f"__init__.py version ({package_init_version}) does not match pyproject.toml version ({pyproject_version})"

    # 3. Try to get version using importlib.metadata (for when package is installed)
    try:
        metadata_version = importlib.metadata.version("deepsecure")
        assert package_init_version == metadata_version, \
            f"__init__.py version ({package_init_version}) does not match importlib.metadata version ({metadata_version})"
        assert pyproject_version == metadata_version, \
            f"pyproject.toml version ({pyproject_version}) does not match importlib.metadata version ({metadata_version})"
        print(f"All versions consistent: {package_init_version}")
    except importlib.metadata.PackageNotFoundError:
        # This is acceptable if the package is not "installed" in the current environment
        # (e.g., running tests directly from source without `pip install -e .`).
        # The check against pyproject.toml already validated package_init_version.
        print(f"Package 'deepsecure' not found by importlib.metadata. Skipping metadata version check. "
              f"__init__.py version ({package_init_version}) and pyproject.toml version ({pyproject_version}) match.")
    except Exception as e:
        assert False, f"An unexpected error occurred when checking versions: {e}" 