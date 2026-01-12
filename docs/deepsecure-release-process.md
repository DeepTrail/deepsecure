# DeepSecure Release Process

This document outlines the standard operating procedure for publishing a new version of the `deepsecure` package. Following these steps ensures consistency, quality, and clear communication for each release.

---

## Pre-Release Testing Checklist

Use this checklist as a quick reference before each release. Detailed instructions for each step are provided in the phases below.

- [ ] Run unit tests: `make test-unit`
- [ ] Run integration tests: `make test-integration` (with backend services running)
- [ ] Generate test report: `make test-report`
- [ ] Review failed tests and document known issues
- [ ] All critical tests pass (verify in `test-results/vX.Y.Z/test-report.md`)
- [ ] Update CHANGELOG with test summary
- [ ] Commit test results to `test-results/vX.Y.Z/`
- [ ] Tag release and push

---

## Phase 1: Code and Documentation Finalization

This phase involves updating all version numbers and summarizing the work included in the release.

### 1. Update Version Number

The project version must be updated in **five** key locations to ensure consistency across the entire dual architecture. Replace `X.Y.Z` with the new version number (e.g., `0.1.10`).

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
-   **`docker-compose.yml`**: Update the `DEEPSECURE_VERSION` environment variable for the deeptrail-control service.
    ```yaml
    deeptrail-control:
      # ... other config ...
      environment:
        - DEEPSECURE_VERSION=X.Y.Z # <-- UPDATE THIS
    ```
-   **`docs/openapi.yaml`**: Update the API specification version.
    ```yaml
    openapi: 3.0.0
    info:
      title: DeepSecure API
      version: "X.Y.Z" # <-- UPDATE THIS
    ```
-   **`docs/backend-services-setup.md`**: Update the version in the health check example response.
    ```json
    {
      "service": "DeepSecure Control Plane",
      "version": "X.Y.Z", # <-- UPDATE THIS
      "status": "ok",
      "dependencies": {
        "database": "connected"
      }
    }
    ```

### 2. Update Changelog

Document the changes for the new release in the `CHANGELOG.md` file.

-   Create a new heading for the release using the format `## [X.Y.Z] - YYYY-MM-DD`.
-   Under the new heading, add subsections (`### Added`, `### Changed`, `### Fixed`, `### Removed`) as needed.
-   Summarize the key changes, bug fixes, and improvements made since the last release.

## Phase 2: Comprehensive Testing

This phase ensures the release is stable, functional, and that the documentation accurately reflects the dual architecture setup.

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

Before starting, ensure any old deeptrail-control and deeptrail-gateway containers and their data volumes are removed. This guarantees you are testing from a clean slate. From the repository root, run:

```bash
docker compose down --volumes
```

---

-   **[ ] Workflow 1: Dual Architecture Setup**
    1.  Follow the "Getting Started" section in the main `README.md` from scratch in a clean environment. Key validation steps include:
        - Running `docker-compose up -d` to start all services
        - Verifying all containers are running and healthy: `docker ps`
        - Expected containers:
          - `deeptrail_control_app` (Control Plane)
          - `deeptrail_gateway_app` (Gateway)
          - `deeptrail_control_db` (PostgreSQL Database)
          - `deeptrail_gateway_redis` (Redis for Split-Key Storage)
        - Verifying the control plane service: `curl http://localhost:8000/health`
        - Verifying the gateway service: `curl http://localhost:8002/health`

-   **[ ] Workflow 2: Main `README.md` Quick Start**
    1.  Follow the 30-second quickstart in the main `README.md` precisely. Key validation steps include:
        - Using `deepsecure configure set-url http://localhost:8000` as instructed.
        - Creating a test agent: `deepsecure agent create --name "test-agent"`.
        - Testing SDK functionality with the quickstart code example.

-   **[ ] Workflow 3: Run Example Scripts**
    1.  Execute the automated example test suite to validate all Python SDK examples:
        ```bash
        # Run all example tests with proper environment setup
        DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000 \
        DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN=DEFAULT_QUICKSTART_TOKEN \
        python -m pytest tests/test_examples.py -v -m e2e
        ```
    2.  Confirm all examples pass without errors and produce expected output.
    3.  Review any skipped tests and ensure they're intentionally skipped (e.g., missing dependencies).

-   **[ ] Workflow 4: Architecture Validation**
    1.  Verify the dual architecture is working correctly:
        - Test that management operations (agent create, policy create) go directly to deeptrail-control.
        - Test that runtime operations (secret fetching, external API calls) go through deeptrail-gateway.
        - Verify policy enforcement is working at the gateway level.
        - Check audit logs are being written to the control plane.
    2.  Container health validation:
        - Verify `deeptrail_control_db` is healthy and accepting connections
        - Verify `deeptrail_gateway_redis` is healthy and accessible
        - Test database connectivity: `docker exec deeptrail_control_app psql $DATABASE_URL -c "SELECT 1;"`
        - Test Redis connectivity: `docker exec deeptrail_gateway_redis redis-cli ping`

## Phase 3: Git and Build Workflow

This phase prepares the code for publication.

### 1. Commit All Changes

Stage all modified files (`pyproject.toml`, `deepsecure/__init__.py`, `docker-compose.yml`, `docs/openapi.yaml`, `docs/backend-services-setup.md`, `CHANGELOG.md`, etc.) and create a release commit.

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

## Post-Release Verification

After publishing, perform these verification steps:

### 1. PyPI Verification
- Visit the [DeepSecure PyPI page](https://pypi.org/project/deepsecure/) to confirm the new version is live.
- Test installation in a fresh environment: `pip install deepsecure==X.Y.Z`.

### 2. Documentation Verification
- Verify that all documentation links and examples work with the new version.
- Check that the dual architecture diagrams and explanations are accurate.

### 3. Container Verification
- Pull and test the updated Docker containers to ensure they work with the new version.
- Verify that the `DEEPSECURE_VERSION` environment variable is correctly set in running containers.
- Validate all four containers are running:
  ```bash
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  ```
  Expected output should show:
  - `deeptrail_control_app` (Up, port 8000:8001)
  - `deeptrail_gateway_app` (Up, port 8002:8001)
  - `deeptrail_control_db` (Up, port 5434:5432)
  - `deeptrail_gateway_redis` (Up, port 6380:6379)

---

## Troubleshooting Common Issues

### Version Mismatch Errors
If you encounter version mismatch errors during testing:
1. Ensure all five version locations have been updated consistently.
2. Reinstall the package in development mode: `pip install -e .`.
3. Clear any cached Python bytecode: `find . -name "*.pyc" -delete`.

### Docker Build Issues
If Docker builds fail after version updates:
1. Clear Docker build cache: `docker builder prune`.
2. Rebuild with no cache: `docker-compose build --no-cache`.
3. Check that all volume mounts and file paths are correct.

### Test Failures
If integration tests fail:
1. Ensure all four containers are running and healthy:
   - `deeptrail_control_app`
   - `deeptrail_gateway_app`
   - `deeptrail_control_db`
   - `deeptrail_gateway_redis`
2. Check that all environment variables are set correctly.
3. Verify that ports 8000 (control plane) and 8002 (gateway) are not in use by other services.
4. Check container logs for specific errors:
   ```bash
   docker logs deeptrail_control_app
   docker logs deeptrail_gateway_app
   docker logs deeptrail_control_db
   docker logs deeptrail_gateway_redis
   ``` 