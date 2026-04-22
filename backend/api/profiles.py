"""
Enhanced Profile Management API Endpoints
Includes versioning, workflow builder, and field mapping
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlmodel import Session, select
from datetime import datetime

from ..database import get_session
from ..models import (
    Profile, ProfileField, WorkflowStep, ProfileVersion, 
    ColumnMapping, MappingSession
)
from ..schemas import (
    ProfileRead, ProfileCreate, ProfileUpdate, EnhancedProfileRead,
    ProfileFieldRead, ProfileFieldCreate, ProfileFieldUpdate,
    WorkflowStepRead, WorkflowStepCreate, WorkflowStepUpdate, WorkflowValidation,
    ProfileVersionRead, ProfileVersionDetail,
    MappingSessionRead, MappingSessionDetail, AutoMapRequest, AutoMapResponse,
    ConfirmMappingRequest, ProfileForkRequest, ProfileForkResponse,
    DetectFieldsRequest, DetectFieldsResponse, CreateProfileFromDetection
)
from ..services.ai_client import get_ai_client

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/", response_model=List[EnhancedProfileRead])
async def list_profiles(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    session: Session = Depends(get_session)
):
    """List profiles with filtering and metadata."""
    query = select(Profile)
    
    if status:
        query = query.where(Profile.status == status)
    
    if search:
        query = query.where(
            Profile.name.contains(search) | 
            Profile.description.contains(search)
        )
    
    profiles = session.exec(query.offset(offset).limit(limit)).all()
    
    # Enhance with metadata
    result = []
    for profile in profiles:
        field_count = session.exec(
            select(ProfileField).where(ProfileField.profile_id == profile.id)
        ).all()
        step_count = session.exec(
            select(WorkflowStep).where(WorkflowStep.profile_id == profile.id)
        ).all()
        
        # Get latest version
        latest_version = session.exec(
            select(ProfileVersion)
            .where(ProfileVersion.profile_id == profile.id)
            .order_by(ProfileVersion.version_number.desc())
        ).first()
        
        # Check for default mapping
        has_mapping = session.exec(
            select(ColumnMapping).where(ColumnMapping.profile_id == profile.id)
        ).first() is not None
        
        profile_data = EnhancedProfileRead(
            **profile.model_dump(),
            field_count=len(field_count),
            step_count=len(step_count),
            latest_version=latest_version.version_number if latest_version else profile.version,
            has_default_mapping=has_mapping
        )
        result.append(profile_data)
    
    return result


@router.post("/", response_model=ProfileRead)
async def create_profile(
    profile: ProfileCreate,
    session: Session = Depends(get_session)
):
    """Create a new profile."""
    db_profile = Profile.model_validate(profile)
    db_profile.id = str(uuid.uuid4())
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


@router.get("/{profile_id}", response_model=EnhancedProfileRead)
async def get_profile(
    profile_id: str,
    include_fields: bool = False,
    include_steps: bool = False,
    session: Session = Depends(get_session)
):
    """Get profile by ID with optional includes."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get counts
    field_count = len(profile.profile_fields) if include_fields else 0
    step_count = len(profile.workflow_steps) if include_steps else 0
    
    if not include_fields:
        field_count = session.exec(
            select(ProfileField).where(ProfileField.profile_id == profile_id)
        ).all()
        field_count = len(field_count)
    
    if not include_steps:
        step_count = session.exec(
            select(WorkflowStep).where(WorkflowStep.profile_id == profile_id)
        ).all()
        step_count = len(step_count)
    
    # Get latest version
    latest_version = session.exec(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile_id)
        .order_by(ProfileVersion.version_number.desc())
    ).first()
    
    # Check for default mapping
    has_mapping = session.exec(
        select(ColumnMapping).where(ColumnMapping.profile_id == profile_id)
    ).first() is not None
    
    return EnhancedProfileRead(
        **profile.model_dump(),
        field_count=field_count,
        step_count=step_count,
        latest_version=latest_version.version_number if latest_version else profile.version,
        has_default_mapping=has_mapping
    )


@router.patch("/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: str,
    update: ProfileUpdate,
    session: Session = Depends(get_session)
):
    """Update profile metadata."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """Delete a profile."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    session.delete(profile)
    session.commit()
    return {"message": "Profile deleted"}


# Profile Versioning Endpoints

@router.get("/{profile_id}/versions", response_model=List[ProfileVersionRead])
async def list_versions(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """List all versions of a profile."""
    versions = session.exec(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile_id)
        .order_by(ProfileVersion.version_number.desc())
    ).all()
    return versions


@router.post("/{profile_id}/versions", response_model=ProfileVersionRead)
async def create_version(
    profile_id: str,
    change_summary: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Create a new version snapshot of the profile."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get current state
    fields = session.exec(
        select(ProfileField).where(ProfileField.profile_id == profile_id)
    ).all()
    steps = session.exec(
        select(WorkflowStep).where(WorkflowStep.profile_id == profile_id)
    ).all()
    
    # Create snapshot
    snapshot = {
        "profile": profile.model_dump(),
        "fields": [f.model_dump() for f in fields],
        "steps": [s.model_dump() for s in steps],
        "field_mappings": profile.field_mappings
    }
    
    # Get next version number
    latest = session.exec(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile_id)
        .order_by(ProfileVersion.version_number.desc())
    ).first()
    
    next_version = (latest.version_number + 1) if latest else 1
    
    # Create version record
    version = ProfileVersion(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        version_number=next_version,
        snapshot=snapshot,
        change_summary=change_summary
    )
    
    # Update profile version
    profile.version = next_version
    
    session.add(version)
    session.add(profile)
    session.commit()
    session.refresh(version)
    
    return version


@router.get("/{profile_id}/versions/{version_id}", response_model=ProfileVersionDetail)
async def get_version(
    profile_id: str,
    version_id: str,
    session: Session = Depends(get_session)
):
    """Get a specific version with full snapshot."""
    version = session.get(ProfileVersion, version_id)
    if not version or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return version


@router.post("/{profile_id}/versions/{version_id}/restore", response_model=ProfileRead)
async def restore_version(
    profile_id: str,
    version_id: str,
    session: Session = Depends(get_session)
):
    """Restore profile to a previous version."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    version = session.get(ProfileVersion, version_id)
    if not version or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Restore from snapshot
    snapshot = version.snapshot
    
    # Update profile
    profile_data = snapshot.get("profile", {})
    for key, value in profile_data.items():
        if key not in ["id", "created_at"] and hasattr(profile, key):
            setattr(profile, key, value)
    
    # Delete current fields and steps
    for field in profile.profile_fields:
        session.delete(field)
    for step in profile.workflow_steps:
        session.delete(step)
    
    # Restore fields
    for field_data in snapshot.get("fields", []):
        field_data["id"] = str(uuid.uuid4())
        field_data["profile_id"] = profile_id
        field = ProfileField.model_validate(field_data)
        session.add(field)
    
    # Restore steps
    for step_data in snapshot.get("steps", []):
        step_data["id"] = str(uuid.uuid4())
        step_data["profile_id"] = profile_id
        step = WorkflowStep.model_validate(step_data)
        session.add(step)
    
    # Restore mappings
    profile.field_mappings = snapshot.get("field_mappings", {})
    
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    return profile


@router.post("/{profile_id}/fork", response_model=ProfileForkResponse)
async def fork_profile(
    profile_id: str,
    request: ProfileForkRequest,
    session: Session = Depends(get_session)
):
    """Create a copy of an existing profile."""
    original = session.get(Profile, profile_id)
    if not original:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Create new profile
    new_profile = Profile(
        id=str(uuid.uuid4()),
        name=request.new_name,
        description=request.description or original.description,
        base_url=original.base_url,
        version=1,
        steps=original.steps,
        field_mappings=original.field_mappings,
        success_indicators=original.success_indicators,
        ai_hints=original.ai_hints,
        is_active=True
    )
    
    session.add(new_profile)
    session.flush()  # Get the new profile ID
    
    # Copy fields
    for field in original.profile_fields:
        new_field = ProfileField(
            id=str(uuid.uuid4()),
            name=field.name,
            label=field.label,
            field_type=field.field_type,
            semantic_tag=field.semantic_tag,
            required=field.required,
            locator_type=field.locator_type,
            locator_value=field.locator_value,
            locator_fallback=field.locator_fallback,
            validation_regex=field.validation_regex,
            min_length=field.min_length,
            max_length=field.max_length,
            options=field.options,
            is_visible=field.is_visible,
            is_in_iframe=field.is_in_iframe,
            iframe_selector=field.iframe_selector,
            order_index=field.order_index,
            detection_confidence=field.detection_confidence,
            ai_reasoning=field.ai_reasoning,
            profile_id=new_profile.id
        )
        session.add(new_field)
    
    # Copy steps
    step_id_map = {}
    for step in original.workflow_steps:
        new_step = WorkflowStep(
            id=str(uuid.uuid4()),
            step_type=step.step_type,
            name=step.name,
            description=step.description,
            order_index=step.order_index,
            config=step.config,
            condition=step.condition,
            retry_count=step.retry_count,
            retry_delay_ms=step.retry_delay_ms,
            on_error=step.on_error,
            profile_id=new_profile.id,
            parent_step_id=None  # Will update after all steps created
        )
        session.add(new_step)
        step_id_map[step.id] = new_step.id
    
    session.flush()
    
    # Update parent_step_id references
    for step in original.workflow_steps:
        if step.parent_step_id and step.parent_step_id in step_id_map:
            new_step_id = step_id_map[step.id]
            new_parent_id = step_id_map[step.parent_step_id]
            new_step = session.get(WorkflowStep, new_step_id)
            new_step.parent_step_id = new_parent_id
            session.add(new_step)
    
    session.commit()
    
    return ProfileForkResponse(
        original_id=profile_id,
        new_id=new_profile.id,
        new_name=request.new_name
    )


# Field Management Endpoints

@router.get("/{profile_id}/fields", response_model=List[ProfileFieldRead])
async def get_profile_fields(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """Get all fields for a profile."""
    fields = session.exec(
        select(ProfileField)
        .where(ProfileField.profile_id == profile_id)
        .order_by(ProfileField.order_index)
    ).all()
    return fields


@router.post("/{profile_id}/fields", response_model=ProfileFieldRead)
async def add_field(
    profile_id: str,
    field: ProfileFieldCreate,
    session: Session = Depends(get_session)
):
    """Add a new field to a profile."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_field = ProfileField.model_validate(field)
    db_field.id = str(uuid.uuid4())
    db_field.profile_id = profile_id
    
    session.add(db_field)
    session.commit()
    session.refresh(db_field)
    return db_field


