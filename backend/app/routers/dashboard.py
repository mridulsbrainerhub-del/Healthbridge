from fastapi import APIRouter, Depends

from ..auth.dependencies import require_nurse, require_doctor
from ..db.database import SessionLocal
from ..services.chronic_care_repo import ChronicCareRepository


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/nurse")
async def nurse_dashboard(
    current_user=Depends(require_nurse)
):
    db = SessionLocal()

    try:
        repo = ChronicCareRepository(db)
        patients = repo.get_all_patients()

        roster = []

        for p in patients.values():
            vitals_history = p.get("vitals_history", [])
            latest = vitals_history[-1] if vitals_history else {}

            unresolved_alert_count = sum(
                1
                for alert in p.get("alerts", [])
                if not alert.get("resolved", False)
            )

            adherence_flag = any(
                "missed" in med.get("adherence_notes", "").lower()
                or "inconsistent" in med.get("adherence_notes", "").lower()
                for med in p.get("medications", [])
            )

            roster.append({
                "patient_id": p["patient_id"],
                "full_name": p["full_name"],
                "conditions": p.get("conditions", []),
                "assigned_doctor": p.get("assigned_doctor"),
                "latest_vitals_summary": latest,
                "vitals_history": vitals_history,
                "unresolved_alert_count": unresolved_alert_count,
                "adherence_flag": adherence_flag,
            })

        roster.sort(
            key=lambda r: r["unresolved_alert_count"],
            reverse=True
        )

        return {"roster": roster}

    finally:
        db.close()


@router.get("/doctor")
async def doctor_dashboard(
    current_user=Depends(require_doctor)
):
    db = SessionLocal()

    try:
        repo = ChronicCareRepository(db)
        patients = repo.get_all_patients()

        overview = []

        for p in patients.values():
            vitals_history = p.get("vitals_history", [])
            latest = vitals_history[-1] if vitals_history else {}

            high_severity_alerts = [
                alert
                for alert in p.get("alerts", [])
                if alert.get("severity") == "high"
                and not alert.get("resolved", False)
            ]

            overview.append({
                "patient_id": p["patient_id"],
                "full_name": p["full_name"],
                "conditions": p.get("conditions", []),
                "assigned_nurse": p.get("assigned_nurse"),
                "latest_vitals_summary": latest,
                "vitals_history": vitals_history,
                "escalations": high_severity_alerts,
            })

        overview.sort(
            key=lambda o: len(o["escalations"]),
            reverse=True
        )

        return {"patients": overview}

    finally:
        db.close()