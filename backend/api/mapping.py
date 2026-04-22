"""
Field Mapping API Endpoints
Handles CSV-to-profile field mapping with AI assistance
"""
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime

from ..database import get_session
from ..models import (
    Profile, ProfileField, ColumnMapping, MappingSession
)
from ..schemas import (
    AutoMapRequest, AutoMapResponse, MappingSuggestion,
    ConfirmMappingRequest, ColumnMappingRead, MappingSessionRead, MappingSessionDetail
)
from ..services.ai_client import get_ai_client

router = APIRouter(prefix="/api/mapping", tags=["mapping"])


def _find_semantic_matches(csv_columns: List[str], profile_fields: List[ProfileField]) -> List[MappingSuggestion]:
    """Find semantic matches between CSV columns and profile fields."""
    suggestions = []
    
    # Semantic to column keyword mappings
    semantic_keywords = {
        "given_name": ["first", "fname", "first_name", "given"],
        "family_name": ["last", "lname", "last_name", "surname", "family"],
        "full_name": ["name", "full_name", "full"],
        "email": ["email", "e_mail", "mail", "email_address"],
        "phone": ["phone", "telephone", "mobile", "tel", "cell"],
        "address": ["address", "street", "addr"],
        "city": ["city", "town"],
        "state": ["state", "province", "st"],
        "postal_code": ["zip", "postal", "postcode", "zipcode"],
        "country": ["country", "nation"],
        "job_title": ["title", "position", "role", "job"],
        "company": ["company", "employer", "organization", "org"],
        "experience": ["experience", "years", "exp"],
        "education": ["education", "degree", "school"],
        "skills": ["skills", "qualifications", "skill"],
        "salary": ["salary", "pay", "compensation", "wage"],
        "cover_letter": ["cover", "letter", "message", "coverletter"],
        "resume": ["resume", "cv"],
        "availability": ["availability", "start_date", "available"]
    }
    
    matched_columns = set()
    
    for field in profile_fields:
        best_match = None
        best_score = 0
        
        keywords = semantic_keywords.get(field.semantic_tag, [field.semantic_tag])
        keywords.extend([k.lower() for k in field.label.split() if field.label])
        
        for column in csv_columns:
            if column in matched_columns:
                continue
                
            col_lower = column.lower().replace("_", " ").replace("-", " ")
            score = 0
            
            for keyword in keywords:
                keyword = keyword.lower()
                if keyword == col_lower:
                    score += 100  # Exact match
                elif keyword in col_lower:
                    score += 50  # Partial match
                elif col_lower in keyword:
                    score += 25  # Reverse match
            
            if score > best_score:
                best_score = score
                best_match = column
        
        if best_match and best_score >= 30:
            confidence = "high" if best_score >= 70 else "medium" if best_score >= 40 else "low"
            
            suggestions.append(MappingSuggestion(
                csv_column=best_match,
                semantic_tag=field.semantic_tag,
                field_id=field.id,
                confidence=confidence,
                reasoning=f"Matched based on column name similarity (score: {best_score})"
            ))
            matched_columns.add(best_match)
    
    return suggestions


def _suggest_transformation(semantic_tag: str, sample_values: List[str]) -> Optional[str]:
    """Suggest data transformation based on semantic tag and sample values."""
    if not sample_values:
        return None
    
    # Check for transformation needs
    if semantic_tag == "email":
        return "email_clean"
    
    elif semantic_tag == "phone":
        return "phone_format"
    
    elif semantic_tag in ["given_name", "family_name", "city", "state", "job_title", "company"]:
        # Check if values need title case
        needs_title = any(
            val.isupper() or (val.islower() and len(val) > 2)
            for val in sample_values if val and isinstance(val, str)
        )
        if needs_title:
            return "title_case"
    
    return None


