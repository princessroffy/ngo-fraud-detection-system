from sqlalchemy.orm import Session

from app.models import AuditLog
from app.schemas import CurrentUser


def write_audit(
    db: Session,
    user: CurrentUser,
    action: str,
    record_id: str | None = None,
    batch_id: str | None = None,
    previous_value: dict | None = None,
    new_value: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role.value,
        action=action,
        record_id=record_id,
        batch_id=batch_id,
        previous_value=previous_value,
        new_value=new_value,
    )
    db.add(log)
    return log
