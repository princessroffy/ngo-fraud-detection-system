from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BeneficiaryRecord, UploadBatch, UserRole
from app.schemas import CurrentUser, UploadBatchOut
from app.security import require_roles
from app.services.audit import write_audit
from app.services.detection import REQUIRED_COLUMNS, analyze_records
from app.services.weights import get_weight_config


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadBatchOut, status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> UploadBatch:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported")

    contents = await file.read()
    try:
        raw_df = pd.read_csv(BytesIO(contents), dtype=str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSV file") from exc

    weights = get_weight_config(db)
    analyzed = analyze_records(raw_df, weights)
    total_records = len(analyzed)
    high_risk_count = int((analyzed["risk_level"] == "High").sum())
    review_count = int(analyzed["risk_level"].isin(["Medium", "High"]).sum())
    review_rate = int(round((review_count / total_records) * 100)) if total_records else 0

    batch = UploadBatch(
        file_name=file.filename,
        total_records=total_records,
        high_risk_count=high_risk_count,
        review_rate=review_rate,
        uploaded_by=user.email,
    )
    db.add(batch)
    db.flush()

    for _, row in analyzed.iterrows():
        record_data = {column: str(row.get(column, "")) for column in REQUIRED_COLUMNS}
        db.add(
            BeneficiaryRecord(
                batch_id=batch.id,
                **record_data,
                fraud_score=int(row["fraud_score"]),
                risk_level=str(row["risk_level"]),
                fraud_flags=list(row["fraud_flags"]),
                score_breakdown=list(row["score_breakdown"]),
                risk_explanation=str(row["risk_explanation"]),
                similar_name_matches=str(row.get("similar_name_matches", "")),
            )
        )

    write_audit(
        db,
        user,
        action="batch_uploaded",
        batch_id=batch.id,
        new_value={
            "file_name": batch.file_name,
            "total_records": total_records,
            "high_risk_count": high_risk_count,
            "review_rate": review_rate,
        },
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=list[UploadBatchOut])
def list_uploads(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER, UserRole.VIEWER)),
) -> list[UploadBatch]:
    return db.query(UploadBatch).order_by(UploadBatch.upload_date.desc()).limit(100).all()
