from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    language: Mapped[str] = mapped_column(String(20), default="python")
    repo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    files: Mapped[list["SourceFile"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (UniqueConstraint("project_id", "path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="files")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    threshold: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    autofix: Mapped[bool] = mapped_column(Boolean, default=False)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    files_count: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="analyses")
    smells: Mapped[list["Smell"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class Smell(Base):
    __tablename__ = "smells"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(300))
    line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)

    analysis: Mapped[Analysis] = relationship(back_populates="smells")
    rule: Mapped[Rule] = relationship()
    fix: Mapped["Fix | None"] = relationship(back_populates="smell", uselist=False)


class Fix(Base):
    __tablename__ = "fixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    smell_id: Mapped[int] = mapped_column(ForeignKey("smells.id", ondelete="CASCADE"), unique=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id", ondelete="CASCADE"))
    diff: Mapped[str] = mapped_column(Text)
    old_content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="applied")
    applied_by: Mapped[str] = mapped_column(String(100), default="developer")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    smell: Mapped[Smell] = relationship(back_populates="fix")
