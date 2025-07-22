"""
Proxy Configuration Module for DeepTrail Gateway

This module provides configuration management for the proxy functionality,
designed with industry-standard patterns to ensure compatibility with
production reverse proxies like NGINX, Traefik, and HAProxy.

Core PEP Configuration:
- Basic proxy settings
- JWT validation
- Simple policy enforcement
- Target URL routing

For Future - Enterprise Grade:
- Advanced security filtering
- Comprehensive rate limiting
- Sophisticated IP blocking
- Performance monitoring
- Multi-environment configuration
"""

import os
import toml
from pathlib import Path
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field, validator
from enum import Enum


def get_project_version() -> str:
    """Reads the project version from environment variable or pyproject.toml file."""
    # First try to get version from environment variable (for Docker)
    env_version = os.getenv("DEEPSECURE_VERSION")
    if env_version:
        return env_version
    
    # Fallback to reading from pyproject.toml (for local development)
    # Gateway is inside deeptrail-gateway directory, so go up two levels to reach project root
    pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return "0.0.0-dev"  # Fallback for when run in isolation
    
    try:
        pyproject_data = toml.load(pyproject_path)
        return pyproject_data.get("project", {}).get("version", "0.0.0-unknown")
    except Exception:
        return "0.0.0-unknown"


class ProxyType(str, Enum):
    """Supported proxy types for future migration compatibility."""
    DEEPTRAIL_GATEWAY = "deeptrail-gateway"
    # For Future - Enterprise Grade: Support for other proxy types
    NGINX = "nginx"
    TRAEFIK = "traefik"
    HAPROXY = "haproxy"
    ENVOY = "envoy"


class SecurityConfig(BaseModel):
    """Security configuration for proxy operations."""
    
    # Core PEP: Basic IP filtering
    block_internal_ips: bool = Field(
        default=True,
        description="Block requests to internal IP ranges for security"
    )
    
    # Core PEP: Basic request limits
    max_request_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum allowed request body size in bytes"
    )
    
    # Core PEP: Request timeout
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    
    # JWT Configuration for signature validation
    jwt_secret_key: str = Field(
        default="your-secret-key-for-jwt",
        description="Secret key for JWT signature validation (must match deeptrail-control)"
    )
    
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm (must match deeptrail-control)"
    )
    
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT token expiration time in minutes"
    )

    # For Future - Enterprise Grade: Advanced security
    enable_request_signing: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable request signing"
    )
    
    # For Future - Enterprise Grade: Advanced IP filtering
    allowed_ip_ranges: List[str] = Field(
        default_factory=list,
        description="For Future - Enterprise Grade: List of allowed IP ranges"
    )
    
    blocked_ip_ranges: List[str] = Field(
        default_factory=list,
        description="For Future - Enterprise Grade: List of blocked IP ranges"
    )
    
    # For Future - Enterprise Grade: Advanced rate limiting
    enable_rate_limiting: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable rate limiting"
    )
    
    rate_limit_requests_per_minute: int = Field(
        default=100,
        description="For Future - Enterprise Grade: Rate limit per minute"
    )
    
    # For Future - Enterprise Grade: DDoS protection
    enable_ddos_protection: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable DDoS protection"
    )


class RoutingConfig(BaseModel):
    """Routing configuration for proxy operations."""
    
    # Core PEP: Basic routing
    target_header: str = Field(
        default="X-Target-Base-URL",
        description="Header containing the target URL for proxy requests"
    )
    
    path_prefix: str = Field(
        default="/proxy",
        description="Path prefix for proxy requests"
    )
    
    # For Future - Enterprise Grade: Advanced routing
    enable_path_rewriting: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable path rewriting"
    )
    
    path_rewrite_rules: Dict[str, str] = Field(
        default_factory=dict,
        description="For Future - Enterprise Grade: Path rewrite rules"
    )
    
    # For Future - Enterprise Grade: Load balancing
    enable_load_balancing: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable load balancing"
    )
    
    load_balancing_strategy: str = Field(
        default="round_robin",
        description="For Future - Enterprise Grade: Load balancing strategy"
    )


class AuthenticationConfig(BaseModel):
    """Authentication configuration."""
    
    # Core PEP: JWT validation (essential)
    jwt_validation: bool = Field(
        default=True,
        description="Enable JWT token validation for requests"
    )
    
    # For Future - Enterprise Grade: Advanced authentication
    jwt_public_key_url: Optional[str] = Field(
        default=None,
        description="For Future - Enterprise Grade: URL to fetch JWT public key"
    )
    
    jwt_audience: Optional[str] = Field(
        default=None,
        description="For Future - Enterprise Grade: Expected JWT audience"
    )
    
    jwt_issuer: Optional[str] = Field(
        default=None,
        description="For Future - Enterprise Grade: Expected JWT issuer"
    )
    
    # For Future - Enterprise Grade: Multi-factor authentication
    enable_mfa: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable multi-factor authentication"
    )
    
    # For Future - Enterprise Grade: OAuth2 integration
    enable_oauth2: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable OAuth2 integration"
    )


