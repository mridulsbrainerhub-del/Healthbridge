import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Insurance(Base):
    __tablename__ = "insurance"

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

    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    policy_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )