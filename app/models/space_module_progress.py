import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SpaceModuleProgress(Base):
    __tablename__ = "space_module_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "module_id", name="uq_space_module_progress"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
