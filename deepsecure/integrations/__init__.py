# Placeholder for future integration-wide imports or initializations
# For now, this makes 'integrations' a Python package.

DEEPSECURE_FRAMEWORK_LANGCHAIN = "LangChain"
DEEPSECURE_FRAMEWORK_CREWAI = "CrewAI"
DEEPSECURE_FRAMEWORK_AWS_STRANDS = "AWSStrands"


_initialized_frameworks = set()


def get_initialized_frameworks():
    """Returns a set of frameworks that have been initialized."""
    return _initialized_frameworks


def mark_as_initialized(framework_name: str):
    """Marks a framework as initialized."""
    _initialized_frameworks.add(framework_name)


def is_initialized(framework_name: str) -> bool:
    """Checks if a framework has been initialized."""
    return framework_name in _initialized_frameworks 