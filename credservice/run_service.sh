#!/bin/bash
# Run script for DeepSecure Credential Service

set -e

# Set environment variables
export DATABASE_URL="sqlite:///./test.db"
export BACKEND_API_TOKEN="deepsecure_api_token_for_testing"
export SECRET_KEY="very_secure_secret_key_for_jwt_if_needed"

# Change to the credservice directory if not already there
cd "$(dirname "$0")"

# Run the FastAPI service with uvicorn
echo "Starting DeepSecure Credential Service with SQLite database..."

# Run database migrations
alembic upgrade head

# Start the FastAPI application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000