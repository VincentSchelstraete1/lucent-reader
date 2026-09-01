from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("user_id", "type", "url", name="uq_sources_user_type_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    documents: Mapped[list["Document"]] = relationship(back_populates="source")
