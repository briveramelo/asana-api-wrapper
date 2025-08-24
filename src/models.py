from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SectionSpec(BaseModel):
    name: str | None = None


class TaskSpec(BaseModel):
    name: str | None = None
    notes: str | None = None
    assignee: str | None = None  # GID
    due_on: str | None = None  # YYYY-MM-DD
    due_at: str | None = None  # RFC3339 timestamp
    followers: list[str] | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    section: str | None = None  # section GID
    section_name: str | None = None  # fallback by name (best-effort)
    subtasks: list["TaskSpec"] | None = None
    inherit_project_membership: bool | None = None


class ProjectMeta(BaseModel):
    name: str | None = None
    notes: str | None = None
    privacy: str | None = None  # "private" | "public_to_team" etc.


class ProjectSpec(BaseModel):
    project: ProjectMeta | None = None
    sections: list[SectionSpec] | None = None
    tasks: list[TaskSpec] | None = None


def task_spec_schema() -> dict[str, Any]:
    return TaskSpec.model_json_schema()


def project_spec_schema() -> dict[str, Any]:
    return ProjectSpec.model_json_schema()


# Resolve forward references for TaskSpec
TaskSpec.model_rebuild()

