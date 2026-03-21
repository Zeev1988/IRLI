import os
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class LabProfileORM(Base):
    __tablename__ = "lab_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    pi_name: Mapped[str] = mapped_column(Text, nullable=False)
    institution: Mapped[str] = mapped_column(Text, nullable=False)
    faculty: Mapped[str] = mapped_column(Text, nullable=False)
    research_summary: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    technologies: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    representative_papers: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    hiring_status: Mapped[str] = mapped_column(Text, nullable=False)
    lab_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    embedding: Mapped[list[float] | None] = mapped_column(
    Vector(int(os.getenv("EMBEDDING_DIM", "1024"))), nullable=True
    )

    publication_count: Mapped[int | None] = mapped_column(nullable=True)
    citation_count: Mapped[int | None] = mapped_column(nullable=True)
    h_index: Mapped[int | None] = mapped_column(nullable=True)
    semantic_scholar_author_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<LabProfileORM id={self.id} pi={self.pi_name!r}>"


class IngestionLogORM(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_url: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
