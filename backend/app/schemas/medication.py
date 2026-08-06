from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MedicationCreate(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    status: str


class MedicationUpdate(BaseModel):
    medication_name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    status: str | None = None


class MedicationResponse(BaseModel):
    id: UUID
    patient_code: str

    medication_name: str
    dosage: str
    frequency: str
    status: str

    model_config = ConfigDict(from_attributes=True)