class PolicyConfig(BaseModel):
    """Policy enforcement configuration."""
    
    # Core PEP: Basic policy enforcement
    enforcement_mode: str = Field(
        default="strict",
        description="Policy enforcement mode: strict, permissive, or disabled"
    )
    
    # For Future - Enterprise Grade: Advanced policy features
    enable_policy_caching: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable policy caching"
    )
    
    policy_cache_ttl_seconds: int = Field(
        default=300,
        description="For Future - Enterprise Grade: Policy cache TTL in seconds"
    )
    
    # For Future - Enterprise Grade: Policy decision logging
    enable_policy_logging: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable policy decision logging"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    # Core PEP: Basic logging
    enable_request_logging: bool = Field(
        default=True,
        description="Enable request/response logging"
    )
    
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    # For Future - Enterprise Grade: Advanced logging
    enable_structured_logging: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable structured logging"
    )
    
    log_format: str = Field(
        default="simple",
        description="For Future - Enterprise Grade: Log format: simple, json, or custom"
    )
    
    # For Future - Enterprise Grade: Log shipping
    enable_log_shipping: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable log shipping"
    )
    
    log_shipping_endpoint: Optional[str] = Field(
        default=None,
        description="For Future - Enterprise Grade: Log shipping endpoint"
    )


class MonitoringConfig(BaseModel):
    """Monitoring and metrics configuration."""
    
    # For Future - Enterprise Grade: Metrics collection
    enable_metrics: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable metrics collection"
    )
    
    metrics_endpoint: str = Field(
        default="/metrics",
        description="For Future - Enterprise Grade: Metrics endpoint path"
    )
    
    # For Future - Enterprise Grade: Health checks
    enable_health_checks: bool = Field(
        default=True,
        description="For Future - Enterprise Grade: Enable health checks"
    )
    
    health_check_endpoint: str = Field(
        default="/health",
        description="For Future - Enterprise Grade: Health check endpoint path"
    )
    
    # For Future - Enterprise Grade: Performance monitoring
    enable_performance_monitoring: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable performance monitoring"
    )


class ProxyConfig(BaseModel):
    """Main proxy configuration."""
    
    # Version information
    version: str = Field(
        default_factory=get_project_version,
        description="Application version from environment or pyproject.toml"
    )
    
    # Core PEP: Basic server configuration
    host: str = Field(
        default="0.0.0.0",
        description="Host to bind the proxy server"
    )
    
    port: int = Field(
        default=8002,
        description="Port to bind the proxy server"
    )
    
    # Core PEP: Control plane connection
    control_plane_url: str = Field(
        default="http://deeptrail-control:8000",
        description="URL of the deeptrail-control service"
    )
    
    # Core PEP: Essential configurations
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security configuration"
    )
    
    routing: RoutingConfig = Field(
        default_factory=RoutingConfig,
        description="Routing configuration"
    )
    
    authentication: AuthenticationConfig = Field(
        default_factory=AuthenticationConfig,
        description="Authentication configuration"
    )
    
    policy: PolicyConfig = Field(
        default_factory=PolicyConfig,
        description="Policy enforcement configuration"
    )
    
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig,
        description="Monitoring configuration"
    )
    
    # For Future - Enterprise Grade: Proxy type selection
    proxy_type: ProxyType = Field(
        default=ProxyType.DEEPTRAIL_GATEWAY,
        description="For Future - Enterprise Grade: Proxy type for migration compatibility"
    )
    
    # For Future - Enterprise Grade: Advanced features
    enable_caching: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable response caching"
    )
    
    enable_compression: bool = Field(
        default=False,
        description="For Future - Enterprise Grade: Enable response compression"
    )


def load_config() -> ProxyConfig:
    """Load proxy configuration from environment variables."""
    
    # Helper function to parse size strings
    def parse_size(size_str: str) -> int:
        """Parse size string like '10MB' into bytes."""
        if isinstance(size_str, int):
            return size_str
        
        size_str = size_str.upper()
        if size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    # Core PEP: Load essential configuration
    config_data = {
        'host': os.getenv('PROXY_HOST', '0.0.0.0'),
        'port': int(os.getenv('PROXY_PORT', '8002')),
        'control_plane_url': os.getenv('CONTROL_PLANE_URL', 'http://deeptrail-control:8000'),
        'security': {
            'block_internal_ips': os.getenv('BLOCK_INTERNAL_IPS', 'true').lower() == 'true',
            'max_request_size': parse_size(os.getenv('MAX_REQUEST_SIZE', '10MB')),
            'request_timeout': int(os.getenv('REQUEST_TIMEOUT', '30')),
            'jwt_secret_key': os.getenv('SECRET_KEY', 'your-secret-key-for-jwt'),
            'jwt_algorithm': os.getenv('JWT_ALGORITHM', 'HS256'),
            'jwt_access_token_expire_minutes': int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30')),
        },
        'routing': {
            'target_header': os.getenv('TARGET_HEADER', 'X-Target-Base-URL'),
            'path_prefix': os.getenv('PATH_PREFIX', '/proxy'),
        },
        'authentication': {
            'jwt_validation': os.getenv('JWT_VALIDATION', 'true').lower() == 'true',
        },
        'policy': {
            'enforcement_mode': os.getenv('POLICY_ENFORCEMENT', 'strict'),
        },
        'logging': {
            'enable_request_logging': os.getenv('ENABLE_REQUEST_LOGGING', 'true').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        }
    }
    
    # For Future - Enterprise Grade: Advanced configuration loading
    # Load additional enterprise features from environment
    
    return ProxyConfig(**config_data)

# Global config instance
config = load_config()

# For Future - Enterprise Grade: Configuration validation and monitoring
def validate_config():
    """For Future - Enterprise Grade: Validate configuration on startup."""
    pass

def monitor_config_changes():
    """For Future - Enterprise Grade: Monitor configuration changes."""
    pass

def reload_config():
    """For Future - Enterprise Grade: Reload configuration without restart."""
    pass 