# DeepSecure Release Process

This document outlines the standard operating procedure for publishing a new version of the `deepsecure` package. Following these steps ensures consistency, quality, and clear communication for each release.

## Phase 1: Code and Documentation Finalization

This phase involves updating all version numbers and summarizing the work included in the release.

### 1. Update Version Number

The project version must be updated in three key locations to ensure consistency. Replace `X.Y.Z` with the new version number (e.g., `0.1.9`).

-   **`pyproject.toml`**: Update the `version` key in the `[project]` table.
    ```toml
    [project]
    name = "deepsecure"
    version = "X.Y.Z" # <-- UPDATE THIS
    ```
-   **`deepsecure/__init__.py`**: Update the `__version__` dunder variable.
    ```python
    __version__ = "X.Y.Z" # <-- UPDATE THIS
    ```
-   **`credservice/docker-compose.yml`**: Update the `DEEPSECURE_VERSION` environment variable.
    ```yaml
    environment:
      - DEEPSECURE_VERSION=X.Y.Z # <-- UPDATE THIS
    ```

### 2. Update Changelog

Document the changes for the new release in the `CHANGELOG.md` file.

-   Create a new heading for the release using the format `## [X.Y.Z] - YYYY-MM-DD`.
-   Under the new heading, add subsections (`### Added`, `### Changed`, `### Fixed`, `### Removed`) as needed.
-   Summarize the key changes, bug fixes, and improvements made since the last release.

## Phase 2: Comprehensive Testing

This phase ensures the release is stable, functional, and that the documentation accurately reflects the product.

### 1. Reinstall Package in Development Mode

After updating version numbers, reinstall the package to ensure the development environment matches the source code version.

```bash
# Reinstall the package in development mode to sync versions
pip install -e .
```

This step is critical because:
- It ensures the installed package version matches the source code version
- It prevents version mismatch errors during testing
- It updates the package metadata that tests may check

### 2. Automated Testing

Run the complete automated test suite to check for any regressions or new bugs.

```bash
# Run tests using the Makefile for convenience
make test
```
*or directly*
```bash
python -m pytest
```
Ensure all tests pass before proceeding.

### 3. End-to-End Documentation-Led Testing

This is a critical manual validation step. Perform the exact steps a new user would take, following only the official documentation.

**Preliminary Step: Ensure a Clean Environment**

Before starting, ensure any old `credservice` containers and their data volumes are removed. This guarantees you are testing from a clean slate. From the repository root, run:

```bash
docker compose -f credservice/docker-compose.yml down --volumes
```

---

-   **[ ] Workflow 1: `credservice` Setup**
    1.  Follow the `docs/credservice-setup.md` guide from scratch in a clean environment. Key validation steps include:
        - Running `docker compose -f credservice/docker-compose.yml up -d --build`.
        - Verifying the service is running with `curl http://127.0.0.1:8001/health`.
        - (Optional) Verifying the database schema was created using `psql`.

-   **[ ] Workflow 2: Main `README.md` Quick Start**
    1.  Follow the steps in the main `README.md` precisely. Key validation steps include:
        - Using `deepsecure configure set-url` and `deepsecure configure set-token` as instructed.
        - Ensuring `deepsecure vault store` and other commands work as expected against the running service.

-   **[ ] Workflow 3: Run Example Scripts**
    1.  Execute the automated example test suite to validate all Python SDK examples:
        ```bash
        # Run all example tests with proper environment setup
        DEEPSECURE_CREDSERVICE_URL=http://127.0.0.1:8001 \
        DEEPSECURE_CREDSERVICE_API_TOKEN=DEFAULT_QUICKSTART_TOKEN \
        python -m pytest tests/test_examples.py -v -m e2e
        ```
    2.  Confirm all 7 examples pass without errors and produce expected output.
    3.  Review any skipped tests and ensure they're intentionally skipped (e.g., missing dependencies).

## Phase 3: Git and Build Workflow

This phase prepares the code for publication.

### 1. Commit All Changes

Stage all modified files (`pyproject.toml`, `CHANGELOG.md`, etc.) and create a release commit.

```bash
# Stage all changes
git add .

# Commit with a standardized message
git commit -m "chore(release): version X.Y.Z"
```

### 2. Create a Git Tag

Tag the release commit to mark this specific version in the project's history.

```bash
git tag vX.Y.Z
```

### 3. Build the Distribution Package

Ensure a clean build by removing old artifacts and then running the build script.

```bash
# Clean the dist directory and build the package using make (recommended)
make build
```
*or directly*
```bash
./scripts/build_package.sh
```
This will generate the final wheel (`.whl`) and source archive (`.tar.gz`) in the `dist/` directory.

## Phase 4: Publication

This is the final step to make the package publicly available.

### 1. Upload to PyPI

Use `twine` to securely upload the new distribution files to the Python Package Index.

```bash
# This will prompt for your PyPI username and password
twine upload dist/*
```

### 2. Push to Remote Repository

Push the release commit and the new tag to the primary branch (e.g., `main` or `dev`) on GitHub.

```bash
# Push the commit
git push origin main

# Push the tag
git push origin vX.Y.Z
``` 