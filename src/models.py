from __future__ import annotations
from typing import Dict, List, Optional, Any, TypedDict

class SectionSpec(TypedDict, total=False):
    name: str

class TaskSpec(TypedDict, total=False):
    name: str
    notes: str
    assignee: str              # GID
    due_on: str                # YYYY-MM-DD
    due_at: str                # RFC3339 timestamp
    followers: List[str]
    tags: List[str]
    custom_fields: Dict[str, Any]
    section: str               # section GID
    section_name: str          # fallback by name (best-effort)
    subtasks: List["TaskSpec"]

class ProjectMeta(TypedDict, total=False):
    name: str
    notes: str
    privacy: str               # "private" | "public_to_team" etc.

class ProjectSpec(TypedDict, total=False):
    project: ProjectMeta
    sections: List[SectionSpec]
    tasks: List[TaskSpec]