import re

from app.models import BeneficiaryRecord, UserRole
from app.schemas import BeneficiaryRecordOut, CurrentUser


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) <= 4:
        return "***"
    return f"{digits[:4]}{'*' * max(len(digits) - 6, 3)}{digits[-2:]}"


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    first = local[:1] or "*"
    return f"{first}***@{domain}"


def record_to_out(record: BeneficiaryRecord, user: CurrentUser) -> BeneficiaryRecordOut:
    should_mask = user.role == UserRole.VIEWER
    return BeneficiaryRecordOut(
        id=record.id,
        batch_id=record.batch_id,
        beneficiary_id=record.beneficiary_id,
        full_name=record.full_name,
        phone=mask_phone(record.phone) if should_mask else record.phone,
        email=mask_email(record.email) if should_mask else record.email,
        gender=record.gender,
        age=record.age,
        address="Restricted" if should_mask else record.address,
        community=record.community,
        program_applied=record.program_applied,
        date_registered=record.date_registered,
        support_received=record.support_received,
        fraud_score=record.fraud_score,
        risk_level=record.risk_level,
        fraud_flags=record.fraud_flags or [],
        score_breakdown=record.score_breakdown or [],
        risk_explanation=record.risk_explanation,
        similar_name_matches=record.similar_name_matches,
        review_status=record.review_status,
        reviewer_notes=record.reviewer_notes,
        reviewed_by=record.reviewed_by,
        date_reviewed=record.date_reviewed,
        created_at=record.created_at,
    )
