from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, UserRole
from app.schemas import AuditLogOut, CurrentUser
from app.security import require_roles


router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN)),
) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
