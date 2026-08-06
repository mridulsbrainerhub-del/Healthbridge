from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertCreate(BaseModel):
    alert_type: str
    message: str
    priority: str
    alert_date: date


class AlertUpdate(BaseModel):
    alert_type: str | None = None
    message: str | None = None
    priority: str | None = None
    alert_date: date | None = None


class AlertResponse(BaseModel):
    id: UUID
    patient_code: str

    alert_type: str
    message: str
    priority: str
    alert_date: date

    model_config = ConfigDict(from_attributes=True)