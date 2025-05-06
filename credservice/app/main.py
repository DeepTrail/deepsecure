"""Main FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.v1.api import api_router
from app.core.config import settings

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
    title="DeepSecure Backend API",
    description="API for managing DeepSecure agent credentials and identities.",
    version="0.1.0"
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

@app.get("/health", tags=["Health"])
async def health_check():
    """Perform a basic health check.

    Returns:
        dict: A dictionary indicating the service status.
    """
    return {"status": "ok"}

# TODO: Add routers for vault endpoints
# from app.api.v1 import vault_router
# app.include_router(vault_router, prefix="/v1/vault", tags=["Vault"])

# TODO: Add startup/shutdown events (e.g., connect/disconnect DB) 