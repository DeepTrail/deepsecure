#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Wait for the database to be ready.
# The DATABASE_URL is injected by docker-compose.
echo "INFO: Waiting for database to be ready..."
until pg_isready --quiet --host=db --username=${POSTGRES_USER:-deepsecure_user}; do
  echo "INFO: Database is unavailable - sleeping"
  sleep 1
done
echo "INFO: Database is ready."

# Apply database migrations before starting the server.
echo "INFO: Applying database migrations..."
alembic upgrade head
echo "INFO: Database migrations applied."

# Start the Uvicorn server.
# The 'exec' command replaces the shell process with the Uvicorn process,
# which allows it to receive signals (like SIGTERM) from Docker correctly.
echo "INFO: Starting Uvicorn server on 0.0.0.0:8001..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001