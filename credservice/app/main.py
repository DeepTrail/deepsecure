"""Main FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
from app.api.deps import DbDep
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request logging middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        
        # Process the request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log response
            logger.info(f"Response: {request.method} {request.url.path} - {response.status_code} in {process_time:.4f}s")
            
            return response
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            raise

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for managing DeepSecure agent credentials and identities.",
    version=settings.PROJECT_VERSION
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with appropriate origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Include the main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"], response_model=dict)
async def health_check(db: DbDep):
    """
    Perform a detailed health check, including database connectivity.
    """
    db_status = "connected"
    try:
        # Try to execute a simple query to check DB connection
        db.execute(text("SELECT 1"))
    except (SQLAlchemyError, ConnectionRefusedError) as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"

    return {
        "service": "DeepSecure CredService",
        "version": app.version,
        "status": "ok",
        "dependencies": {
            "database": db_status
        }
    }

# TODO: Add routers for vault endpoints
# from app.api.v1 import vault_router
# app.include_router(vault_router, prefix="/v1/vault", tags=["Vault"])

# TODO: Add startup/shutdown events (e.g., connect/disconnect DB) 