from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LabCreate(BaseModel):
    test_name: str
    test_date: date
    result: str
    status: str


class LabUpdate(BaseModel):
    test_name: str | None = None
    test_date: date | None = None
    result: str | None = None
    status: str | None = None


class LabResponse(BaseModel):
    id: UUID
    patient_code: str

    test_name: str
    test_date: date
    result: str
    status: str

    model_config = ConfigDict(from_attributes=True)