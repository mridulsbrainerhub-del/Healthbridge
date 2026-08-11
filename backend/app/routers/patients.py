from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import require_clinical_or_admin
from ..db.database import SessionLocal
from ..services.chronic_care_repo import ChronicCareRepository


router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)


@router.get("")
async def get_patients(
    current_user=Depends(require_clinical_or_admin)
):
    db = SessionLocal()

    try:
        repo = ChronicCareRepository(db)
        patients = repo.get_all_patients()

        return patients

    finally:
        db.close()


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str,
    current_user=Depends(require_clinical_or_admin)
):
    db = SessionLocal()

    try:
        repo = ChronicCareRepository(db)

        patients = repo.get_all_patients()

        patient = patients.get(patient_id)

        if not patient:
            raise HTTPException(
                status_code=404,
                detail="Patient not found"
            )

        return patient

    finally:
        db.close()