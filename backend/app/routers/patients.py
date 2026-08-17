from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.dependencies import require_clinical_or_admin
from ..db.database import get_db
from ..models.patient import Patient


router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)


@router.get("")
async def get_patients(
    current_user=Depends(require_clinical_or_admin),
    db: Session = Depends(get_db),
):
    patients = db.query(Patient).all()

    return patients


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str,
    current_user=Depends(require_clinical_or_admin),
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.patient_code == patient_id)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    return patient