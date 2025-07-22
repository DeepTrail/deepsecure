#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Add a fixed delay to allow Docker networking to stabilize.
# This is a workaround for persistent networking issues in some Docker environments.
echo "INFO: Adding a 15-second delay for network stabilization..."
sleep 15

# Apply database migrations before starting the server.
echo "INFO: Applying database migrations..."
alembic upgrade head
echo "INFO: Database migrations applied."

# Start the Uvicorn server.
# The 'exec' command replaces the shell process with the Uvicorn process,
# which allows it to receive signals (like SIGTERM) from Docker correctly.
echo "INFO: Starting Uvicorn server on 0.0.0.0:8001..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001