import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Vital(Base):
    __tablename__ = "vitals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=False,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    systolic: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    diastolic: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    heart_rate: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    glucose: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    weight: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    spo2: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )