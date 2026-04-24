from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .models import JobStatus, LogLevel, WorkflowStatus

# Profile schemas
class ProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    base_url: str
    steps: Dict[str, Any] = Field(default_factory=dict)
    field_mappings: Dict[str, Any] = Field(default_factory=dict)
    success_indicators: Dict[str, Any] = Field(default_factory=dict)
    ai_hints: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    steps: Optional[Dict[str, Any]] = None
    field_mappings: Optional[Dict[str, Any]] = None
    success_indicators: Optional[Dict[str, Any]] = None
    ai_hints: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ProfileRead(ProfileBase):
    id: str
    version: int
    created_at: datetime
    updated_at: datetime
    owner_id: str

# Job schemas
class JobBase(BaseModel):
    name: str
    description: Optional[str] = None
    concurrency: int = 1
    delay_between_requests: float = 1.0
    max_retries: int = 3
    use_stealth: bool = True
    proxy_group: Optional[str] = None
    data_source: Dict[str, Any] = Field(default_factory=dict)

class JobCreate(JobBase):
    profile_id: str

class JobUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[JobStatus] = None
    concurrency: Optional[int] = None
    delay_between_requests: Optional[float] = None
    max_retries: Optional[int] = None
    use_stealth: Optional[bool] = None
    proxy_group: Optional[str] = None

class JobRead(JobBase):
    id: str
    status: JobStatus
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_completion: Optional[datetime]
    output_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    profile_id: str
    owner_id: str

# Log schemas
class ExecutionLogBase(BaseModel):
    level: LogLevel = LogLevel.INFO
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    row_index: Optional[int] = None
    step_name: Optional[str] = None

class ExecutionLogRead(ExecutionLogBase):
    id: str
    timestamp: datetime
    job_id: str

# Analysis schemas
class FieldInfo(BaseModel):
    semantic_tag: str
    label: str
    field_type: str
    locator: Dict[str, Any]
    required: bool = False
    validation: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = None  # For select/checkbox

class SiteAnalysis(BaseModel):
    url: str
    title: str
    forms: List[FieldInfo]
    multi_step: bool = False
    estimated_success_rate: float = 0.8
    confidence: float = 0.9

class FieldMapping(BaseModel):
    csv_column: str
    field_semantic: str
    confidence: float
    transformation: Optional[str] = None  # e.g., "title_case", "phone_format"

class MappingSuggestion(BaseModel):
    mappings: List[FieldMapping]
    unmapped_columns: List[str]
    unmapped_fields: List[str]
    overall_confidence: float

# File analysis schemas
class ColumnInfo(BaseModel):
    name: str
    type: str
    sample_values: List[str]
    null_count: int
    unique_count: int

class FileAnalysis(BaseModel):
    filename: str
    total_rows: int
    total_columns: int
    columns: List[ColumnInfo]
    sample_data: List[Dict[str, Any]]
    validation_errors: List[str] = Field(default_factory=list)

# Test result schemas
class TestResult(BaseModel):
    success: bool
    steps_completed: List[str]
    errors: List[str] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float

# Job status update schemas
class JobStatusUpdate(BaseModel):
    job_id: str
    status: JobStatus
    processed_rows: int
    successful_rows: int
    failed_rows: int
    current_row: Optional[int] = None
    current_step: Optional[str] = None
    message: Optional[str] = None


# Enhanced Profile Management Schemas

class ProfileFieldBase(BaseModel):
    name: str
    label: Optional[str] = None
    field_type: str = "text"
    semantic_tag: str = "custom"
    required: bool = False
    locator_type: str = "css"
    locator_value: str
    locator_fallback: Optional[Dict[str, Any]] = None
    validation_regex: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    options: Optional[List[Dict[str, str]]] = None
    is_visible: bool = True
    is_in_iframe: bool = False
    iframe_selector: Optional[str] = None
    order_index: int = 0
    detection_confidence: float = 0.0
    ai_reasoning: Optional[str] = None


class ProfileFieldCreate(ProfileFieldBase):
    profile_id: str
    workflow_step_id: Optional[str] = None


class ProfileFieldRead(ProfileFieldBase):
    id: str
    profile_id: str
    workflow_step_id: Optional[str] = None


class ProfileFieldUpdate(BaseModel):
    label: Optional[str] = None
    semantic_tag: Optional[str] = None
    required: Optional[bool] = None
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    validation_regex: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None
    order_index: Optional[int] = None


class WorkflowStepBase(BaseModel):
    step_type: str
    name: str
    description: Optional[str] = None
    order_index: int
    config: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None
    retry_count: int = 3
    retry_delay_ms: int = 1000
    on_error: str = "fail"


class WorkflowStepCreate(WorkflowStepBase):
    profile_id: str
    parent_step_id: Optional[str] = None
    fields: Optional[List[ProfileFieldCreate]] = None


class WorkflowStepRead(WorkflowStepBase):
    id: str
    profile_id: str
    parent_step_id: Optional[str] = None
    fields: List[ProfileFieldRead] = Field(default_factory=list)
    child_steps: List["WorkflowStepRead"] = Field(default_factory=list)


class WorkflowStepUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    condition: Optional[str] = None
    retry_count: Optional[int] = None
    on_error: Optional[str] = None


class WorkflowValidation(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProfileVersionRead(BaseModel):
    id: str
    version_number: int
    change_summary: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


class ProfileVersionDetail(BaseModel):
    id: str
    version_number: int
    snapshot: Dict[str, Any]
    change_summary: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


class ColumnMappingBase(BaseModel):
    csv_column_name: str
    csv_sample_values: Optional[List[str]] = None
    field_id: Optional[str] = None
    semantic_tag: Optional[str] = None
    transform_template: Optional[str] = None
    transform_function: Optional[str] = None
    confidence: str = "manual"
    ai_reasoning: Optional[str] = None
    is_user_override: bool = False


class ColumnMappingCreate(ColumnMappingBase):
    profile_id: str
    mapping_session_id: Optional[str] = None


class ColumnMappingRead(ColumnMappingBase):
    id: str
    profile_id: str
    mapping_session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ColumnMappingUpdate(BaseModel):
    field_id: Optional[str] = None
    semantic_tag: Optional[str] = None
    transform_template: Optional[str] = None
    transform_function: Optional[str] = None
    is_user_override: Optional[bool] = None


class MappingSessionRead(BaseModel):
    id: str
    profile_id: str
    csv_headers: List[str]
    csv_sample_rows: List[Dict[str, Any]]
    is_complete: bool
    created_at: datetime


class MappingSessionDetail(BaseModel):
    id: str
    profile_id: str
    csv_headers: List[str]
    csv_sample_rows: List[Dict[str, Any]]
    is_complete: bool
    mappings: List[ColumnMappingRead]
    created_at: datetime


class AutoMapRequest(BaseModel):
    profile_id: str
    csv_headers: List[str]
    csv_sample_rows: List[Dict[str, Any]]
    use_ai: bool = True


class MappingSuggestion(BaseModel):
    csv_column: str
    semantic_tag: Optional[str] = None
    field_id: Optional[str] = None
    confidence: str
    reasoning: Optional[str] = None
    transform_suggestion: Optional[str] = None


class AutoMapResponse(BaseModel):
    session_id: str
    suggestions: List[MappingSuggestion]
    unmapped_columns: List[str]
    unmapped_fields: List[str]
    overall_confidence: float


class ConfirmMappingRequest(BaseModel):
    session_id: str
    mappings: List[ColumnMappingCreate]
    save_as_default: bool = True


class ProfileForkRequest(BaseModel):
    new_name: str
    description: Optional[str] = None


class ProfileForkResponse(BaseModel):
    original_id: str
    new_id: str
    new_name: str


class EnhancedProfileRead(ProfileRead):
    field_count: int = 0
    step_count: int = 0
    latest_version: int = 1
    has_default_mapping: bool = False


# Detection schemas
class DetectFieldsRequest(BaseModel):
    url: str
    wait_for_selector: Optional[str] = None
    use_ai: bool = True


class DetectFieldsResponse(BaseModel):
    url: str
    detected_fields: List[ProfileFieldRead]
    detected_steps: List[WorkflowStepRead]
    confidence_score: float
    preview_screenshot_url: Optional[str] = None


class CreateProfileFromDetection(BaseModel):
    name: str
    description: Optional[str] = None
    detected_fields: List[ProfileFieldCreate]
    detected_steps: List[WorkflowStepCreate]
    success_indicators: Optional[Dict[str, Any]] = None


# ===== Automation Workflow Schemas =====

class ScanUrlRequest(BaseModel):
    url: str
    name: Optional[str] = None

class ScanUrlResponse(BaseModel):
    workflow_id: str
    name: str
    target_url: str
    page_title: Optional[str] = None
    detected_fields: Dict[str, Any]
    confidence: float
    screenshot_url: Optional[str] = None

class WorkflowRead(BaseModel):
    id: str
    name: str
    target_url: str
    description: Optional[str] = None
    status: WorkflowStatus
    detected_fields: Dict[str, Any]
    custom_selectors: Dict[str, Any]
    credentials_file: Optional[str] = None
    credential_count: int
    delay_between_logins: float
    use_stealth: bool
    max_retries: int
    success_indicators: Dict[str, Any]
    total_credentials: int
    processed_count: int
    successful_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    custom_selectors: Optional[Dict[str, Any]] = None
    delay_between_logins: Optional[float] = None
    use_stealth: Optional[bool] = None
    max_retries: Optional[int] = None
    success_indicators: Optional[Dict[str, Any]] = None

class CredentialPasteRequest(BaseModel):
    text: str
    format: Optional[str] = None  # "txt" or "csv"; auto-detected if omitted

class CredentialUploadResponse(BaseModel):
    workflow_id: str
    credential_count: int
    sample_usernames: List[str]
    status: WorkflowStatus

class WorkflowRunResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    message: str
    total_credentials: int
