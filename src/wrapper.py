from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional
from .client import get_client, _with_backoff
from .config import get_settings
from .models import ProjectSpec, TaskSpec

logger = logging.getLogger(__name__)


def _create_section(client, project_gid: str, name: str) -> Optional[dict]:
    """Create a section by name; supports both old/new SDK method names."""
    try:
        return _with_backoff(client.sections.create_section_for_project, project_gid, {"name": name})
    except AttributeError:
        pass
    try:
        return _with_backoff(client.sections.create_in_project, project_gid, {"name": name})
    except Exception as e:
        logger.warning("Could not create section '%s': %s", name, e)
        return None


def _list_sections(client, project_gid: str) -> List[dict]:
    try:
        return list(_with_backoff(client.sections.get_sections_for_project, project_gid))
    except AttributeError:
        pass
    try:
        return list(_with_backoff(client.sections.find_by_project, project_gid))
    except Exception:
        return []


def _map_section_names(client, project_gid: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for s in _list_sections(client, project_gid):
        nm = s.get("name")
        gid = s.get("gid")
        if nm and gid:
            mapping[nm] = gid
    return mapping


def _build_task_payload(project_gid: str, t: TaskSpec, section_name_to_gid: Dict[str, str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": t["name"],
        "projects": [project_gid],
    }
    # Optional simple fields
    for key in ("notes", "assignee", "due_on", "due_at"):
        if key in t:
            payload[key] = t[key]  # type: ignore[index]

    if "followers" in t:
        payload["followers"] = t["followers"]
    if "tags" in t:
        payload["tags"] = t["tags"]
    if "custom_fields" in t:
        payload["custom_fields"] = t["custom_fields"]

    # Section placement (prefer explicit GID; else name lookup)
    memberships = []
    section_gid = t.get("section")
    if not section_gid and t.get("section_name"):
        section_gid = section_name_to_gid.get(t["section_name"])  # type: ignore[index]
    if section_gid:
        memberships.append({"project": project_gid, "section": section_gid})
    if memberships:
        payload["memberships"] = memberships

    return payload


def _create_subtasks_recursive(client, parent_task_gid: str, project_gid: str, subtasks: List[TaskSpec]):
    for st in subtasks:
        sub_payload = {"name": st["name"], "parent": parent_task_gid}
        # Optional attributes for subtasks
        for key in ("notes", "assignee", "due_on", "due_at"):
            if key in st:
                sub_payload[key] = st[key]  # type: ignore[index]
        if "followers" in st:
            sub_payload["followers"] = st["followers"]
        if "tags" in st:
            sub_payload["tags"] = st["tags"]
        if "custom_fields" in st:
            sub_payload["custom_fields"] = st["custom_fields"]
        # Optional: include project membership for visibility
        if st.get("inherit_project_membership", False):
            sub_payload["projects"] = [project_gid]
        created = _with_backoff(client.tasks.create, sub_payload)
        if st.get("subtasks"):
            _create_subtasks_recursive(client, created["gid"], project_gid, st["subtasks"])  # type: ignore[index]


def create_project_from_json(spec: ProjectSpec) -> Dict[str, Any]:
    """Create a project (and optional sections + tasks) from a JSON-like dict.

    Returns a dictionary with keys: project, sections (list), tasks (list).
    """
    client = get_client()
    settings = get_settings()

    project_meta = spec.get("project", {})
    p_payload = {
        "name": project_meta.get("name", "Untitled Project"),
        "workspace": settings.workspace_gid,
        "team": settings.team_gid,
    }
    if project_meta.get("notes"):
        p_payload["notes"] = project_meta["notes"]  # type: ignore[index]
    if project_meta.get("privacy"):
        p_payload["privacy_setting"] = project_meta["privacy"]  # type: ignore[index]

    project = _with_backoff(client.projects.create, p_payload)

    created_sections: List[dict] = []
    section_name_to_gid: Dict[str, str] = {}

    # Create sections if provided
    for s in spec.get("sections", []) or []:
        sec = _create_section(client, project["gid"], s.get("name", "Section"))
        if sec:
            created_sections.append(sec)
            section_name_to_gid[sec["name"]] = sec["gid"]

    # Also map any preexisting sections (covers cases where project template has them)
    section_name_to_gid.update(_map_section_names(client, project["gid"]))

    created_tasks: List[dict] = []
    # Create tasks
    for t in spec.get("tasks", []) or []:
        if "name" not in t or not t["name"]:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(project["gid"], t, section_name_to_gid)
        created = _with_backoff(client.tasks.create, payload)
        created_tasks.append(created)
        # Subtasks
        if t.get("subtasks"):
            _create_subtasks_recursive(client, created["gid"], project["gid"], t["subtasks"])  # type: ignore[index]

    return {"project": project, "sections": created_sections, "tasks": created_tasks}


def create_tasks_in_project(project_gid: str, tasks_spec: List[TaskSpec]) -> List[dict]:
    """Add tasks to an existing project from a list of TaskSpec dicts."""
    client = get_client()
    # Map section names if caller uses section_name
    section_name_to_gid = _map_section_names(client, project_gid)

    created: List[dict] = []
    for t in tasks_spec:
        if "name" not in t or not t["name"]:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(project_gid, t, section_name_to_gid)
        task = _with_backoff(client.tasks.create, payload)
        created.append(task)
        if t.get("subtasks"):
            _create_subtasks_recursive(client, task["gid"], project_gid, t["subtasks"])  # type: ignore[index]
    return created