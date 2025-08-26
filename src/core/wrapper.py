import logging
from typing import Any

from src.core.asana_client import get_client, with_backoff
from src.core.config import get_settings
from src.core.models import (
    ProjectMeta,
    ProjectRecord,
    ProjectResult,
    ProjectSpec,
    SectionResult,
    TagResult,
    TagSpec,
    TaskResult,
    TaskSpec,
)


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


def _map_custom_fields(client, project_gid: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    name_to_gid: dict[str, str] = {}
    option_map: dict[str, dict[str, str]] = {}
    field_settings = client.custom_field_settings.list_for_project(
        project_gid, opt_fields="custom_field.name,custom_field.enum_options"
    )
    for setting in field_settings:
        field = setting.get("custom_field") or {}
        name = field.get("name")
        gid = field.get("gid")
        if name and gid:
            name_to_gid[name] = gid
            options_map: dict[str, str] = {}
            for option in field.get("enum_options") or []:
                option_name = option.get("name")
                option_gid = option.get("gid")
                if option_name and option_gid:
                    options_map[option_name] = option_gid
            if options_map:
                option_map[name] = options_map
                option_map[gid] = options_map
    return name_to_gid, option_map


def _translate_custom_fields(
    custom_fields: dict[str, Any],
    name_to_gid: dict[str, str],
    option_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in custom_fields.items():
        field_gid = name_to_gid.get(key, key)
        if isinstance(value, str):
            options = option_map.get(key) or option_map.get(field_gid) or {}
            translated[field_gid] = options.get(value, value)
        else:
            translated[field_gid] = value
    return translated


def _collect_tag_specs(tasks: list[TaskSpec]) -> dict[str, TagSpec]:
    tag_map: dict[str, TagSpec] = {}
    for task in tasks:
        for tag in task.tags or []:
            if tag.name not in tag_map:
                tag_map[tag.name] = tag
        if task.subtasks:
            tag_map.update(_collect_tag_specs(task.subtasks))
    return tag_map


def _create_tags(client, tag_map: dict[str, TagSpec]) -> dict[str, str]:
    settings = get_settings()
    name_to_gid: dict[str, str] = {}
    for tag in tag_map.values():
        payload: dict[str, Any] = {"name": tag.name, "workspace": settings.workspace_gid}
        if tag.color:
            payload["color"] = tag.color
        if tag.notes:
            payload["notes"] = tag.notes
        created = with_backoff(client.tags.create, payload)
        name_to_gid[tag.name] = created["gid"]
    return name_to_gid


def _build_task_payload(
    project_gid: str,
    t: TaskSpec,
    section_name_to_gid: dict[str, str],
    custom_field_name_to_gid: dict[str, str],
    custom_field_option_map: dict[str, dict[str, str]],
    tag_name_to_gid: dict[str, str],
) -> dict[str, Any]:
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
        payload["tags"] = [tag_name_to_gid[tag.name] for tag in t.tags]
    if t.custom_fields is not None:
        payload["custom_fields"] = _translate_custom_fields(
            t.custom_fields,
            custom_field_name_to_gid,
            custom_field_option_map,
        )

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


def _create_subtasks_recursive(
    client,
    parent_task_gid: str,
    project_gid: str,
    subtasks: list[TaskSpec],
    custom_field_name_to_gid: dict[str, str],
    custom_field_option_map: dict[str, dict[str, str]],
    tag_name_to_gid: dict[str, str],
) -> None:
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
            sub_payload["tags"] = [tag_name_to_gid[tag.name] for tag in st.tags]
        if st.custom_fields is not None:
            sub_payload["custom_fields"] = _translate_custom_fields(
                st.custom_fields,
                custom_field_name_to_gid,
                custom_field_option_map,
            )
        # Optional: include project membership for visibility
        if st.inherit_project_membership:
            sub_payload["projects"] = [project_gid]
        created = with_backoff(client.tasks.create, sub_payload)
        if st.subtasks:
            _create_subtasks_recursive(
                client,
                created["gid"],
                project_gid,
                st.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )


def create_project_from_json(spec: ProjectSpec) -> ProjectResult:
    """Create a project and return structured metadata."""
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

    created_sections: list[SectionResult] = []
    section_name_to_gid: dict[str, str] = {}

    # Create sections if provided
    for s in spec.sections or []:
        sec = _create_section(client, project["gid"], s.name or "Section")
        if sec:
            sec_model = SectionResult.model_validate(sec)
            created_sections.append(sec_model)
            if sec_model.name:
                section_name_to_gid[sec_model.name] = sec_model.gid

    # Also map any preexisting sections (covers cases where project template has them)
    section_name_to_gid.update(_map_section_names(client, project["gid"]))

    # Create custom fields and attach to project
    for field_spec in spec.custom_fields or []:
        field_payload: dict[str, Any] = {
            "name": field_spec.name,
            "resource_subtype": field_spec.resource_subtype,
            "workspace": settings.workspace_gid,
        }
        if field_spec.description:
            field_payload["description"] = field_spec.description
        if field_spec.options:
            field_payload["enum_options"] = [
                {"name": option.name, **({"color": option.color} if option.color else {})}
                for option in field_spec.options
            ]
        created_field = with_backoff(client.custom_fields.create, field_payload)
        with_backoff(
            client.custom_field_settings.add_to_project,
            project["gid"],
            created_field["gid"],
        )

    custom_field_name_to_gid, custom_field_option_map = _map_custom_fields(client, project["gid"])

    tag_name_to_gid = _create_tags(client, _collect_tag_specs(spec.tasks or []))

    created_tasks: list[TaskResult] = []
    # Create tasks
    for t in spec.tasks or []:
        if not t.name:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(
            project["gid"],
            t,
            section_name_to_gid,
            custom_field_name_to_gid,
            custom_field_option_map,
            tag_name_to_gid,
        )
        created = with_backoff(client.tasks.create, payload)
        task_model = TaskResult.model_validate(created)
        created_tasks.append(task_model)
        # Subtasks
        if t.subtasks:
            _create_subtasks_recursive(
                client,
                task_model.gid,
                project["gid"],
                t.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )

    project_model = ProjectRecord.model_validate(project)
    return ProjectResult(project=project_model, sections=created_sections, tasks=created_tasks)


def create_tasks_in_project(project_gid: str, tasks_spec: list[TaskSpec]) -> list[TaskResult]:
    """Add tasks to an existing project from a list of TaskSpec models."""
    client = get_client()
    # Map section names if caller uses section_name
    section_name_to_gid = _map_section_names(client, project_gid)
    custom_field_name_to_gid, custom_field_option_map = _map_custom_fields(client, project_gid)
    tag_name_to_gid = _create_tags(client, _collect_tag_specs(tasks_spec))

    created: list[TaskResult] = []
    for t in tasks_spec:
        if not t.name:
            logger.warning("Skipping task with no name: %s", t)
            continue
        payload = _build_task_payload(
            project_gid,
            t,
            section_name_to_gid,
            custom_field_name_to_gid,
            custom_field_option_map,
            tag_name_to_gid,
        )
        task = with_backoff(client.tasks.create, payload)
        task_model = TaskResult.model_validate(task)
        created.append(task_model)
        if t.subtasks:
            _create_subtasks_recursive(
                client,
                task_model.gid,
                project_gid,
                t.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )
    return created


def create_tag(spec: TagSpec) -> TagResult:
    """Create a tag in the configured workspace."""
    client = get_client()
    settings = get_settings()
    payload: dict[str, Any] = {"name": spec.name, "workspace": settings.workspace_gid}
    if spec.color:
        payload["color"] = spec.color
    if spec.notes:
        payload["notes"] = spec.notes
    tag = with_backoff(client.tags.create, payload)
    return TagResult.model_validate(tag)


def add_tags_to_task(task_gid: str, tag_gids: list[str]) -> list[TagResult]:
    """Attach existing tags to a task."""
    client = get_client()
    results: list[TagResult] = []
    for tag_gid in tag_gids:
        tag = with_backoff(client.tasks.add_tag, task_gid, tag_gid)
        results.append(TagResult.model_validate(tag))
    return results

