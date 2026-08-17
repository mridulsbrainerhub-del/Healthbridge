from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.dependencies import require_nurse, require_doctor
from ..db.database import get_db

from ..models.patient import Patient
from ..models.condition import Condition
from ..models.alerts import Alert
from ..models.medication import Medication
from ..models.vital import Vital


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/nurse")
async def nurse_dashboard(
    current_user=Depends(require_nurse),
    db: Session = Depends(get_db),
):
    patients = db.query(Patient).all()

    roster = []

    for patient in patients:

        # -------------------------------------------------
        # Conditions
        # -------------------------------------------------

        conditions = (
            db.query(Condition)
            .filter(Condition.patient_id == patient.id)
            .all()
        )

        condition_names = [
            condition.condition_name
            for condition in conditions
        ]

        # -------------------------------------------------
        # Latest vital
        # -------------------------------------------------

        latest_vital = (
            db.query(Vital)
            .filter(Vital.patient_id == patient.id)
            .order_by(Vital.recorded_at.desc())
            .first()
        )

        latest_vitals_summary = {}

        if latest_vital:
            latest_vitals_summary = {
                "recorded_at": latest_vital.recorded_at,
                "systolic": latest_vital.systolic,
                "diastolic": latest_vital.diastolic,
                "heart_rate": latest_vital.heart_rate,
                "glucose": latest_vital.glucose,
                "weight": latest_vital.weight,
                "spo2": latest_vital.spo2,
                "notes": latest_vital.notes,
            }

        # -------------------------------------------------
        # Unresolved alerts
        # -------------------------------------------------

        unresolved_alerts = (
            db.query(Alert)
            .filter(
                Alert.patient_id == patient.id,
                Alert.resolved == False,
            )
            .all()
        )

        # -------------------------------------------------
        # Medication adherence
        # -------------------------------------------------

        medications = (
            db.query(Medication)
            .filter(Medication.patient_id == patient.id)
            .all()
        )

        adherence_flag = any(
            (
                medication.adherence_notes
                and (
                    "missed" in medication.adherence_notes.lower()
                    or "inconsistent"
                    in medication.adherence_notes.lower()
                )
            )
            for medication in medications
        )

        # -------------------------------------------------
        # Build patient roster
        # -------------------------------------------------

        roster.append({
            "patient_id": patient.patient_code,
            "full_name": (
                f"{patient.first_name} "
                f"{patient.last_name}"
            ),
            "conditions": condition_names,
            "assigned_doctor": patient.assigned_doctor,
            "latest_vitals_summary": latest_vitals_summary,
            "unresolved_alert_count": len(unresolved_alerts),
            "adherence_flag": adherence_flag,
        })

    # Patients with the most unresolved alerts first
    roster.sort(
        key=lambda patient: patient["unresolved_alert_count"],
        reverse=True,
    )

    return {
        "roster": roster
    }


@router.get("/doctor")
async def doctor_dashboard(
    current_user=Depends(require_doctor),
    db: Session = Depends(get_db),
):
    patients = db.query(Patient).all()

    overview = []

    for patient in patients:

        # -------------------------------------------------
        # Conditions
        # -------------------------------------------------

        conditions = (
            db.query(Condition)
            .filter(Condition.patient_id == patient.id)
            .all()
        )

        condition_names = [
            condition.condition_name
            for condition in conditions
        ]

        # -------------------------------------------------
        # Latest vital
        # -------------------------------------------------

        latest_vital = (
            db.query(Vital)
            .filter(Vital.patient_id == patient.id)
            .order_by(Vital.recorded_at.desc())
            .first()
        )

        latest_vitals_summary = {}

        if latest_vital:
            latest_vitals_summary = {
                "recorded_at": latest_vital.recorded_at,
                "systolic": latest_vital.systolic,
                "diastolic": latest_vital.diastolic,
                "heart_rate": latest_vital.heart_rate,
                "glucose": latest_vital.glucose,
                "weight": latest_vital.weight,
                "spo2": latest_vital.spo2,
                "notes": latest_vital.notes,
            }

        # -------------------------------------------------
        # High-severity unresolved alerts
        # -------------------------------------------------

        high_severity_alerts = (
            db.query(Alert)
            .filter(
                Alert.patient_id == patient.id,
                Alert.severity == "high",
                Alert.resolved == False,
            )
            .all()
        )

        escalations = [
            {
                "id": str(alert.id),
                "severity": alert.severity,
                "message": alert.message,
                "resolved": alert.resolved,
                "created_at": alert.created_at,
            }
            for alert in high_severity_alerts
        ]

        # -------------------------------------------------
        # Build doctor overview
        # -------------------------------------------------

        overview.append({
            "patient_id": patient.patient_code,
            "full_name": (
                f"{patient.first_name} "
                f"{patient.last_name}"
            ),
            "conditions": condition_names,
            "assigned_nurse": patient.assigned_nurse,
            "latest_vitals_summary": latest_vitals_summary,
            "escalations": escalations,
        })

    # Patients with the most escalations first
    overview.sort(
        key=lambda patient: len(patient["escalations"]),
        reverse=True,
    )

    return {
        "patients": overview
    }