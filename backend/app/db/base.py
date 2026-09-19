from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    plex_url: Mapped[str] = mapped_column(String(500), default="")
    plex_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    mediux_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    kometa_asset_dir: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Library(Base):
    __tablename__ = "libraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plex_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(20))
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list["MediaItem"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )


class MediaItem(Base):
    __tablename__ = "media_items"
    __table_args__ = (UniqueConstraint("library_id", "rating_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"))
    rating_key: Mapped[str] = mapped_column(String(100), index=True)
    media_type: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    tvdb_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    media_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    asset_name: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    last_exported_set_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    library: Mapped[Library] = relationship(back_populates="items")
    mediux_cache: Mapped["MediuxAvailabilityCache | None"] = relationship(
        cascade="all, delete-orphan", single_parent=True
    )


class MediuxAvailabilityCache(Base):
    __tablename__ = "mediux_availability_cache"

    media_item_id: Mapped[int] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE"), primary_key=True
    )
    media_type: Mapped[str] = mapped_column(String(20))
    tmdb_id: Mapped[str] = mapped_column(String(50), index=True)
    has_assets: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sets: Mapped[list] = mapped_column(JSON, default=list)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"))
    mediux_set_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    results: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
