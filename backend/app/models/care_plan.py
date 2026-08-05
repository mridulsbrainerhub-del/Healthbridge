import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CarePlan(Base):
    __tablename__ = "care_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=False,
        unique=True,
    )

    next_appointment: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    goals: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )