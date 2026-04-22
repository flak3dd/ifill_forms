"""
Tests for Profile Management API endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ..models import Profile, ProfileField, WorkflowStep, ProfileVersion


def test_list_profiles(client: TestClient, session: Session, sample_profile_data):
    """Test listing profiles."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    response = client.get("/api/profiles/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["name"] == sample_profile_data["name"] for p in data)


def test_create_profile(client: TestClient, sample_profile_data):
    """Test creating a new profile."""
    response = client.post("/api/profiles/", json=sample_profile_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_profile_data["name"]
    assert "id" in data
    assert "created_at" in data


def test_get_profile(client: TestClient, session: Session, sample_profile_data):
    """Test getting a profile by ID."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    response = client.get(f"/api/profiles/{profile.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == profile.id
    assert data["name"] == sample_profile_data["name"]
    assert "field_count" in data
    assert "step_count" in data


def test_get_profile_not_found(client: TestClient):
    """Test getting a non-existent profile."""
    response = client.get("/api/profiles/nonexistent-id")
    assert response.status_code == 404


def test_update_profile(client: TestClient, session: Session, sample_profile_data):
    """Test updating a profile."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    update_data = {"name": "Updated Profile Name"}
    response = client.patch(f"/api/profiles/{profile.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Profile Name"


def test_delete_profile(client: TestClient, session: Session, sample_profile_data):
    """Test deleting a profile."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    response = client.delete(f"/api/profiles/{profile.id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    response = client.get(f"/api/profiles/{profile.id}")
    assert response.status_code == 404


def test_profile_fields(client: TestClient, session: Session, sample_profile_data, sample_field_data):
    """Test profile field management."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    # Add field
    field_data = {**sample_field_data, "profile_id": profile.id}
    response = client.post(f"/api/profiles/{profile.id}/fields", json=field_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_field_data["name"]
    field_id = data["id"]
    
    # Get fields
    response = client.get(f"/api/profiles/{profile.id}/fields")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == sample_field_data["name"]
    
    # Update field
    update_data = {"label": "Updated Label"}
    response = client.patch(f"/api/profiles/{profile.id}/fields/{field_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["label"] == "Updated Label"
    
    # Delete field
    response = client.delete(f"/api/profiles/{profile.id}/fields/{field_id}")
    assert response.status_code == 200


def test_workflow_steps(client: TestClient, session: Session, sample_profile_data, sample_step_data):
    """Test workflow step management."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    # Add step
    step_data = {**sample_step_data, "profile_id": profile.id}
    response = client.post(f"/api/profiles/{profile.id}/steps", json=step_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_step_data["name"]
    step_id = data["id"]
    
    # Get steps
    response = client.get(f"/api/profiles/{profile.id}/steps")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    # Update step
    update_data = {"name": "Updated Step"}
    response = client.patch(f"/api/profiles/{profile.id}/steps/{step_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Step"
    
    # Delete step
    response = client.delete(f"/api/profiles/{profile.id}/steps/{step_id}")
    assert response.status_code == 200


def test_profile_versioning(client: TestClient, session: Session, sample_profile_data):
    """Test profile versioning."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    # Create version
    response = client.post(
        f"/api/profiles/{profile.id}/versions",
        params={"change_summary": "Test version"}
    )
    assert response.status_code == 200
    version_data = response.json()
    assert version_data["version_number"] == 1
    version_id = version_data["id"]
    
    # List versions
    response = client.get(f"/api/profiles/{profile.id}/versions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    # Get version details
    response = client.get(f"/api/profiles/{profile.id}/versions/{version_id}")
    assert response.status_code == 200
    data = response.json()
    assert "snapshot" in data
    
    # Restore version
    response = client.post(f"/api/profiles/{profile.id}/versions/{version_id}/restore")
    assert response.status_code == 200


def test_profile_fork(client: TestClient, session: Session, sample_profile_data):
    """Test forking a profile."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    # Fork profile
    fork_data = {"new_name": "Forked Profile", "description": "Forked description"}
    response = client.post(f"/api/profiles/{profile.id}/fork", json=fork_data)
    assert response.status_code == 200
    data = response.json()
    assert data["original_id"] == profile.id
    assert data["new_name"] == "Forked Profile"
    assert "new_id" in data


def test_profile_validation(client: TestClient, session: Session, sample_profile_data, sample_field_data):
    """Test profile validation."""
    # Create test profile
    profile = Profile(id=str(uuid.uuid4()), **sample_profile_data)
    session.add(profile)
    session.commit()
    
    # Add required field without locator
    field_data = {
        **sample_field_data,
        "profile_id": profile.id,
        "required": True,
        "locator_value": ""  # Empty locator
    }
    response = client.post(f"/api/profiles/{profile.id}/fields", json=field_data)
    assert response.status_code == 200
    
    # Validate - should have errors
    response = client.post(f"/api/profiles/{profile.id}/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0
