from typing import Optional, Any
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from uuid import uuid4


def gen_id() -> str:
    return str(uuid4())


class Organization(BaseModel):
    id: str = Field(default_factory=gen_id)
    name: str
    slug: Optional[str] = None
    status: str = "active"
    settings_json: dict = Field(default_factory=dict)
    logo_file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(BaseModel):
    id: str = Field(default_factory=gen_id)
    email: EmailStr
    password_hash: str
    full_name: Optional[str] = None
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrganizationMembership(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    user_id: str
    role: str  # admin, reviewer, viewer
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserPreferences(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    org_id: str
    prefs_json: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    user_id: Optional[str] = None
    type: str
    title: str
    message: str
    data_json: Optional[dict] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmailEvent(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    to_email: EmailStr
    subject: str
    template_name: Optional[str] = None
    payload_json: Optional[dict] = None
    status: str = "queued"  # queued, sent, failed
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None


class RetentionPolicy(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    entity_type: str
    retention_days: int
    delete_mode: str  # soft or hard
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamMember(BaseModel):
    id: str = Field(default_factory=gen_id)
    organization_id: str
    full_name: str
    email: EmailStr
    role: str  # Admin | Reviewer | Viewer
    status: str = "active"  # active | disabled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationPreferences(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    upload_completed: bool = True
    review_required: bool = True
    export_ready: bool = True
    exceptions_detected: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(BaseModel):
    id: str = Field(default_factory=gen_id)
    organization_id: str
    user_id: str
    user_name: str
    action: str
    category: str  # Upload | Review | Export | Exception | Template
    file_name: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TemplateConfig(BaseModel):
    id: str = Field(default_factory=gen_id)
    organization_id: str
    template_name: str
    fields: dict = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
