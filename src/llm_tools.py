"""FastAPI endpoints exposing Asana helper utilities for LLM use."""

from typing import Optional

from fastapi import APIRouter, Body

from .wrapper import create_project_from_json, create_tasks_in_project
from .asana_mapping_generator import generate_asana_mapping

router = APIRouter()


@router.post("/project")
def create_project(spec: dict[str, any] = Body(...)) -> dict[str, any]:
    """Create an Asana project from a JSON specification.

    Parameters
    ----------
    spec : dict
        JSON object describing the project to create. Schema::

            {
              "project": {"name": "My Project", ...},
              "sections": [{"name": "Section"}, ...],
              "tasks": [TaskSpec, ...]
            }

        TaskSpec is a dict with keys such as "name", "notes", "assignee",
        "due_on", "section"/"section_name", and optional "subtasks" which is a
        list of TaskSpec.

    Returns
    -------
    dict
        ``{"project": {...}, "sections": [...], "tasks": [...]}``
    """

    return create_project_from_json(spec)


@router.post("/project/{project_gid}/tasks")
def create_tasks(
    project_gid: str,
    tasks: list[dict[str, any]] = Body(...),
) -> list[dict[str, any]]:
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
    list[dict]
        list of task objects returned by the Asana API.
    """

    return create_tasks_in_project(project_gid, tasks)


@router.post("/mapping")
def generate_mapping(
    workspace_gid: Optional[str] = None,
    projects: Optional[list[str]] = None,
) -> dict[str, any]:
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
    dict
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

    return generate_asana_mapping(
        workspace_gid=workspace_gid,
        projects=projects,
    )
