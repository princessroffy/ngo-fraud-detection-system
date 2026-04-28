from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "Pending Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    NEEDS_INVESTIGATION = "Needs Investigation"
    RESOLVED = "Resolved"


class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    REVIEWER = "Reviewer"
    VIEWER = "Viewer"


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    review_rate: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)

    records: Mapped[list["BeneficiaryRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class BeneficiaryRecord(Base):
    __tablename__ = "beneficiary_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    batch_id: Mapped[str] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    beneficiary_id: Mapped[str] = mapped_column(String(120), default="")
    full_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    gender: Mapped[str] = mapped_column(String(80), default="")
    age: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    community: Mapped[str] = mapped_column(String(255), default="")
    program_applied: Mapped[str] = mapped_column(String(255), default="")
    date_registered: Mapped[str] = mapped_column(String(80), default="")
    support_received: Mapped[str] = mapped_column(String(255), default="")
    fraud_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(30), default="Low", index=True)
    fraud_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    score_breakdown: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_explanation: Mapped[str] = mapped_column(Text, default="")
    similar_name_matches: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(
        String(40),
        default=ReviewStatus.PENDING_REVIEW.value,
        index=True,
    )
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str] = mapped_column(String(255), default="")
    date_reviewed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="records")


class FraudWeight(Base):
    __tablename__ = "fraud_weights"

    rule_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    previous_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
