from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BeneficiaryRecord, UserRole
from app.privacy import record_to_out
from app.schemas import BeneficiaryRecordOut, CurrentUser, ReviewUpdate
from app.security import require_roles
from app.services.audit import write_audit


router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("", response_model=list[BeneficiaryRecordOut])
def list_records(
    batch_id: str | None = None,
    risk_level: str | None = None,
    review_status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER, UserRole.VIEWER)),
) -> list[BeneficiaryRecordOut]:
    query = db.query(BeneficiaryRecord)
    if batch_id:
        query = query.filter(BeneficiaryRecord.batch_id == batch_id)
    if risk_level:
        query = query.filter(BeneficiaryRecord.risk_level == risk_level)
    if review_status:
        query = query.filter(BeneficiaryRecord.review_status == review_status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                BeneficiaryRecord.beneficiary_id.ilike(pattern),
                BeneficiaryRecord.full_name.ilike(pattern),
                BeneficiaryRecord.phone.ilike(pattern),
                BeneficiaryRecord.email.ilike(pattern),
                BeneficiaryRecord.address.ilike(pattern),
                BeneficiaryRecord.community.ilike(pattern),
                BeneficiaryRecord.program_applied.ilike(pattern),
            )
        )

    records = (
        query.order_by(BeneficiaryRecord.fraud_score.desc(), BeneficiaryRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [record_to_out(record, user) for record in records]


@router.patch("/{record_id}/review", response_model=BeneficiaryRecordOut)
def update_review(
    record_id: str,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> BeneficiaryRecordOut:
    record = db.query(BeneficiaryRecord).filter(BeneficiaryRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    previous_value = {
        "review_status": record.review_status,
        "reviewer_notes": record.reviewer_notes,
        "reviewed_by": record.reviewed_by,
    }
    record.review_status = payload.review_status.value
    record.reviewer_notes = payload.reviewer_notes
    record.reviewed_by = user.email
    record.date_reviewed = datetime.now(timezone.utc)

    write_audit(
        db,
        user,
        action="record_reviewed",
        record_id=record.id,
        batch_id=record.batch_id,
        previous_value=previous_value,
        new_value={
            "review_status": record.review_status,
            "reviewer_notes": record.reviewer_notes,
            "reviewed_by": record.reviewed_by,
        },
    )
    db.commit()
    db.refresh(record)
    return record_to_out(record, user)