@router.post("/auto", response_model=AutoMapResponse)
async def auto_map_fields(
    request: AutoMapRequest,
    session: Session = Depends(get_session)
):
    """
    AI-assisted column-to-field mapping.
    Returns proposed mappings with confidence scores.
    """
    # Get profile fields
    profile = session.get(Profile, request.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    fields = session.exec(
        select(ProfileField).where(ProfileField.profile_id == request.profile_id)
    ).all()
    
    if not fields:
        raise HTTPException(status_code=400, detail="Profile has no fields to map")
    
    # Create mapping session
    mapping_session = MappingSession(
        id=str(uuid.uuid4()),
        profile_id=request.profile_id,
        csv_headers=request.csv_headers,
        csv_sample_rows=request.csv_sample_rows,
        is_complete=False
    )
    session.add(mapping_session)
    session.commit()
    
    # Find semantic matches
    suggestions = _find_semantic_matches(request.csv_headers, fields)
    
    # Use AI for additional suggestions if enabled
    if request.use_ai:
        try:
            ai_client = get_ai_client()
            ai_result = await ai_client.suggest_mappings(
                csv_columns=request.csv_headers,
                csv_samples=request.csv_sample_rows,
                profile_fields=[
                    {
                        "semantic_tag": f.semantic_tag,
                        "label": f.label,
                        "field_type": f.field_type
                    }
                    for f in fields
                ]
            )
            
            # Merge AI suggestions
            existing_columns = {s.csv_column for s in suggestions}
            for ai_mapping in ai_result.get("mappings", []):
                col = ai_mapping.get("csv_column")
                if col and col not in existing_columns:
                    # Find matching field
                    semantic = ai_mapping.get("semantic_tag")
                    field = next((f for f in fields if f.semantic_tag == semantic), None)
                    
                    suggestions.append(MappingSuggestion(
                        csv_column=col,
                        semantic_tag=semantic,
                        field_id=field.id if field else None,
                        confidence=ai_mapping.get("confidence", "medium").lower(),
                        reasoning=ai_mapping.get("reasoning", "AI-suggested mapping")
                    ))
        except Exception as e:
            # Continue with semantic matches if AI fails
            print(f"AI mapping failed: {e}")
    
    # Add transformations
    for suggestion in suggestions:
        sample_values = [
            row.get(suggestion.csv_column, "")
            for row in request.csv_sample_rows[:3]
        ]
        transform = _suggest_transformation(suggestion.semantic_tag, sample_values)
        suggestion.transform_suggestion = transform
    
    # Calculate unmapped items
    mapped_columns = {s.csv_column for s in suggestions}
    unmapped_columns = [c for c in request.csv_headers if c not in mapped_columns]
    
    mapped_fields = {s.semantic_tag for s in suggestions if s.semantic_tag}
    unmapped_fields = [f.semantic_tag for f in fields if f.semantic_tag not in mapped_fields]
    
    # Calculate overall confidence
    confidence_scores = {"high": 0.9, "medium": 0.7, "low": 0.5, "manual": 1.0}
    overall_confidence = sum(
        confidence_scores.get(s.confidence, 0.5) for s in suggestions
    ) / len(suggestions) if suggestions else 0.0
    
    return AutoMapResponse(
        session_id=mapping_session.id,
        suggestions=suggestions,
        unmapped_columns=unmapped_columns,
        unmapped_fields=unmapped_fields,
        overall_confidence=overall_confidence
    )


@router.post("/confirm", response_model=List[ColumnMappingRead])
async def confirm_mapping(
    request: ConfirmMappingRequest,
    session: Session = Depends(get_session)
):
    """Save confirmed mappings for a profile."""
    mapping_session = session.get(MappingSession, request.session_id)
    if not mapping_session:
        raise HTTPException(status_code=404, detail="Mapping session not found")
    
    profile = session.get(Profile, mapping_session.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    saved_mappings = []
    
    # Clear existing mappings if saving as default
    if request.save_as_default:
        existing = session.exec(
            select(ColumnMapping).where(
                ColumnMapping.profile_id == mapping_session.profile_id,
                ColumnMapping.mapping_session_id.is_(None)  # Default mappings have no session
            )
        ).all()
        for m in existing:
            session.delete(m)
    
    # Save new mappings
    for mapping_data in request.mappings:
        column_mapping = ColumnMapping(
            id=str(uuid.uuid4()),
            profile_id=mapping_session.profile_id,
            mapping_session_id=request.session_id if not request.save_as_default else None,
            csv_column_name=mapping_data.csv_column_name,
            csv_sample_values=mapping_data.csv_sample_values,
            field_id=mapping_data.field_id,
            semantic_tag=mapping_data.semantic_tag,
            transform_template=mapping_data.transform_template,
            transform_function=mapping_data.transform_function,
            confidence=mapping_data.confidence,
            ai_reasoning=mapping_data.ai_reasoning,
            is_user_override=mapping_data.is_user_override
        )
        session.add(column_mapping)
        saved_mappings.append(column_mapping)
    
    # Update session status
    mapping_session.is_complete = True
    session.add(mapping_session)
    
    # Update profile field_mappings (for backward compatibility)
    if request.save_as_default:
        profile_mappings = {}
        for m in saved_mappings:
            profile_mappings[m.csv_column_name] = {
                "semantic": m.semantic_tag,
                "field_id": m.field_id,
                "transformation": m.transform_function
            }
        profile.field_mappings = profile_mappings
        session.add(profile)
    
    session.commit()
    
    for m in saved_mappings:
        session.refresh(m)
    
    return saved_mappings


@router.get("/profile/{profile_id}/default", response_model=List[ColumnMappingRead])
async def get_default_mapping(
    profile_id: str,
    session: Session = Depends(get_session)
):
    """Get the default saved mapping for a profile."""
    mappings = session.exec(
        select(ColumnMapping)
        .where(ColumnMapping.profile_id == profile_id)
        .where(ColumnMapping.mapping_session_id.is_(None))
    ).all()
    
    return mappings


@router.get("/sessions/{session_id}", response_model=MappingSessionDetail)
async def get_mapping_session(
    session_id: str,
    session: Session = Depends(get_session)
):
    """Get mapping session details with mappings."""
    mapping_session = session.get(MappingSession, session_id)
    if not mapping_session:
        raise HTTPException(status_code=404, detail="Mapping session not found")
    
    mappings = session.exec(
        select(ColumnMapping).where(ColumnMapping.mapping_session_id == session_id)
    ).all()
    
    return MappingSessionDetail(
        id=mapping_session.id,
        profile_id=mapping_session.profile_id,
        csv_headers=mapping_session.csv_headers,
        csv_sample_rows=mapping_session.csv_sample_rows,
        is_complete=mapping_session.is_complete,
        mappings=[
            ColumnMappingRead(
                id=m.id,
                csv_column_name=m.csv_column_name,
                csv_sample_values=m.csv_sample_values,
                field_id=m.field_id,
                semantic_tag=m.semantic_tag,
                transform_template=m.transform_template,
                transform_function=m.transform_function,
                confidence=m.confidence,
                ai_reasoning=m.ai_reasoning,
                is_user_override=m.is_user_override,
                profile_id=m.profile_id,
                mapping_session_id=m.mapping_session_id,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
            for m in mappings
        ],
        created_at=mapping_session.created_at
    )


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(
    mapping_id: str,
    session: Session = Depends(get_session)
):
    """Delete a column mapping."""
    mapping = session.get(ColumnMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Mapping deleted"}


@router.patch("/mappings/{mapping_id}", response_model=ColumnMappingRead)
async def update_mapping(
    mapping_id: str,
    field_id: Optional[str] = None,
    semantic_tag: Optional[str] = None,
    transform_function: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Update a column mapping."""
    mapping = session.get(ColumnMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    if field_id is not None:
        mapping.field_id = field_id
    if semantic_tag is not None:
        mapping.semantic_tag = semantic_tag
    if transform_function is not None:
        mapping.transform_function = transform_function
    
    mapping.is_user_override = True
    mapping.updated_at = datetime.utcnow()
    
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping
