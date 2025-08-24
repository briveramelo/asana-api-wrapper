from __future__ import annotations

import logging
from typing import Any

from .asana_client import get_client, with_backoff
from .config import get_settings
from .models import ProjectMeta, ProjectSpec, TaskSpec


logger = logging.getLogger(__name__)


def _create_section(client, project_gid: str, name: str) -> dict | None:
    """Create a section by name; supports both old/new SDK method names."""
    try:
        return with_backoff(client.sections.create_section_for_project, project_gid, {"name": name})
    except AttributeError:
        pass
    try:
        return with_backoff(client.sections.create_in_project, project_gid, {"name": name})
    except Exception as e:
        logger.warning("Could not create section '%s': %s", name, e)
        return None


def _list_sections(client, project_gid: str) -> list[dict]:
    try:
        return list(with_backoff(client.sections.get_sections_for_project, project_gid))
    except AttributeError:
        pass
    try:
        return list(with_backoff(client.sections.find_by_project, project_gid))
    except Exception:
        return []


def _map_section_names(client, project_gid: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for s in _list_sections(client, project_gid):
        nm = s.get("name")
        gid = s.get("gid")
        if nm and gid:
            mapping[nm] = gid
    return mapping


def _build_task_payload(project_gid: str, t: TaskSpec, section_name_to_gid: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": t.name,
        "projects": [project_gid],
    }
    # Optional simple fields
    for key in ("notes", "assignee", "due_on", "due_at"):
        value = getattr(t, key)
        if value is not None:
            payload[key] = value

    if t.followers is not None:
        payload["followers"] = t.followers
    if t.tags is not None:
        payload["tags"] = t.tags
    if t.custom_fields is not None:
        payload["custom_fields"] = t.custom_fields

    # Section placement (prefer explicit GID; else name lookup)
    memberships = []
    section_gid = t.section
    if not section_gid and t.section_name:
        section_gid = section_name_to_gid.get(t.section_name)
    if section_gid:
        memberships.append({"project": project_gid, "section": section_gid})
    if memberships:
        payload["memberships"] = memberships

    return payload


def _create_subtasks_recursive(client, parent_task_gid: str, project_gid: str, subtasks: list[TaskSpec]) -> None:
    for st in subtasks:
        sub_payload = {"name": st.name, "parent": parent_task_gid}
        # Optional attributes for subtasks
        for key in ("notes", "assignee", "due_on", "due_at"):
            value = getattr(st, key)
            if value is not None:
                sub_payload[key] = value
        if st.followers is not None:
            sub_payload["followers"] = st.followers
        if st.tags is not None:
            sub_payload["tags"] = st.tags
        if st.custom_fields is not None:
            sub_payload["custom_fields"] = st.custom_fields
        # Optional: include project membership for visibility
        if st.inherit_project_membership:
            sub_payload["projects"] = [project_gid]
        created = with_backoff(client.tasks.create, sub_payload)
        if st.subtasks:
            _create_subtasks_recursive(client, created["gid"], project_gid, st.subtasks)


def create_project_from_json(spec: ProjectSpec) -> dict[str, Any]:
    """Create a project (and optional sections + tasks) from a JSON-like dict.

    Returns a dictionary with keys: project, sections (list), tasks (list).
    """
    client = get_client()
    settings = get_settings()

    project_meta = spec.project or ProjectMeta()
    p_payload = {
        "name": project_meta.name or "Untitled Project",
        "workspace": settings.workspace_gid,
        "team": settings.team_gid,
    }
    if project_meta.notes:
        p_payload["notes"] = project_meta.notes
    if project_meta.privacy:
        p_payload["privacy_setting"] = project_meta.privacy

    project = with_backoff(client.projects.create, p_payload)

    created_sections: list[dict] = []
    section_name_to_gid: dict[str, str] = {}

    # Create sections if provided
    for s in spec.sections or []:
        sec = _create_section(client, project["gid"], s.name or "Section")
        if sec:
            created_sections.append(sec)
            section_name_to_gid[sec["name"]] = sec["gid"]

    # Also map any preexisting sections (covers cases where project template has them)
    section_name_to_gid.update(_map_section_names(client, project["gid"]))

    created_tasks: list[dict] = []
    # Create tasks
    for t in spec.tasks or []:
        if not t.name:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(project["gid"], t, section_name_to_gid)
        created = with_backoff(client.tasks.create, payload)
        created_tasks.append(created)
        # Subtasks
        if t.subtasks:
            _create_subtasks_recursive(client, created["gid"], project["gid"], t.subtasks)

    return {"project": project, "sections": created_sections, "tasks": created_tasks}


def create_tasks_in_project(project_gid: str, tasks_spec: list[TaskSpec]) -> list[dict]:
    """Add tasks to an existing project from a list of TaskSpec models."""
    client = get_client()
    # Map section names if caller uses section_name
    section_name_to_gid = _map_section_names(client, project_gid)

    created: list[dict] = []
    for t in tasks_spec:
        if not t.name:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(project_gid, t, section_name_to_gid)
        task = with_backoff(client.tasks.create, payload)
        created.append(task)
        if t.subtasks:
            _create_subtasks_recursive(client, task["gid"], project_gid, t.subtasks)
    return created

