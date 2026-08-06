from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InsuranceCreate(BaseModel):
    provider: str
    policy_number: str


class InsuranceUpdate(BaseModel):
    provider: str | None = None
    policy_number: str | None = None


class InsuranceResponse(BaseModel):
    id: UUID
    patient_code: str

    provider: str
    policy_number: str

    model_config = ConfigDict(from_attributes=True)