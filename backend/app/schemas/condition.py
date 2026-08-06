from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConditionCreate(BaseModel):
    condition_name: str
    status: str


class ConditionUpdate(BaseModel):
    condition_name: str | None = None
    status: str | None = None


class ConditionResponse(BaseModel):
    id: UUID
    patient_code: str

    condition_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)