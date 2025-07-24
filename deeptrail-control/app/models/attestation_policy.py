import enum

from sqlalchemy import Column, Enum, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class PlatformType(str, enum.Enum):
    KUBERNETES = "kubernetes"
    AWS_IAM = "aws_iam"
    AZURE_MANAGED_IDENTITY = "azure_managed_identity"
    DOCKER_CONTAINER = "docker_container"


class AttestationPolicy(Base):
    __tablename__ = "attestation_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    platform = Column(Enum(PlatformType), nullable=False)
    selector = Column(String, nullable=False, unique=True)
    agent_name_to_bootstrap = Column(String, nullable=False) 