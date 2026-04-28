from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FraudWeight, UserRole
from app.schemas import CurrentUser, FraudWeightOut, FraudWeightUpdate
from app.security import require_roles
from app.services.audit import write_audit
from app.services.weights import seed_default_weights


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/fraud-weights", response_model=list[FraudWeightOut])
def list_fraud_weights(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN)),
) -> list[FraudWeight]:
    seed_default_weights(db)
    return db.query(FraudWeight).order_by(FraudWeight.rule_key).all()


@router.patch("/fraud-weights/{rule_key}", response_model=FraudWeightOut)
def update_fraud_weight(
    rule_key: str,
    payload: FraudWeightUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN)),
) -> FraudWeight:
    seed_default_weights(db)
    weight = db.query(FraudWeight).filter(FraudWeight.rule_key == rule_key).first()
    if not weight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud weight not found")

    previous_value = {"score": weight.score}
    weight.score = payload.score
    weight.updated_by = user.email
    write_audit(
        db,
        user,
        action="fraud_weight_updated",
        previous_value=previous_value,
        new_value={"rule_key": rule_key, "score": weight.score},
    )
    db.commit()
    db.refresh(weight)
    return weight
