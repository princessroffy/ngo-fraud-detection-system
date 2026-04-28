from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db, init_db
from app.routers import audit, records, reports, settings, uploads
from app.schemas import CurrentUser
from app.security import get_current_user
from app.services.weights import seed_default_weights


settings_config = get_settings()
app = FastAPI(title=settings_config.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_config.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_default_weights(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


@app.get("/api/stats")
def stats(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    from app.models import BeneficiaryRecord

    total = db.query(BeneficiaryRecord).count()
    high = db.query(BeneficiaryRecord).filter(BeneficiaryRecord.risk_level == "High").count()
    medium = db.query(BeneficiaryRecord).filter(BeneficiaryRecord.risk_level == "Medium").count()
    pending = db.query(BeneficiaryRecord).filter(BeneficiaryRecord.review_status == "Pending Review").count()
    return {
        "total_records": total,
        "high_risk": high,
        "medium_risk": medium,
        "pending_review": pending,
    }


app.include_router(uploads.router)
app.include_router(records.router)
app.include_router(settings.router)
app.include_router(audit.router)
app.include_router(reports.router)
