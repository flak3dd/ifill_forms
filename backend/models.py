from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import JSON, Column
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json

class User(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    profiles: List["Profile"] = Relationship(back_populates="owner")
    jobs: List["Job"] = Relationship(back_populates="owner")

class Profile(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    base_url: str
    version: int = 1
    steps: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # JSON workflow steps
    field_mappings: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # CSV column to field mappings
    success_indicators: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    ai_hints: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign keys
    owner_id: str = Field(foreign_key="user.id")
    owner: User = Relationship(back_populates="profiles")
    
    # Relationships
    jobs: List["Job"] = Relationship(back_populates="profile")
    profile_fields: List["ProfileField"] = Relationship(back_populates="profile")
    workflow_steps: List["WorkflowStep"] = Relationship(back_populates="profile")
    versions: List["ProfileVersion"] = Relationship(back_populates="profile")
    column_mappings: List["ColumnMapping"] = Relationship(back_populates="profile")
    mapping_sessions: List["MappingSession"] = Relationship(back_populates="profile")

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class Job(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    
    # Configuration
    concurrency: int = 1
    delay_between_requests: float = 1.0
    max_retries: int = 3
    use_stealth: bool = True
    proxy_group: Optional[str] = None
    
    # Data source
    data_source: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # File path, URL, etc.
    total_rows: int = 0
    processed_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Results
    output_data: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # Extracted data, confirmations, etc.
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    profile: Profile = Relationship(back_populates="jobs")
    owner_id: str = Field(foreign_key="user.id")
    owner: User = Relationship(back_populates="jobs")
    
    # Relationships
    logs: List["ExecutionLog"] = Relationship(back_populates="job")

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ExecutionLog(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    level: LogLevel = LogLevel.INFO
    message: str
    details: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # Additional context, screenshots, etc.
    
    # Row-specific info
    row_index: Optional[int] = None
    step_name: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign keys
    job_id: str = Field(foreign_key="job.id")
    job: Job = Relationship(back_populates="logs")

class Settlement(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    from_user: str
    to_user: str
    amount: float
    date: datetime
    group_id: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Enhanced Profile Management Models

class ProfileStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class FieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    TEL = "tel"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    FILE = "file"
    HIDDEN = "hidden"


class LocatorType(str, Enum):
    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    CSS = "css"
    XPATH = "xpath"
    TEST_ID = "test_id"
    SEMANTIC = "semantic"


class StepType(str, Enum):
    NAVIGATE = "navigate"
    FILL = "fill"
    CLICK = "click"
    WAIT = "wait"
    ASSERT = "assert"
    EXTRACT = "extract"
    UPLOAD = "upload"
    CONDITIONAL = "conditional"


class MappingConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL = "manual"


# Enhanced Field Model
class ProfileField(SQLModel, table=True):
    """Individual form field within a profile."""
    __tablename__ = "profile_fields"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    # Identification
    name: str  # Internal identifier
    label: Optional[str] = None  # Display label from page
    field_type: str = Field(default="text")  # FieldType value
    semantic_tag: str = Field(default="custom")  # For CSV mapping
    required: bool = Field(default=False)
    
    # Locator strategy (layered)
    locator_type: str = Field(default="css")  # LocatorType value
    locator_value: str
    locator_fallback: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)
    
    # Validation rules
    validation_regex: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    
    # Options for select/checkbox/radio
    options: Optional[List[Dict[str, str]]] = Field(default=None, sa_type=JSON)
    
    # Metadata
    is_visible: bool = Field(default=True)
    is_in_iframe: bool = Field(default=False)
    iframe_selector: Optional[str] = None
    order_index: int = Field(default=0)
    
    # AI detection metadata
    detection_confidence: float = Field(default=0.0)
    ai_reasoning: Optional[str] = None
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    workflow_step_id: Optional[str] = Field(default=None, foreign_key="workflow_step.id")
    
    # Relationships
    profile: "Profile" = Relationship(back_populates="profile_fields")
    workflow_step: Optional["WorkflowStep"] = Relationship(back_populates="fields")


# Workflow Step Model
class WorkflowStep(SQLModel, table=True):
    """Individual step in a profile workflow."""
    __tablename__ = "workflow_step"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    step_type: str  # StepType value
    name: str
    description: Optional[str] = None
    order_index: int
    
    # Step-specific configuration
    config: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    
    # Conditional execution
    condition: Optional[str] = None  # Jinja2 expression
    
    # Error handling
    retry_count: int = Field(default=3)
    retry_delay_ms: int = Field(default=1000)
    on_error: str = Field(default="fail")  # fail, skip, manual
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    parent_step_id: Optional[str] = Field(default=None, foreign_key="workflow_step.id")
    
    # Relationships
    profile: "Profile" = Relationship(back_populates="workflow_steps")
    fields: List["ProfileField"] = Relationship(back_populates="workflow_step")
    child_steps: List["WorkflowStep"] = Relationship(
        back_populates="parent_step",
        sa_relationship_kwargs={
            "remote_side": "WorkflowStep.id",
            "foreign_keys": "WorkflowStep.parent_step_id"
        }
    )
    parent_step: Optional["WorkflowStep"] = Relationship(
        back_populates="child_steps",
        sa_relationship_kwargs={"foreign_keys": "WorkflowStep.parent_step_id"}
    )


# Profile Version Model
class ProfileVersion(SQLModel, table=True):
    """Version history for profiles."""
    __tablename__ = "profile_versions"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    version_number: int
    snapshot: Dict[str, Any] = Field(sa_type=JSON)  # Full profile JSON snapshot
    change_summary: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, foreign_key="user.id")
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    
    # Relationships
    profile: "Profile" = Relationship(back_populates="versions")


# Column Mapping Model
class ColumnMapping(SQLModel, table=True):
    """Mapping between CSV columns and profile fields."""
    __tablename__ = "column_mappings"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    # CSV column info
    csv_column_name: str
    csv_sample_values: Optional[List[str]] = Field(default=None, sa_type=JSON)
    
    # Target field mapping
    field_id: Optional[str] = Field(default=None, foreign_key="profile_fields.id")
    semantic_tag: Optional[str] = None
    
    # Transformation
    transform_template: Optional[str] = None  # Jinja2 template
    transform_function: Optional[str] = None  # Built-in function name
    
    # AI-generated mapping info
    confidence: str = Field(default="manual")  # MappingConfidence value
    ai_reasoning: Optional[str] = None
    
    # User override tracking
    is_user_override: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    mapping_session_id: Optional[str] = Field(default=None, foreign_key="mapping_session.id")
    
    # Relationships
    profile: "Profile" = Relationship(back_populates="column_mappings")
    mapping_session: Optional["MappingSession"] = Relationship(back_populates="mappings")


# Mapping Session Model
class MappingSession(SQLModel, table=True):
    """Session for CSV-to-profile mapping process."""
    __tablename__ = "mapping_session"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    csv_headers: List[str] = Field(sa_type=JSON)
    csv_sample_rows: List[Dict[str, Any]] = Field(sa_type=JSON)
    
    is_complete: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign keys
    profile_id: str = Field(foreign_key="profile.id")
    
    # Relationships
    profile: "Profile" = Relationship(back_populates="mapping_sessions")
    mappings: List["ColumnMapping"] = Relationship(back_populates="mapping_session")


# Login Automation Workflow Models

class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AutomationWorkflow(SQLModel, table=True):
    """A login automation workflow: URL scan + credentials + execution."""
    __tablename__ = "automation_workflow"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    
    name: str
    target_url: str
    description: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.DRAFT
    
    # Detected login form selectors
    detected_fields: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    # Example: {
    #   "username_selector": "input#email",
    #   "password_selector": "input#password",
    #   "submit_selector": "button[type=submit]",
    #   "username_label": "Email",
    #   "password_label": "Password",
    #   "submit_label": "Sign In",
    #   "form_action": "/login",
    #   "extra_fields": [...],
    #   "page_title": "Login Page"
    # }
    
    # User-edited selectors (overrides detected)
    custom_selectors: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    
    # Credentials file info
    credentials_file: Optional[str] = None  # Path to uploaded file
    credential_count: int = 0
    
    # Execution settings
    delay_between_logins: float = 2.0  # seconds
    use_stealth: bool = True
    max_retries: int = 1
    
    # Success detection
    success_indicators: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    # Example: {"url_change": true, "selector": ".dashboard", "text_contains": "Welcome"}
    
    # Results
    total_credentials: int = 0
    processed_count: int = 0
    successful_count: int = 0
    failed_count: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    # Each result: {"username": "...", "status": "success"|"failed", "message": "...", "timestamp": "..."}
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Create tables
def create_db_and_tables():
    from .database import engine
    SQLModel.metadata.create_all(engine)
