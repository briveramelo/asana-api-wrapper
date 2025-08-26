"""FastAPI endpoints exposing Asana helper utilities for LLM use."""

from typing import Optional

from fastapi import APIRouter, Body

from src.core.wrapper import (
    add_tags_to_task,
    create_project_from_json,
    create_tag as create_tag_in_asana,
    create_tasks_in_project,
)
from src.core.asana_mapping_generator import generate_asana_mapping
from src.core.models import (
    MappingResult,
    ProjectResult,
    ProjectSpec,
    TagResult,
    TagSpec,
    TaskResult,
    TaskSpec,
)

router = APIRouter()


@router.post("/project")
def create_project(spec: ProjectSpec = Body(...)) -> ProjectResult:
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
        "tags", "section"/"section_name", and optional ``subtasks`` which is a list of
        ``TaskSpec``.

    Returns
    -------
    ProjectResult
        ``{"project": {...}, "sections": [...], "tasks": [...]}``
    """

    result = create_project_from_json(spec)
    return result


@router.post("/project/{project_gid}/tasks")
def create_tasks(
    project_gid: str,
    tasks: list[TaskSpec] = Body(...),
) -> list[TaskResult]:
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
              "tags": [TagSpec, ...],
              "section": "section_gid" | null,
              "section_name": "Section",
              "subtasks": [TaskSpec, ...]
            }

    Returns
    -------
    list[TaskResult]
        List of task objects returned by the Asana API.
    """

    created = create_tasks_in_project(project_gid, tasks)
    return created


@router.post("/tag")
def create_tag(spec: TagSpec = Body(...)) -> TagResult:
    """Create a tag in the workspace."""
    return create_tag_in_asana(spec)


@router.post("/task/{task_gid}/tags")
def add_tags(task_gid: str, tag_gids: list[str] = Body(...)) -> list[TagResult]:
    """Attach existing tags to a task."""
    return add_tags_to_task(task_gid, tag_gids)


@router.post("/mapping")
def generate_mapping(
    workspace_gid: Optional[str] = None,
    projects: Optional[list[str]] = None,
) -> MappingResult:
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
    MappingResult
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

    mapping_result = generate_asana_mapping(
        workspace_gid=workspace_gid,
        projects=projects,
    )
    return mapping_result
