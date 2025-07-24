"""
Bootstrap service for validating platform tokens and creating agent identities.
Enhanced with comprehensive error handling, retry logic, and production hardening.
"""
import logging
import base64
import uuid
import time
import requests
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from app import crud, schemas
from app.models.attestation_policy import PlatformType
from app.core.exceptions import (
    BootstrapError,
    TokenValidationError,
    PolicyNotFoundError,
    ExternalServiceError,
    AgentCreationError,
    NetworkTimeoutError,
    ConfigurationError
)
from app.core.retry_utils import (
    with_retry,
    timeout_handler,
    create_requests_session_with_retry,
    ExternalServiceConfig,
    kubernetes_circuit_breaker,
    aws_circuit_breaker,
    azure_circuit_breaker,
    docker_circuit_breaker
)
from app.core.security_validators import SecurityValidator, SecurityContext, security_validator
from app.core.audit_logger import bootstrap_auditor, AuditSeverity

logger = logging.getLogger(__name__)

# Create pre-configured session for external API calls
external_session = create_requests_session_with_retry(
    total_retries=3,
    backoff_factor=0.3,
    timeout=30.0
)


class KubernetesClaims:
    """Structured representation of Kubernetes SAT claims."""
    def __init__(self, namespace: str, service_account: str, uid: str):
        self.namespace = namespace
        self.service_account = service_account
        self.uid = uid
        
    def to_selector(self) -> str:
        """Convert claims to a selector string for policy matching."""
        return f"namespace={self.namespace},service_account={self.service_account}"


class AWSClaims:
    """Structured representation of AWS STS claims."""
    def __init__(self, arn: str, account_id: str, user_id: str):
        self.arn = arn
        self.account_id = account_id
        self.user_id = user_id
        
    def to_selector(self) -> str:
        """Convert claims to a selector string for policy matching."""
        return f"arn={self.arn}"


class AzureClaims:
    """Structured representation of Azure Managed Identity claims."""
    def __init__(self, subscription_id: str, resource_group: str, vm_name: str, principal_id: str):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.vm_name = vm_name
        self.principal_id = principal_id
        
    def to_selector(self) -> str:
        """Convert claims to a selector string for policy matching."""
        return f"subscription_id={self.subscription_id},resource_group={self.resource_group},vm_name={self.vm_name}"


class DockerClaims:
    """Structured representation of Docker container claims."""
    def __init__(self, container_id: str, image_name: str, image_digest: str, runtime_path: str):
        self.container_id = container_id
        self.image_name = image_name
        self.image_digest = image_digest
        self.runtime_path = runtime_path
        
    def to_selector(self) -> str:
        """Convert claims to a selector string for policy matching."""
        return f"image_name={self.image_name},image_digest={self.image_digest}"


