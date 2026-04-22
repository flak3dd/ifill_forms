"""
Pytest configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from ..main import app
from ..database import get_session
from ..models import Profile, ProfileField, WorkflowStep, ProfileVersion

# Create test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database tables."""
    SQLModel.metadata.create_all(engine)
    yield
    # Cleanup after all tests
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    """Create a test client."""
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def session():
    """Create a test database session."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_profile_data():
    """Sample profile data for testing."""
    return {
        "name": "Test LinkedIn Profile",
        "description": "Test profile for LinkedIn Easy Apply",
        "base_url": "https://www.linkedin.com/jobs",
        "steps": {},
        "field_mappings": {},
        "success_indicators": {},
        "ai_hints": {},
        "is_active": True
    }


@pytest.fixture
def sample_field_data():
    """Sample field data for testing."""
    return {
        "name": "firstName",
        "label": "First name",
        "field_type": "text",
        "semantic_tag": "given_name",
        "required": True,
        "locator_type": "label",
        "locator_value": "First name",
        "order_index": 0
    }


@pytest.fixture
def sample_step_data():
    """Sample workflow step data for testing."""
    return {
        "step_type": "fill",
        "name": "Personal Info",
        "description": "Fill personal information",
        "order_index": 0,
        "config": {}
    }


@pytest.fixture
def sample_mapping_data():
    """Sample mapping data for testing."""
    return {
        "csv_column_name": "First Name",
        "csv_sample_values": ["John", "Jane"],
        "semantic_tag": "given_name",
        "transform_function": "title_case",
        "confidence": "high"
    }
