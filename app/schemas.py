from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    language: Literal["python"] = "python"
    repo_url: str | None = Field(default=None, max_length=300)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    repo_url: str | None = Field(default=None, max_length=300)


class ProjectOut(ORM):
    id: int
    name: str
    language: str
    repo_url: str | None
    created_at: datetime


class FileIn(BaseModel):
    path: str = Field(min_length=1, max_length=300, pattern=r"^[\w./-]+\.py$")
    content: str = Field(max_length=500_000)


class FileOut(ORM):
    id: int
    path: str
    lines: int


class RuleOut(ORM):
    id: int
    code: str
    name: str
    category: str
    threshold: int
    enabled: bool
    autofix: bool


class RuleUpdate(BaseModel):
    threshold: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None


class SmellOut(ORM):
    id: int
    rule_code: str
    file_path: str
    line: int
    end_line: int
    severity: str
    message: str
    fixable: bool


class AnalysisOut(ORM):
    id: int
    project_id: int
    status: str
    started_at: datetime
    duration_ms: float
    files_count: int
    smells_count: int
    by_severity: dict[str, int]


class FixOut(ORM):
    id: int | None
    smell_id: int
    status: str
    diff: str
