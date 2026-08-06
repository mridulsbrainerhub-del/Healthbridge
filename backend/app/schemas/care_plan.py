from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CarePlanCreate(BaseModel):
    goal: str
    interventions: str
    review_date: date
    status: str


class CarePlanUpdate(BaseModel):
    goal: str | None = None
    interventions: str | None = None
    review_date: date | None = None
    status: str | None = None


class CarePlanResponse(BaseModel):
    id: UUID
    patient_code: str

    goal: str
    interventions: str
    review_date: date
    status: str

    model_config = ConfigDict(from_attributes=True)