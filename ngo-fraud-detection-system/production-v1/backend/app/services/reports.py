from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models import BeneficiaryRecord, UploadBatch


def build_batch_pdf(db: Session, batch_id: str) -> BytesIO:
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise ValueError("Batch not found")

    records = (
        db.query(BeneficiaryRecord)
        .filter(BeneficiaryRecord.batch_id == batch_id)
        .order_by(BeneficiaryRecord.fraud_score.desc())
        .all()
    )
    high = sum(1 for record in records if record.risk_level == "High")
    medium = sum(1 for record in records if record.risk_level == "Medium")
    low = sum(1 for record in records if record.risk_level == "Low")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Fraud Summary Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Fraud Summary Report", styles["Title"]),
        Paragraph(f"File: {batch.file_name}", styles["Normal"]),
        Paragraph(f"Uploaded by: {batch.uploaded_by}", styles["Normal"]),
        Paragraph(f"Upload date: {batch.upload_date}", styles["Normal"]),
        Spacer(1, 14),
    ]

    summary_table = Table(
        [
            ["Total Records", "High Risk", "Medium Risk", "Low Risk", "Review Rate"],
            [str(len(records)), str(high), str(medium), str(low), f"{batch.review_rate}%"],
        ]
    )
    summary_table.setStyle(_table_style())
    story.extend([summary_table, Spacer(1, 16)])

    community_counts: dict[str, int] = {}
    for record in records:
        if record.risk_level in {"High", "Medium"}:
            community = record.community or "Unknown"
            community_counts[community] = community_counts.get(community, 0) + 1
    top_communities = sorted(community_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    community_table = Table([["Community", "Suspicious Records"], *top_communities])
    community_table.setStyle(_table_style())
    story.extend([Paragraph("Top Suspicious Communities", styles["Heading2"]), community_table, Spacer(1, 16)])

    flagged_rows = [["Name", "Score", "Risk", "Status", "Reviewer Notes"]]
    for record in records[:25]:
        flagged_rows.append(
            [
                record.full_name,
                str(record.fraud_score),
                record.risk_level,
                record.review_status,
                record.reviewer_notes or "",
            ]
        )
    flagged_table = Table(flagged_rows, repeatRows=1)
    flagged_table.setStyle(_table_style())
    story.extend([Paragraph("Flagged Records", styles["Heading2"]), flagged_table])

    doc.build(story)
    buffer.seek(0)
    return buffer


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#101828")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]
    )
