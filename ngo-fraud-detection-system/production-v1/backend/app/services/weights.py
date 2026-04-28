from sqlalchemy.orm import Session

from app.models import FraudWeight


DEFAULT_FRAUD_WEIGHTS = {
    "exact_duplicate_row": {"label": "Exact duplicate row", "score": 40},
    "repeated_beneficiary_id": {"label": "Repeated beneficiary ID", "score": 35},
    "repeated_full_name": {"label": "Repeated full name", "score": 20},
    "repeated_phone_number": {"label": "Repeated phone number", "score": 30},
    "repeated_email_address": {"label": "Repeated email address", "score": 30},
    "phone_many_names": {"label": "Same phone used by different names", "score": 35},
    "email_many_names": {"label": "Same email used by different names", "score": 35},
    "similar_beneficiary_name": {"label": "Similar beneficiary name", "score": 20},
    "address_many_names": {"label": "Same address used by many names", "score": 25},
    "same_person_across_programs": {"label": "Same person appears across programs", "score": 15},
}


def seed_default_weights(db: Session) -> None:
    existing = {weight.rule_key for weight in db.query(FraudWeight).all()}
    for rule_key, config in DEFAULT_FRAUD_WEIGHTS.items():
        if rule_key in existing:
            continue
        db.add(
            FraudWeight(
                rule_key=rule_key,
                label=config["label"],
                score=config["score"],
            )
        )
    db.commit()


def get_weight_config(db: Session) -> dict[str, dict[str, int | str]]:
    seed_default_weights(db)
    weights = db.query(FraudWeight).all()
    return {
        weight.rule_key: {
            "label": weight.label,
            "score": weight.score,
        }
        for weight in weights
    }
