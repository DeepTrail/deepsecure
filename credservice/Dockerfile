# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install postgresql-client for pg_isready
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and Alembic setup
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .
COPY run_service.sh .

# Make the startup script executable
RUN chmod +x ./run_service.sh

# Make port 8001 available to the world outside this container
EXPOSE 8001

# Define environment variables (can be overridden by docker-compose)
# These are placeholders; actual values will come from docker-compose.yml
ENV DATABASE_URL="postgresql://user:password@db:5432/credservicedb"
# For JWTs or other security features if used by credservice
ENV SECRET_KEY="your-secret-key-please-change-in-compose"
ENV ALGORITHM="HS256"
# For easy quickstart, can be overridden in docker-compose.yml
ENV BACKEND_API_TOKEN="DEFAULT_QUICKSTART_TOKEN"

# Use the run script as the container's entrypoint. This will automatically
# run migrations and then start the server.
CMD ["./run_service.sh"] 