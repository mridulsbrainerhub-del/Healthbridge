from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict,EmailStr


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone: str
    email: EmailStr
    address: str


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class PatientResponse(BaseModel):
    id: UUID
    patient_code: str

    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone: str
    email: str
    address: str

    assigned_nurse: str | None = None
    assigned_doctor: str | None = None
    care_program: str | None = None
    enrollment_date: date | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)