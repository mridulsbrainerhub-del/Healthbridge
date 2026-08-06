from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VitalCreate(BaseModel):
    recorded_date: date
    blood_pressure: str
    heart_rate: int
    oxygen_saturation: int
    weight: float


class VitalUpdate(BaseModel):
    recorded_date: date | None = None
    blood_pressure: str | None = None
    heart_rate: int | None = None
    oxygen_saturation: int | None = None
    weight: float | None = None


class VitalResponse(BaseModel):
    id: UUID
    patient_code: str

    recorded_date: date
    blood_pressure: str
    heart_rate: int
    oxygen_saturation: int
    weight: float

    model_config = ConfigDict(from_attributes=True)