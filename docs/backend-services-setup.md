# DeepSecure Backend Services Setup Guide

Welcome! This guide explains how to set up the complete DeepSecure backend infrastructure locally. DeepSecure uses a **dual-service architecture** with both the Control Plane and Data Plane services working together to provide comprehensive AI agent security.

## Architecture Overview

DeepSecure consists of two main backend services:

- **🧠 Control Plane (`deeptrail-control`)** - Agent identity management, policy engine, credential issuance, and audit logging
- **🚀 Data Plane (`deeptrail-gateway`)** - Secret injection, policy enforcement, split-key security, and request proxying

Both services work together with supporting infrastructure:
- **PostgreSQL Database** - Stores agent identities, policies, and audit logs  
- **Redis** - Split-key storage for enhanced security

## Quickstart: Running All Services

Follow these steps from the root of the repository to get the complete backend infrastructure running.

### 1. Start the Backend Services

This command will build the Docker images and start all four containers in the background:

```bash
docker compose up -d --build
```

On first run, this will:
- Build the `deeptrail-control` and `deeptrail-gateway` services
- Create and initialize the PostgreSQL database with proper schema
- Start Redis for split-key storage
- Apply all database migrations automatically

### 2. Verify All Services Are Running

Check that all four containers are running and healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES                     STATUS                   PORTS
deeptrail_control_app     Up 2 minutes             0.0.0.0:8000->8001/tcp
deeptrail_gateway_app     Up 2 minutes             0.0.0.0:8002->8001/tcp  
deeptrail_control_db      Up 2 minutes (healthy)   0.0.0.0:5434->5432/tcp
deeptrail_gateway_redis   Up 2 minutes (healthy)   0.0.0.0:6380->6379/tcp
```

### 3. Verify Service Health

Test both main services are responding:

**Control Plane Health Check:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "service": "DeepSecure Control Plane",
  "version": "0.1.9",
  "status": "ok",
  "dependencies": {
    "database": "connected"
  }
}
```

**Gateway Health Check:**
```bash
curl http://localhost:8002/health
```

Expected response:
```json
{
  "service": "DeepSecure Gateway",
  "version": "0.1.9",
  "status": "ok",
  "dependencies": {
    "control_plane": "connected",
    "redis": "connected"
  }
}
```

### 4. Verify Database Schema (Optional)

To confirm the database schema was created automatically:

```bash
docker exec -it deeptrail_control_db psql -U deepsecure_user -d deeptrail_controldb
```

At the `deeptrail_controldb=#` prompt, list the tables:
```sql
\dt
```

You should see tables including: `agents`, `credentials`, `policies`, `secrets`, and `alembic_version`.

Type `\q` and press Enter to exit.

### 5. Verify Redis Storage (Optional)

To confirm Redis is working for split-key storage:

```bash
docker exec -it deeptrail_gateway_redis redis-cli ping
```

Expected response: `PONG`

## 🎉 Success! Your Backend is Ready

Your complete DeepSecure backend infrastructure is now running:

- **Control Plane**: http://localhost:8000 (Management operations)
- **Gateway**: http://localhost:8002 (Runtime operations, secret injection)
- **Database**: localhost:5434 (PostgreSQL)
- **Redis**: localhost:6380 (Split-key storage)

You can now proceed with:
- The [30-second quickstart](../README.md#-30-second-quickstart) in the main README
- Running the [examples](../examples/) to see DeepSecure in action
- Using the `deepsecure` CLI and SDK for development

## Service Details

### Control Plane (Port 8000)
**Purpose**: Policy Decision Point (PDP) and agent management
- Agent identity creation and management
- Policy definition and storage  
- Credential issuance (JWT tokens)
- Audit logging and compliance
- Authentication and authorization

**Key Endpoints**:
- `GET /health` - Service health check
- `POST /api/v1/agents` - Create agents
- `POST /api/v1/auth/challenge` - Authentication flow
- `GET /api/v1/policies` - Policy management

### Gateway (Port 8002)  
**Purpose**: Policy Enforcement Point (PEP) and data plane
- Secret injection into external API calls
- Real-time policy enforcement
- Split-key security (JIT reassembly)
- Request proxying and traffic management
- Rate limiting and request filtering

**Key Endpoints**:
- `GET /health` - Service health check
- `POST /proxy/*` - Proxied external API calls
- `GET /secrets/*` - Secret retrieval with policy enforcement

## Development Notes

### Container Communication
- Services communicate internally via Docker network `deepsecure_network`
- Gateway connects to Control Plane at `http://deeptrail-control:8001`
- Control Plane connects to database at `postgresql://deepsecure_user:deepsecure_password@db/deeptrail_controldb`
- Gateway connects to Redis at `redis://redis:6379`

### Data Persistence
- Database data: `postgres_data` Docker volume
- Redis data: `redis_data` Docker volume  
- Data persists across container restarts

### Environment Variables
Key environment variables set in `docker-compose.yml`:
- `DEEPSECURE_VERSION` - Current package version
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `GATEWAY_URL` - Gateway service URL for Control Plane
- `CONTROL_PLANE_URL` - Control Plane URL for Gateway

---

## Troubleshooting

<details>
<summary><b>🔧 Service Startup Issues</b></summary>

If services fail to start, check the logs:

```bash
# View all service logs
docker compose logs

# View specific service logs  
docker logs deeptrail_control_app
docker logs deeptrail_gateway_app
docker logs deeptrail_control_db
docker logs deeptrail_gateway_redis
```

Common issues:
- **Port conflicts**: Ensure ports 8000, 8002, 5434, 6380 are not in use
- **Database connection**: Wait for database to be fully healthy before services start
- **Memory**: Ensure Docker has sufficient memory allocation
</details>

<details>
<summary><b>🗄️ Database Issues</b></summary>

Database connection problems:

```bash
# Check database container health
docker inspect deeptrail_control_db --format='{{.State.Health.Status}}'

# Connect to database manually
docker exec -it deeptrail_control_db psql -U deepsecure_user -d deeptrail_controldb

# Reset database (⚠️ destroys data)
docker compose down -v
docker compose up -d
```
</details>

<details>
<summary><b>🔄 Redis Issues</b></summary>

Redis connection problems:

```bash
# Check Redis health
docker exec deeptrail_gateway_redis redis-cli ping

# View Redis info
docker exec deeptrail_gateway_redis redis-cli info

# Clear Redis data (⚠️ destroys cached keys)
docker exec deeptrail_gateway_redis redis-cli flushall
```
</details>

<details>
<summary><b>🌐 Network Issues</b></summary>

Service communication problems:

```bash
# Check Docker network
docker network ls
docker network inspect deepsecure_network

# Test internal connectivity
docker exec deeptrail_gateway_app curl http://deeptrail-control:8001/health
```
</details>

## Stopping Services

To stop all services:

```bash
# Stop services (keeps data)
docker compose down

# Stop services and remove volumes (⚠️ destroys data)  
docker compose down -v
```