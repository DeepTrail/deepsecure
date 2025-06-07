# Contributing to DeepSecure

First off, thank you for considering contributing to DeepSecure! It's people like you that make open source such a great community. We welcome any and all contributions.

## Getting Started with Code Contributions

1.  Fork the repository.
2.  Create a feature or bugfix branch.
3.  Commit your changes with clear messages.
4.  Push to your fork and open a Pull Request against our `main` branch.

Please provide a clear description of the problem and solution, including any relevant issue numbers.

## Development Environment Setup

To set up your development environment for DeepSecure:

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone https://github.com/DeepTrail/deepsecure.git # Or your fork
    cd deepsecure
    ```

2.  **Create and activate a Python virtual environment:**
    We recommend using a virtual environment to manage project dependencies.
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    Install the core package in editable mode along with development and test dependencies. These are often specified in `pyproject.toml` under `[project.optional-dependencies]` (e.g., `dev`, `test`).
    ```bash
    pip install -e ".[dev,test]" # Adjust if your dependency groups are named differently
    ```

4.  **Set up pre-commit hooks (Optional but Recommended):**
    If the project uses pre-commit hooks for linting and formatting:
    ```bash
    pip install pre-commit
    pre-commit install
    ```

## Running Tests

Ensure your `credservice` backend is running if tests require it (see [Running the Credential Service (Backend)](README.md#️-running-the-credential-service-backend) in the main README).

To run the test suite (typically using `pytest`):
```bash
pytest
```

You might also run specific tests:
```bash
pytest tests/commands/test_agent.py  # Example for a specific file
pytest tests/commands/test_agent.py::test_register_agent # Example for a specific test function
```

Now you're ready to start developing! 
