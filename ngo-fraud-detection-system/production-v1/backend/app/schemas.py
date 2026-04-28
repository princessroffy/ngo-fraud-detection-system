from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ReviewStatus, UserRole


class CurrentUser(BaseModel):
    id: str
    email: str
    role: UserRole


class UploadBatchOut(BaseModel):
    id: str
    file_name: str
    upload_date: datetime
    total_records: int
    high_risk_count: int
    review_rate: int
    uploaded_by: str

    model_config = ConfigDict(from_attributes=True)


class BeneficiaryRecordOut(BaseModel):
    id: str
    batch_id: str
    beneficiary_id: str
    full_name: str
    phone: str
    email: str
    gender: str
    age: str
    address: str
    community: str
    program_applied: str
    date_registered: str
    support_received: str
    fraud_score: int
    risk_level: str
    fraud_flags: list[str] = Field(default_factory=list)
    score_breakdown: list[str] = Field(default_factory=list)
    risk_explanation: str
    similar_name_matches: str
    review_status: ReviewStatus
    reviewer_notes: str
    reviewed_by: str
    date_reviewed: datetime | None
    created_at: datetime


class ReviewUpdate(BaseModel):
    review_status: ReviewStatus
    reviewer_notes: str = ""


class FraudWeightOut(BaseModel):
    rule_key: str
    label: str
    score: int
    updated_by: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FraudWeightUpdate(BaseModel):
    score: int = Field(ge=0, le=100)


class AuditLogOut(BaseModel):
    id: str
    actor_id: str
    actor_email: str
    actor_role: str
    action: str
    record_id: str | None
    batch_id: str | None
    previous_value: dict | None
    new_value: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