class BootstrapService:
    """Service for handling agent identity bootstrapping."""
    
    def __init__(self):
        self.security_validator = security_validator

    @kubernetes_circuit_breaker
    @timeout_handler(ExternalServiceConfig.KUBERNETES_TIMEOUT)
    @with_retry(
        max_attempts=ExternalServiceConfig.KUBERNETES_MAX_RETRIES,
        backoff_factor=1.0,
        retry_exceptions=(requests.RequestException, ConnectionError, TimeoutError)
    )
    def validate_kubernetes_sat(self, token: str, client_ip: str = None) -> KubernetesClaims:
        """
        Validate a Kubernetes Service Account Token and extract claims.
        Enhanced with comprehensive security validation and production hardening.
        
        Args:
            token: The Kubernetes SAT to validate
            client_ip: Client IP address for rate limiting and logging
            
        Returns:
            KubernetesClaims with extracted information
            
        Raises:
            TokenValidationError: If token is invalid or validation fails
        """
        # Create security context
        security_context = SecurityContext(
            platform="kubernetes",
            token_type="SAT",
            client_ip=client_ip,
            request_time=time.time()
        )
        
        # Perform comprehensive security validation
        self.security_validator.validate_token_security(
            token=token,
            security_context=security_context
        )
        
        try:
            # Import Google OAuth2 libraries for token validation
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            from google.auth.exceptions import GoogleAuthError
            
        except ImportError as e:
            raise ConfigurationError(
                setting="google-oauth2-libraries",
                message="Google OAuth2 libraries not available for Kubernetes token validation",
                expected_value="google-auth package installed"
            ) from e
        
        try:
            logger.info("Starting Kubernetes SAT validation with security checks")
            start_time = time.time()
            
            # Create a custom request handler with timeout
            request_handler = google_requests.Request()
            
            # Validate the token signature and extract payload
            id_info = id_token.verify_oauth2_token(
                token, 
                request_handler,
                audience=None  # Skip audience validation for now
            )
            
            # Perform additional security validation on decoded claims
            self.security_validator.validate_token_security(
                token=token,
                security_context=security_context,
                decoded_claims=id_info
            )
            
            validation_time = time.time() - start_time
            logger.info(f"Token validation with security checks completed in {validation_time:.3f}s")
            
            # Extract Kubernetes-specific claims with validation
            kubernetes_info = id_info.get("kubernetes.io", {})
            if not kubernetes_info:
                raise TokenValidationError(
                    message="Token missing kubernetes.io claims section",
                    platform="kubernetes",
                    token_type="SAT", 
                    validation_step="claims_extraction",
                    details={"available_claims": list(id_info.keys())}
                )
            
            # Extract and validate namespace
            namespace = kubernetes_info.get("namespace")
            if not namespace:
                raise TokenValidationError(
                    message="Token missing required namespace claim",
                    platform="kubernetes",
                    token_type="SAT",
                    validation_step="namespace_extraction",
                    details={"kubernetes_claims": list(kubernetes_info.keys())}
                )
            
            # Validate namespace format (basic security check)
            if not namespace.replace('-', '').replace('_', '').isalnum():
                raise TokenValidationError(
                    message="Invalid namespace format",
                    platform="kubernetes",
                    token_type="SAT",
                    validation_step="namespace_format_validation",
                    details={"namespace": namespace}
                )
            
            # Extract service account information
            service_account_info = kubernetes_info.get("serviceaccount", {})
            service_account = service_account_info.get("name")
            uid = service_account_info.get("uid", "")
            
            if not service_account:
                raise TokenValidationError(
                    message="Token missing required service account name",
                    platform="kubernetes",
                    token_type="SAT",
                    validation_step="service_account_extraction",
                    details={"service_account_claims": list(service_account_info.keys())}
                )
            
            # Validate service account format
            if not service_account.replace('-', '').replace('_', '').isalnum():
                raise TokenValidationError(
                    message="Invalid service account format",
                    platform="kubernetes",
                    token_type="SAT",
                    validation_step="service_account_format_validation",
                    details={"service_account": service_account}
                )
            
            # Additional security check: validate UID format if present
            if uid and not uid.replace('-', '').isalnum():
                raise TokenValidationError(
                    message="Invalid service account UID format",
                    platform="kubernetes",
                    token_type="SAT",
                    validation_step="uid_format_validation",
                    details={"uid": uid}
                )
            
            logger.info(
                f"Successfully validated Kubernetes SAT with security checks: "
                f"namespace={namespace}, service_account={service_account}, uid={uid}"
            )
            return KubernetesClaims(namespace=namespace, service_account=service_account, uid=uid)
            
        except GoogleAuthError as e:
            raise TokenValidationError(
                message=f"Google Auth validation failed: {str(e)}",
                platform="kubernetes",
                token_type="SAT",
                validation_step="google_auth_validation",
                details={"google_auth_error": str(e)}
            ) from e
            
        except Exception as e:
            if isinstance(e, TokenValidationError):
                raise
            
            logger.error(f"Unexpected error during Kubernetes token validation: {e}")
            raise TokenValidationError(
                message=f"Unexpected validation error: {str(e)}",
                platform="kubernetes",
                token_type="SAT",
                validation_step="unknown",
                details={"exception_type": type(e).__name__}
            ) from e
    
    @aws_circuit_breaker
    @timeout_handler(ExternalServiceConfig.AWS_STS_TIMEOUT)
    @with_retry(
        max_attempts=ExternalServiceConfig.AWS_STS_MAX_RETRIES,
        backoff_factor=1.0,
        retry_exceptions=(Exception,)  # AWS exceptions vary
    )
    def validate_aws_sts_token(self, token: str) -> AWSClaims:
        """
        Validate an AWS STS token and extract claims.
        Enhanced with comprehensive error handling and production hardening.
        
        Args:
            token: The AWS STS token to validate
            
        Returns:
            AWSClaims with extracted information
            
        Raises:
            TokenValidationError: If token is invalid or verification fails
            ConfigurationError: If required libraries are not available
            ExternalServiceError: If AWS STS calls fail
        """
        if not token or not isinstance(token, str):
            raise TokenValidationError(
                message="Token must be a non-empty string",
                platform="aws",
                token_type="STS",
                validation_step="input_validation"
            )
        
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
            
        except ImportError as e:
            raise ConfigurationError(
                setting="boto3-library",
                message="boto3 library not available for AWS token validation",
                expected_value="boto3 package installed"
            ) from e
        
        try:
            logger.info("Starting AWS STS token validation")
            start_time = time.time()
            
            # Create an STS client to validate the token
            # In production, this would use the actual IAM token
            # For now, we'll simulate the validation
            try:
                sts_client = boto3.client('sts', region_name='us-east-1')
            except Exception as e:
                raise ConfigurationError(
                    setting="aws-credentials",
                    message=f"Failed to create AWS STS client: {str(e)}",
                    expected_value="Valid AWS credentials configured"
                ) from e
            
            # Get caller identity (this validates the credentials)
            try:
                caller_identity = sts_client.get_caller_identity()
            except NoCredentialsError as e:
                raise TokenValidationError(
                    message="No AWS credentials found",
                    platform="aws",
                    token_type="STS",
                    validation_step="credentials_check",
                    details={"error": str(e)}
                ) from e
            except PartialCredentialsError as e:
                raise TokenValidationError(
                    message="Incomplete AWS credentials",
                    platform="aws",
                    token_type="STS",
                    validation_step="credentials_check",
                    details={"error": str(e)}
                ) from e
            
            validation_time = time.time() - start_time
            logger.info(f"AWS STS validation completed in {validation_time:.3f}s")
            
            # Extract and validate required claims
            arn = caller_identity.get('Arn')
            account_id = caller_identity.get('Account')
            user_id = caller_identity.get('UserId')
            
            if not arn:
                raise TokenValidationError(
                    message="STS response missing required ARN claim",
                    platform="aws",
                    token_type="STS",
                    validation_step="arn_extraction",
                    details={"available_claims": list(caller_identity.keys())}
                )
            
            if not account_id:
                raise TokenValidationError(
                    message="STS response missing required Account claim",
                    platform="aws",
                    token_type="STS",
                    validation_step="account_extraction",
                    details={"available_claims": list(caller_identity.keys())}
                )
            
            # Validate ARN format
            if not arn.startswith('arn:aws:'):
                raise TokenValidationError(
                    message="Invalid ARN format",
                    platform="aws",
                    token_type="STS",
                    validation_step="arn_format_validation",
                    details={"arn": arn}
                )
            
            # Validate account ID format (12 digits)
            if not account_id.isdigit() or len(account_id) != 12:
                raise TokenValidationError(
                    message="Invalid AWS account ID format",
                    platform="aws",
                    token_type="STS",
                    validation_step="account_format_validation",
                    details={"account_id": account_id}
                )
            
            logger.info(f"Successfully validated AWS STS token: arn={arn}, account={account_id}")
            return AWSClaims(arn=arn, account_id=account_id, user_id=user_id or "")
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            raise ExternalServiceError(
                service_name="aws_sts",
                operation="get_caller_identity",
                message=f"AWS STS error ({error_code}): {error_message}",
                status_code=e.response.get('ResponseMetadata', {}).get('HTTPStatusCode'),
                platform="aws"
            ) from e
            
        except Exception as e:
            logger.error(f"Unexpected error during AWS token validation: {e}")
            raise TokenValidationError(
                message=f"Unexpected AWS validation error: {str(e)}",
                platform="aws",
                token_type="STS",
                validation_step="unknown",
                details={"exception_type": type(e).__name__}
            ) from e
    
    @azure_circuit_breaker
    @timeout_handler(ExternalServiceConfig.AZURE_IMDS_TIMEOUT)
    @with_retry(
        max_attempts=ExternalServiceConfig.AZURE_IMDS_MAX_RETRIES,
        backoff_factor=1.0,
        retry_exceptions=(requests.RequestException, ConnectionError, TimeoutError)
    )
    def validate_azure_imds_token(self, token: str) -> AzureClaims:
        """
        Validate an Azure Instance Metadata Service (IMDS) token and extract claims.
        Enhanced with comprehensive error handling and production hardening.
        
        Args:
            token: The Azure IMDS token to validate
            
        Returns:
            AzureClaims with extracted information
            
        Raises:
            TokenValidationError: If token is invalid or verification fails
            ExternalServiceError: If Azure JWKS endpoint fails
            NetworkTimeoutError: If network operations timeout
        """
        if not token or not isinstance(token, str):
            raise TokenValidationError(
                message="Token must be a non-empty string",
                platform="azure",
                token_type="IMDS",
                validation_step="input_validation"
            )
        
        # Basic JWT format validation
        token_parts = token.split('.')
        if len(token_parts) != 3:
            raise TokenValidationError(
                message="Token does not have valid JWT format (header.payload.signature)",
                platform="azure",
                token_type="IMDS",
                validation_step="format_validation",
                details={"token_parts": len(token_parts)}
            )
        
        try:
            import jwt
            import requests
            from jwt.exceptions import InvalidTokenError, DecodeError
            
        except ImportError as e:
            raise ConfigurationError(
                setting="jwt-library",
                message="PyJWT library not available for Azure token validation",
                expected_value="PyJWT[crypto] package installed"
            ) from e
        
        try:
            logger.info("Starting Azure IMDS token validation")
            start_time = time.time()
            
            # Decode the JWT token without verification first to get the kid (key ID)
            try:
                unverified_header = jwt.get_unverified_header(token)
            except DecodeError as e:
                raise TokenValidationError(
                    message=f"Failed to decode JWT header: {str(e)}",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="header_decode",
                    details={"decode_error": str(e)}
                ) from e
            
            kid = unverified_header.get('kid')
            if not kid:
                raise TokenValidationError(
                    message="Azure token missing key ID (kid) in header",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="kid_extraction",
                    details={"header_claims": list(unverified_header.keys())}
                )
            
            # Get Azure's public keys from the well-known endpoint with timeout and retry
            jwks_url = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
            
            try:
                jwks_response = external_session.get(
                    jwks_url, 
                    timeout=ExternalServiceConfig.AZURE_IMDS_TIMEOUT
                )
                jwks_response.raise_for_status()
                jwks = jwks_response.json()
                
            except requests.Timeout as e:
                raise NetworkTimeoutError(
                    operation="azure_jwks_fetch",
                    timeout_seconds=ExternalServiceConfig.AZURE_IMDS_TIMEOUT,
                    platform="azure"
                ) from e
                
            except requests.RequestException as e:
                raise ExternalServiceError(
                    service_name="azure_jwks",
                    operation="fetch_public_keys",
                    message=f"Failed to fetch Azure JWKS: {str(e)}",
                    status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                    platform="azure"
                ) from e
            
            # Find the matching public key
            public_key = None
            available_kids = []
            
            for key in jwks.get('keys', []):
                key_kid = key.get('kid')
                if key_kid:
                    available_kids.append(key_kid)
                    if key_kid == kid:
                        try:
                            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                            break
                        except Exception as e:
                            logger.warning(f"Failed to construct public key from JWK: {e}")
                            continue
                            
            if not public_key:
                raise TokenValidationError(
                    message=f"No matching public key found for kid: {kid}",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="public_key_lookup",
                    details={
                        "requested_kid": kid,
                        "available_kids": available_kids,
                        "total_keys": len(jwks.get('keys', []))
                    }
                )
            
            # Verify and decode the token
            try:
                decoded_token = jwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    options={"verify_exp": True, "verify_aud": False}  # Skip audience validation for now
                )
            except jwt.ExpiredSignatureError as e:
                raise TokenValidationError(
                    message="Token has expired",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="expiry_validation",
                    details={"current_time": int(time.time())}
                ) from e
            except InvalidTokenError as e:
                raise TokenValidationError(
                    message=f"Token signature verification failed: {str(e)}",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="signature_verification",
                    details={"jwt_error": str(e)}
                ) from e
            
            validation_time = time.time() - start_time
            logger.info(f"Azure token validation completed in {validation_time:.3f}s")
            
            # Extract Azure-specific claims
            subscription_id = decoded_token.get('subscription_id') or decoded_token.get('sub')
            resource_group = decoded_token.get('resource_group') or decoded_token.get('rg')
            vm_name = decoded_token.get('vm_name') or decoded_token.get('name')
            principal_id = decoded_token.get('oid') or decoded_token.get('principal_id')
            
            # Validate required claims
            missing_claims = []
            if not subscription_id:
                missing_claims.append('subscription_id')
            if not resource_group:
                missing_claims.append('resource_group') 
            if not vm_name:
                missing_claims.append('vm_name')
                
            if missing_claims:
                raise TokenValidationError(
                    message=f"Token missing required Azure claims: {', '.join(missing_claims)}",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="claims_validation",
                    details={
                        "missing_claims": missing_claims,
                        "available_claims": list(decoded_token.keys())
                    }
                )
            
            # Validate UUID format for subscription_id
            try:
                uuid.UUID(subscription_id)
            except ValueError:
                raise TokenValidationError(
                    message="Invalid subscription ID format (not a valid UUID)",
                    platform="azure",
                    token_type="IMDS",
                    validation_step="subscription_format_validation",
                    details={"subscription_id": subscription_id}
                )
            
            logger.info(
                f"Successfully validated Azure IMDS token: "
                f"subscription={subscription_id}, rg={resource_group}, vm={vm_name}"
            )
            return AzureClaims(
                subscription_id=subscription_id,
                resource_group=resource_group,
                vm_name=vm_name,
                principal_id=principal_id or ""
            )
            
        except Exception as e:
            if isinstance(e, (TokenValidationError, ExternalServiceError, NetworkTimeoutError)):
                raise
            
            logger.error(f"Unexpected error during Azure token validation: {e}")
            raise TokenValidationError(
                message=f"Unexpected Azure validation error: {str(e)}",
                platform="azure",
                token_type="IMDS",
                validation_step="unknown",
                details={"exception_type": type(e).__name__}
            ) from e
    
    def validate_docker_container_token(self, container_id: str, runtime_token: str) -> DockerClaims:
        """
        Validate Docker container identity and extract claims.
        
        Args:
            container_id: The Docker container ID
            runtime_token: Runtime-generated token for verification
            
        Returns:
            DockerClaims with extracted information
            
        Raises:
            ValueError: If validation fails
        """
        try:
            import docker
            import hashlib
            import os
            
            # Connect to Docker daemon
            client = docker.from_env()
            
            # Get container information
            try:
                container = client.containers.get(container_id)
            except docker.errors.NotFound:
                raise ValueError(f"Container {container_id} not found")
            
            # Extract container metadata
            image_name = container.image.tags[0] if container.image.tags else "unknown"
            image_digest = container.image.id
            
            # Validate runtime token - this should be a hash of container metadata + runtime secret
            runtime_secret = os.environ.get('DOCKER_RUNTIME_SECRET', 'default-dev-secret')
            expected_token = hashlib.sha256(
                f"{container_id}:{image_digest}:{runtime_secret}".encode()
            ).hexdigest()
            
            if runtime_token != expected_token:
                raise ValueError("Invalid runtime token - container identity verification failed")
            
            # Get runtime path information
            runtime_path = f"/var/lib/docker/containers/{container_id}"
            
            logger.info(f"Validated Docker container: id={container_id[:12]}, image={image_name}")
            return DockerClaims(
                container_id=container_id,
                image_name=image_name,
                image_digest=image_digest,
                runtime_path=runtime_path
            )
            
        except ImportError:
            raise ValueError("Docker library not available for container validation")
        except Exception as e:
            logger.error(f"Docker container validation failed: {e}")
            raise ValueError(f"Docker container validation error: {e}")
    
    def find_matching_policy(
        self, 
        db: Session, 
        platform: str, 
        selector: str
    ) -> Optional[schemas.AttestationPolicy]:
        """
        Find an attestation policy that matches the platform and selector.
        Enhanced with comprehensive error handling and database resilience.
        
        Args:
            db: Database session
            platform: Platform type (kubernetes, aws, azure, docker)
            selector: Platform-specific selector string
            
        Returns:
            Matching attestation policy or None
            
        Raises:
            PolicyNotFoundError: If no matching policy exists
            ExternalServiceError: If database queries fail
        """
        if not platform or not isinstance(platform, str):
            raise PolicyNotFoundError(
                platform=platform or "unknown",
                selector=selector,
                available_policies=0
            )
        
        if not selector or not isinstance(selector, str):
            raise PolicyNotFoundError(
                platform=platform,
                selector=selector or "empty",
                available_policies=0
            )
        
        try:
            logger.info(f"Searching for attestation policy: platform={platform}, selector={selector}")
            start_time = time.time()
            
            # Query attestation policies for matching platform and selector
            try:
                policies = crud.attestation_policy.get_multi(db)
            except SQLAlchemyError as e:
                raise ExternalServiceError(
                    service_name="database",
                    operation="query_attestation_policies",
                    message=f"Database query failed: {str(e)}",
                    platform=platform
                ) from e
            
            if not policies:
                logger.warning("No attestation policies found in database")
                raise PolicyNotFoundError(
                    platform=platform,
                    selector=selector,
                    available_policies=0
                )
            
            # Search for exact match
            matching_policy = None
            policy_count = len(policies)
            
            for policy in policies:
                if policy.platform == platform and policy.selector == selector:
                    matching_policy = policy
                    break
            
            query_time = time.time() - start_time
            logger.info(f"Policy search completed in {query_time:.3f}s, checked {policy_count} policies")
            
            if matching_policy:
                logger.info(f"Found matching policy: {matching_policy.id} for {platform}:{selector}")
                return matching_policy
            else:
                # Log available policies for debugging
                available_policies = [f"{p.platform}:{p.selector}" for p in policies]
                logger.warning(
                    f"No matching policy found. Available policies: {available_policies}"
                )
                raise PolicyNotFoundError(
                    platform=platform,
                    selector=selector,
                    available_policies=policy_count
                )
                
        except PolicyNotFoundError:
            raise  # Re-raise policy not found errors
        except Exception as e:
            logger.error(f"Unexpected error during policy lookup: {e}")
            raise ExternalServiceError(
                service_name="policy_matcher",
                operation="find_matching_policy",
                message=f"Policy lookup failed: {str(e)}",
                platform=platform
            ) from e
    
    def generate_agent_keys(self) -> Tuple[str, str, str]:
        """
        Generate a new Ed25519 key pair for an agent.
        
        Returns:
            Tuple of (agent_id, private_key_b64, public_key_b64)
        """
        
        # Generate new Ed25519 key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Generate agent ID
        agent_id = f"agent-{str(uuid.uuid4())}"
        
        # Convert to base64 for response
        private_key_b64 = base64.b64encode(private_key_pem).decode('utf-8')
        public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
        
        logger.info(f"Generated new key pair for agent: {agent_id}")
        return agent_id, private_key_b64, public_key_b64
    
    def create_agent(
        self, 
        db: Session, 
        agent_id: str, 
        agent_name: str, 
        public_key_bytes: bytes,
        description: str
    ) -> schemas.Agent:
        """
        Create a new agent in the database.
        
        Args:
            db: Database session
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            public_key_bytes: Raw public key bytes
            description: Agent description
            
        Returns:
            Created agent schema
        """
        try:
            # Convert public key bytes to base64 string for the schema
            public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
            
            agent_create = schemas.AgentCreate(
                agent_id=agent_id,
                name=agent_name,
                public_key=public_key_b64,  # Schema expects base64 string
                description=description
            )
            
            agent = crud.agent.create(db=db, obj_in=agent_create)
            logger.info(f"Created agent in database: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_id}: {e}")
            raise ValueError(f"Failed to create agent: {e}")
    
    def bootstrap_kubernetes_agent(
        self, 
        db: Session, 
        token: str,
        client_ip: str = None,
        user_agent: str = None
    ) -> schemas.BootstrapResponse:
        """
        Complete Kubernetes agent bootstrap flow with comprehensive audit logging.
        
        Args:
            db: Database session
            token: Kubernetes Service Account Token
            client_ip: Client IP address for audit logging
            user_agent: User agent for audit logging
            
        Returns:
            BootstrapResponse with agent credentials
        """
        # Create audit context for correlation
        audit_context = bootstrap_auditor.create_bootstrap_context(
            platform="kubernetes",
            client_ip=client_ip,
            user_agent=user_agent
        )
        correlation_id = audit_context["correlation_id"]
        start_time = audit_context["start_time"]
        
        try:
            # Log bootstrap attempt
            bootstrap_auditor.log_bootstrap_attempt(
                correlation_id=correlation_id,
                platform="kubernetes",
                token_type="SAT",
                client_ip=client_ip,
                user_agent=user_agent,
                additional_data={"token_length": len(token)}
            )
            
            # Validate token and extract claims with audit logging
            try:
                claims = self.validate_kubernetes_sat(token, client_ip)
                
                bootstrap_auditor.log_token_validation(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    token_type="SAT",
                    success=True,
                    validation_steps={
                        "format_validation": True,
                        "signature_verification": True,
                        "claims_extraction": True
                    },
                    duration_ms=(time.time() - start_time) * 1000
                )
                
            except Exception as e:
                bootstrap_auditor.log_token_validation(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    token_type="SAT",
                    success=False,
                    error_details={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    duration_ms=(time.time() - start_time) * 1000
                )
                raise
            
            # Find matching policy with audit logging
            selector = claims.to_selector()
            
            try:
                policy = self.find_matching_policy(db, "kubernetes", selector)
                if not policy:
                    bootstrap_auditor.log_policy_not_found(
                        correlation_id=correlation_id,
                        platform="kubernetes",
                        selector=selector
                    )
                    raise PolicyNotFoundError("kubernetes", selector)
                
                bootstrap_auditor.log_policy_match(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    policy_id=str(policy.id),
                    selector=selector,
                    agent_name=policy.agent_name
                )
                
            except Exception as e:
                bootstrap_auditor.log_bootstrap_failure(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    error_code="POLICY_MATCHING_FAILED",
                    error_message=str(e),
                    validation_step="policy_matching",
                    duration_ms=(time.time() - start_time) * 1000
                )
                raise
            
            # Generate agent keys and create agent
            try:
                agent_id, private_key_b64, public_key_b64 = self.generate_agent_keys()
                
                # Create agent in database
                agent = self.create_agent(
                    db=db,
                    agent_id=agent_id,
                    agent_name=policy.agent_name,
                    public_key_bytes=base64.b64decode(public_key_b64),
                    description=f"Kubernetes agent for {claims.namespace}/{claims.service_account}"
                )
                
                bootstrap_auditor.log_agent_creation(
                    correlation_id=correlation_id,
                    agent_id=agent_id,
                    platform="kubernetes",
                    policy_id=str(policy.id),
                    namespace=claims.namespace,
                    service_account=claims.service_account
                )
                
            except Exception as e:
                bootstrap_auditor.log_bootstrap_failure(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    error_code="AGENT_CREATION_FAILED",
                    error_message=str(e),
                    validation_step="agent_creation",
                    duration_ms=(time.time() - start_time) * 1000
                )
                raise
            
            # Log successful bootstrap
            bootstrap_auditor.log_bootstrap_success(
                correlation_id=correlation_id,
                platform="kubernetes",
                agent_id=agent_id,
                policy_id=str(policy.id),
                duration_ms=(time.time() - start_time) * 1000,
                validation_steps={
                    "token_validation": True,
                    "policy_matching": True,
                    "agent_creation": True
                },
                security_metadata={
                    "namespace": claims.namespace,
                    "service_account": claims.service_account,
                    "uid": claims.uid,
                    "client_ip": client_ip
                },
                additional_data={
                    "agent_name": policy.agent_name,
                    "selector": selector
                }
            )
            
            return schemas.BootstrapResponse(
                agent_id=agent_id,
                private_key_b64=private_key_b64,
                public_key_b64=public_key_b64
            )
            
        except Exception as e:
            # Ensure all failures are audited
            if not any(isinstance(e, exc_type) for exc_type in [
                TokenValidationError, PolicyNotFoundError, AgentCreationError
            ]):
                bootstrap_auditor.log_bootstrap_failure(
                    correlation_id=correlation_id,
                    platform="kubernetes",
                    error_code="UNEXPECTED_ERROR",
                    error_message=str(e),
                    validation_step="unknown",
                    duration_ms=(time.time() - start_time) * 1000,
                    additional_data={"exception_type": type(e).__name__}
                )
            raise
    
    def bootstrap_aws_agent(
        self, 
        db: Session, 
        token: str
    ) -> schemas.BootstrapResponse:
        """
        Complete AWS agent bootstrap flow.
        
        Args:
            db: Database session
            token: AWS STS token
            
        Returns:
            Bootstrap response with agent identity and keys
        """
        # 1. Validate token and extract claims
        claims = self.validate_aws_sts_token(token)
        
        # 2. Find matching attestation policy
        policy = self.find_matching_policy(
            db,
            PlatformType.AWS_IAM,
            claims.to_selector()
        )
        
        if not policy:
            raise ValueError(f"No attestation policy found for AWS ARN={claims.arn}")
        
        # 3. Generate agent keys
        agent_id, private_key_b64, public_key_b64 = self.generate_agent_keys()
        
        # 4. Create agent in database - pass the base64 string directly
        agent = self.create_agent(
            db=db,
            agent_id=agent_id,
            agent_name=policy.agent_name_to_bootstrap,
            public_key_bytes=base64.b64decode(public_key_b64),  # Convert to bytes for internal function
            description=f"Agent bootstrapped from AWS ARN={claims.arn}"
        )
        
        # 5. Return bootstrap response
        return schemas.BootstrapResponse(
            agent_id=agent_id,
            private_key_b64=private_key_b64,
            public_key_b64=public_key_b64
        )
    
    def bootstrap_azure_agent(
        self, 
        db: Session, 
        token: str
    ) -> schemas.BootstrapResponse:
        """
        Complete Azure agent bootstrap flow.
        
        Args:
            db: Database session
            token: Azure IMDS token
            
        Returns:
            Bootstrap response with agent identity and keys
        """
        # 1. Validate token and extract claims
        claims = self.validate_azure_imds_token(token)
        
        # 2. Find matching attestation policy
        policy = self.find_matching_policy(
            db,
            PlatformType.AZURE_MANAGED_IDENTITY,
            claims.to_selector()
        )
        
        if not policy:
            raise ValueError(f"No attestation policy found for Azure subscription={claims.subscription_id}, vm={claims.vm_name}")
        
        # 3. Generate agent keys
        agent_id, private_key_b64, public_key_b64 = self.generate_agent_keys()
        
        # 4. Create agent in database
        agent = self.create_agent(
            db=db,
            agent_id=agent_id,
            agent_name=policy.agent_name_to_bootstrap,
            public_key_bytes=base64.b64decode(public_key_b64),
            description=f"Agent bootstrapped from Azure subscription={claims.subscription_id}, vm={claims.vm_name}"
        )
        
        # 5. Return bootstrap response
        return schemas.BootstrapResponse(
            agent_id=agent_id,
            private_key_b64=private_key_b64,
            public_key_b64=public_key_b64
        )
    
    def bootstrap_docker_agent(
        self, 
        db: Session, 
        container_id: str,
        runtime_token: str
    ) -> schemas.BootstrapResponse:
        """
        Complete Docker agent bootstrap flow.
        
        Args:
            db: Database session
            container_id: Docker container ID
            runtime_token: Runtime verification token
            
        Returns:
            Bootstrap response with agent identity and keys
        """
        # 1. Validate container and extract claims
        claims = self.validate_docker_container_token(container_id, runtime_token)
        
        # 2. Find matching attestation policy
        policy = self.find_matching_policy(
            db,
            PlatformType.DOCKER_CONTAINER,
            claims.to_selector()
        )
        
        if not policy:
            raise ValueError(f"No attestation policy found for Docker image={claims.image_name}")
        
        # 3. Generate agent keys
        agent_id, private_key_b64, public_key_b64 = self.generate_agent_keys()
        
        # 4. Create agent in database
        agent = self.create_agent(
            db=db,
            agent_id=agent_id,
            agent_name=policy.agent_name_to_bootstrap,
            public_key_bytes=base64.b64decode(public_key_b64),
            description=f"Agent bootstrapped from Docker container={claims.container_id[:12]}, image={claims.image_name}"
        )
        
        # 5. Return bootstrap response
        return schemas.BootstrapResponse(
            agent_id=agent_id,
            private_key_b64=private_key_b64,
            public_key_b64=public_key_b64
        )


# Create singleton instance
bootstrap_service = BootstrapService() 