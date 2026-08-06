from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AllergyCreate(BaseModel):
    allergen: str
    severity: str
    reaction: str


class AllergyUpdate(BaseModel):
    allergen: str | None = None
    severity: str | None = None
    reaction: str | None = None


class AllergyResponse(BaseModel):
    id: UUID
    patient_code: str

    allergen: str
    severity: str
    reaction: str

    model_config = ConfigDict(from_attributes=True)