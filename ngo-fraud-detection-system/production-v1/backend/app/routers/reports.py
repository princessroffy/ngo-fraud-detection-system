from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserRole
from app.schemas import CurrentUser
from app.security import require_roles
from app.services.reports import build_batch_pdf


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/batches/{batch_id}.pdf")
def download_batch_report(
    batch_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> StreamingResponse:
    try:
        pdf_buffer = build_batch_pdf(db, batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found") from exc

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="fraud-summary-{batch_id}.pdf"'},
    )