@router.patch("/{profile_id}/fields/{field_id}", response_model=ProfileFieldRead)
async def update_field(
    profile_id: str,
    field_id: str,
    update: ProfileFieldUpdate,
    session: Session = Depends(get_session)
):
    """Update a field."""
    field = session.get(ProfileField, field_id)
    if not field or field.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Field not found")
    
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(field, key, value)
    
    session.add(field)
    session.commit()
    session.refresh(field)
    return field


@router.delete("/{profile_id}/fields/{field_id}")
async def delete_field(
    profile_id: str,
    field_id: str,
    session: Session = Depends(get_session)
):
    """Delete a field."""
    field = session.get(ProfileField, field_id)
    if not field or field.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Field not found")
    
    session.delete(field)
    session.commit()
    return {"message": "Field deleted"}


# Workflow Step Endpoints

@router.get("/{profile_id}/steps", response_model=List[WorkflowStepRead])
async def get_profile_steps(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """Get all workflow steps for a profile."""
    steps = session.exec(
        select(WorkflowStep)
        .where(WorkflowStep.profile_id == profile_id)
        .order_by(WorkflowStep.order_index)
    ).all()
    return steps


@router.post("/{profile_id}/steps", response_model=WorkflowStepRead)
async def add_step(
    profile_id: str,
    step: WorkflowStepCreate,
    session: Session = Depends(get_session)
):
    """Add a new workflow step."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_step = WorkflowStep.model_validate(step)
    db_step.id = str(uuid.uuid4())
    db_step.profile_id = profile_id
    
    session.add(db_step)
    session.commit()
    session.refresh(db_step)
    return db_step


@router.patch("/{profile_id}/steps/{step_id}", response_model=WorkflowStepRead)
async def update_step(
    profile_id: str,
    step_id: str,
    update: WorkflowStepUpdate,
    session: Session = Depends(get_session)
):
    """Update a workflow step."""
    step = session.get(WorkflowStep, step_id)
    if not step or step.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Step not found")
    
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(step, key, value)
    
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.delete("/{profile_id}/steps/{step_id}")
async def delete_step(
    profile_id: str,
    step_id: str,
    session: Session = Depends(get_session)
):
    """Delete a workflow step."""
    step = session.get(WorkflowStep, step_id)
    if not step or step.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Step not found")
    
    session.delete(step)
    session.commit()
    return {"message": "Step deleted"}


@router.post("/{profile_id}/validate", response_model=WorkflowValidation)
async def validate_profile(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """Validate profile for errors."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    errors = []
    warnings = []
    
    # Check for required fields without locators
    fields = session.exec(
        select(ProfileField).where(ProfileField.profile_id == profile_id)
    ).all()
    
    for field in fields:
        if field.required and not field.locator_value:
            errors.append(f"Required field '{field.name}' has no locator")
        
        if field.locator_type == "semantic" and not field.locator_fallback:
            warnings.append(f"Field '{field.name}' uses semantic locator without fallback")
    
    # Check workflow has at least one step
    steps = session.exec(
        select(WorkflowStep).where(WorkflowStep.profile_id == profile_id)
    ).all()
    
    if not steps:
        warnings.append("Profile has no workflow steps")
    
    # Check for duplicate field names
    field_names = [f.name for f in fields]
    if len(field_names) != len(set(field_names)):
        errors.append("Duplicate field names found")
    
    return WorkflowValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
