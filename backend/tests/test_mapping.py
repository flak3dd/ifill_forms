"""
Tests for Field Mapping API endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ..models import Profile, ProfileField, MappingSession, ColumnMapping


def test_auto_mapping(client: TestClient, session: Session):
    """Test AI-assisted field mapping."""
    # Create test profile with fields
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.commit()
    
    # Add fields
    fields = [
        ProfileField(
            id=str(uuid.uuid4()),
            name="firstName",
            label="First Name",
            field_type="text",
            semantic_tag="given_name",
            required=True,
            locator_type="label",
            locator_value="First Name",
            order_index=0,
            profile_id=profile.id
        ),
        ProfileField(
            id=str(uuid.uuid4()),
            name="lastName",
            label="Last Name",
            field_type="text",
            semantic_tag="family_name",
            required=True,
            locator_type="label",
            locator_value="Last Name",
            order_index=1,
            profile_id=profile.id
        ),
        ProfileField(
            id=str(uuid.uuid4()),
            name="email",
            label="Email",
            field_type="email",
            semantic_tag="email",
            required=True,
            locator_type="label",
            locator_value="Email",
            order_index=2,
            profile_id=profile.id
        )
    ]
    for field in fields:
        session.add(field)
    session.commit()
    
    # Test auto-mapping
    mapping_request = {
        "profile_id": profile.id,
        "csv_headers": ["first_name", "last_name", "email_address", "phone"],
        "csv_sample_rows": [
            {"first_name": "John", "last_name": "Doe", "email_address": "john@example.com", "phone": "555-1234"}
        ],
        "use_ai": False  # Use semantic matching only for test
    }
    
    response = client.post("/api/mapping/auto", json=mapping_request)
    assert response.status_code == 200
    data = response.json()
    
    assert "session_id" in data
    assert "suggestions" in data
    assert "unmapped_columns" in data
    assert "overall_confidence" in data
    
    # Verify semantic matching worked
    suggestions = data["suggestions"]
    assert len(suggestions) >= 2  # Should match first_name, last_name, email
    
    # Verify unmapped columns
    assert "phone" in data["unmapped_columns"]


def test_confirm_mapping(client: TestClient, session: Session):
    """Test confirming and saving field mappings."""
    # Create test profile and mapping session
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.flush()
    
    mapping_session = MappingSession(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        csv_headers=["first_name", "last_name", "email"],
        csv_sample_rows=[{"first_name": "John", "last_name": "Doe", "email": "john@example.com"}],
        is_complete=False
    )
    session.add(mapping_session)
    session.commit()
    
    # Add a field
    field = ProfileField(
        id=str(uuid.uuid4()),
        name="firstName",
        label="First Name",
        field_type="text",
        semantic_tag="given_name",
        locator_type="label",
        locator_value="First Name",
        order_index=0,
        profile_id=profile.id
    )
    session.add(field)
    session.commit()
    
    # Confirm mapping
    confirm_request = {
        "session_id": mapping_session.id,
        "mappings": [
            {
                "profile_id": profile.id,
                "csv_column_name": "first_name",
                "csv_sample_values": ["John", "Jane"],
                "field_id": field.id,
                "semantic_tag": "given_name",
                "transform_function": "title_case",
                "confidence": "high",
                "is_user_override": False
            }
        ],
        "save_as_default": True
    }
    
    response = client.post("/api/mapping/confirm", json=confirm_request)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["csv_column_name"] == "first_name"
    assert data[0]["field_id"] == field.id


def test_get_default_mapping(client: TestClient, session: Session):
    """Test retrieving default mappings."""
    # Create test profile with mappings
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.flush()
    
    field = ProfileField(
        id=str(uuid.uuid4()),
        name="email",
        label="Email",
        field_type="email",
        semantic_tag="email",
        locator_type="label",
        locator_value="Email",
        order_index=0,
        profile_id=profile.id
    )
    session.add(field)
    session.flush()
    
    # Add default mapping (no session_id = default)
    mapping = ColumnMapping(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        mapping_session_id=None,  # Default mapping
        csv_column_name="Email",
        field_id=field.id,
        semantic_tag="email",
        transform_function="email_clean",
        confidence="high"
    )
    session.add(mapping)
    session.commit()
    
    # Get default mappings
    response = client.get(f"/api/mapping/profile/{profile.id}/default")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["csv_column_name"] == "Email"


def test_mapping_session_details(client: TestClient, session: Session):
    """Test getting mapping session details."""
    # Create test profile and session
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.flush()
    
    mapping_session = MappingSession(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        csv_headers=["col1", "col2"],
        csv_sample_rows=[{"col1": "val1", "col2": "val2"}],
        is_complete=True
    )
    session.add(mapping_session)
    session.commit()
    
    # Get session details
    response = client.get(f"/api/mapping/sessions/{mapping_session.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mapping_session.id
    assert data["profile_id"] == profile.id
    assert data["csv_headers"] == ["col1", "col2"]
    assert data["is_complete"] is True


def test_update_mapping(client: TestClient, session: Session):
    """Test updating a column mapping."""
    # Create test profile with mapping
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.flush()
    
    mapping = ColumnMapping(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        csv_column_name="Name",
        semantic_tag="full_name",
        transform_function="title_case",
        confidence="medium"
    )
    session.add(mapping)
    session.commit()
    
    # Update mapping
    response = client.patch(
        f"/api/mapping/mappings/{mapping.id}",
        params={
            "semantic_tag": "given_name",
            "transform_function": "upper_case"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["semantic_tag"] == "given_name"
    assert data["transform_function"] == "upper_case"
    assert data["is_user_override"] is True


def test_delete_mapping(client: TestClient, session: Session):
    """Test deleting a column mapping."""
    # Create test profile with mapping
    profile = Profile(
        id=str(uuid.uuid4()),
        name="Test Profile",
        base_url="https://example.com",
        steps={},
        field_mappings={},
        success_indicators={},
        is_active=True
    )
    session.add(profile)
    session.flush()
    
    mapping = ColumnMapping(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        csv_column_name="ToDelete",
        semantic_tag="custom"
    )
    session.add(mapping)
    session.commit()
    
    # Delete mapping
    response = client.delete(f"/api/mapping/mappings/{mapping.id}")
    assert response.status_code == 200
    
    # Verify deletion
    result = session.get(ColumnMapping, mapping.id)
    assert result is None
