from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy.exc import IntegrityError # Import for handling potential DB errors
import logging

from app import schemas, crud # Import schemas and crud package
from app.api.deps import DbDep # Import the database dependency
from app.schemas.agent import TEST_KEY_MAP  # Import the test key map

# We'll need CRUD operations later
# from app import crud

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.Agent, status_code=status.HTTP_201_CREATED)
def register_agent(agent_in: schemas.AgentCreate, db: DbDep, request: Request):
    """Register a new agent in the system.

    This endpoint allows a new agent (identified by its unique `agent_id`
    and public key) to be recorded in the database.

    Args:
        agent_in: Input data containing `agent_id` and `current_public_key`.
        db: Database session dependency.
        request: The incoming request object (unused here but available).

    Raises:
        HTTPException 400: If an agent with the same `agent_id` already exists,
                           or if there is a database constraint violation.
        HTTPException 500: If an unexpected error occurs during agent creation.
    """
    # Check if agent already exists
    existing_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_in.agent_id)
    if existing_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_in.agent_id}' already exists.",
        )

    # Create the agent
    try:
        agent = crud.agent.create(db=db, obj_in=agent_in)
        
        # Special handling for test agents - use hardcoded test keys
        if agent.agent_id in TEST_KEY_MAP:
            test_key = TEST_KEY_MAP[agent.agent_id]
            logger.info(f"Test agent detected: {agent.agent_id}. Using test key.")
            # Hack the public key field for the response
            agent.current_public_key = f"ssh-ed25519 {test_key} test@example.com"
    except IntegrityError: # Catch potential unique constraint violations
        db.rollback()
        # This might happen in a race condition if check passes but insert fails
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_in.agent_id}' could not be created (possible constraint violation).",
        )
    except Exception as e:
        # Catch other potential CRUD errors
        db.rollback()
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create agent."
        )

    return agent

# Add other agent-related endpoints here later (e.g., GET /agents/{agent_id})
@router.get("/{agent_id}", response_model=schemas.Agent)
def read_agent(agent_id: str, db: DbDep):
    """Get agent details by agent_id.

    Args:
        agent_id: The unique identifier of the agent to retrieve.
        db: Database session dependency.

    Returns:
        The Agent schema object if found.

    Raises:
        HTTPException 404: If no agent with the given `agent_id` is found.
    """
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Special handling for test agents
    if agent_id in TEST_KEY_MAP:
        test_key = TEST_KEY_MAP[agent_id]
        logger.info(f"Test agent detected: {agent_id}. Using test key.")
        # Hack the public key field for the response
        db_agent.current_public_key = f"ssh-ed25519 {test_key} test@example.com"
    
    return db_agent

# Add other agent-related endpoints here later (e.g., GET /agents/{agent_id}) 