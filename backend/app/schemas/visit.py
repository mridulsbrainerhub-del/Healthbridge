from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VisitCreate(BaseModel):
    visit_date: date
    visit_type: str
    provider: str
    notes: str


class VisitUpdate(BaseModel):
    visit_date: date | None = None
    visit_type: str | None = None
    provider: str | None = None
    notes: str | None = None


class VisitResponse(BaseModel):
    id: UUID
    patient_code: str

    visit_date: date
    visit_type: str
    provider: str
    notes: str

    model_config = ConfigDict(from_attributes=True)