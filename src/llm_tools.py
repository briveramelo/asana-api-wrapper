"""FastAPI endpoints exposing Asana helper utilities for LLM use."""

from typing import Any, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel

from .wrapper import create_project_from_json, create_tasks_in_project
from .asana_mapping_generator import generate_asana_mapping
from .models import ProjectSpec, TaskSpec

router = APIRouter()


class ProjectCreationResult(BaseModel):
    project: dict[str, Any]
    sections: list[dict[str, Any]]
    tasks: list[dict[str, Any]]


class TasksCreationResult(BaseModel):
    tasks: list[dict[str, Any]]


class MappingModel(BaseModel):
    projects: dict[str, str]
    sections: dict[str, dict[str, str]]
    custom_fields: dict[str, dict[str, Any]]
    tags: dict[str, str]
    users: dict[str, str]


@router.post("/project")
def create_project(spec: ProjectSpec = Body(...)) -> ProjectCreationResult:
    """Create an Asana project from a JSON specification.

    Parameters
    ----------
    spec : ProjectSpec
        JSON object describing the project to create. Schema::

            {
              "project": {"name": "My Project", ...},
              "sections": [{"name": "Section"}, ...],
              "tasks": [TaskSpec, ...]
            }

        ``TaskSpec`` includes keys like "name", "notes", "assignee", "due_on",
        "section"/"section_name", and optional ``subtasks`` which is a list of
        ``TaskSpec``.

    Returns
    -------
    ProjectCreationResult
        ``{"project": {...}, "sections": [...], "tasks": [...]}``
    """

    result = create_project_from_json(spec)
    return ProjectCreationResult(**result)


@router.post("/project/{project_gid}/tasks")
def create_tasks(
    project_gid: str,
    tasks: list[TaskSpec] = Body(...),
) -> TasksCreationResult:
    """Add tasks to an existing project.

    Parameters
    ----------
    project_gid : str
        GID of the target project.
    tasks : list[TaskSpec]
        JSON array describing tasks to create. Each ``TaskSpec`` has the schema::

            {
              "name": "Task name",
              "notes": "Optional description",
              "assignee": "user_gid",
              "due_on": "YYYY-MM-DD",
              "section": "section_gid" | null,
              "section_name": "Section",
              "subtasks": [TaskSpec, ...]
            }

    Returns
    -------
    TasksCreationResult
        Wrapper around the list of task objects returned by the Asana API.
    """

    created = create_tasks_in_project(project_gid, tasks)
    return TasksCreationResult(tasks=created)


@router.post("/mapping")
def generate_mapping(
    workspace_gid: Optional[str] = None,
    projects: Optional[list[str]] = None,
) -> MappingModel:
    """Generate a lightweight mapping of Asana identifiers.

    Parameters
    ----------
    workspace_gid : str, optional
        Workspace to index. Defaults to ``settings.workspace_gid`` if omitted.
    projects : list[str], optional
        Optional list of project names to include; defaults to all projects in the
        workspace.

    Returns
    -------
    MappingModel
        Mapping with schema::

            {
              "projects": {"Project": "gid"},
              "sections": {"Project": {"Section": "gid"}},
              "custom_fields": {
                "Project": {
                  "Field": {"field_gid": "...", "resource_subtype": "enum",
                             "options": {"Opt": "gid"}}
                }
              },
              "tags": {"Tag": "gid"},
              "users": {"User": "gid"}
            }
    """

    mapping = generate_asana_mapping(
        workspace_gid=workspace_gid,
        projects=projects,
    )
    return MappingModel(**mapping)
