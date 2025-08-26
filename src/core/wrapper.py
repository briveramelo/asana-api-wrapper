import logging
from typing import Any

from src.core.asana_client import get_client
from src.core.config import get_settings
from src.core.models import (
    ProjectMeta,
    ProjectResult,
    ProjectSpec,
    SectionResult,
    TagResult,
    TagSpec,
    TaskResult,
    TaskSpec,
)


logger = logging.getLogger(__name__)


def _create_section(client, project_gid: str, name: str) -> SectionResult | None:
    """Create a section by name; supports both old/new SDK method names."""
    try:
        return client.sections.create_section_for_project(project_gid, {"name": name})
    except AttributeError:
        pass
    try:
        return client.sections.create_in_project(project_gid, {"name": name})
    except Exception as exc:
        logger.warning("Could not create section '%s': %s", name, exc)
        return None


def _list_sections(client, project_gid: str) -> list[SectionResult]:
    try:
        return list(client.sections.get_sections_for_project(project_gid))
    except AttributeError:
        pass
    try:
        return list(client.sections.find_by_project(project_gid))
    except Exception:
        return []


def _map_section_names(client, project_gid: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for section in _list_sections(client, project_gid):
        if section.name:
            mapping[section.name] = section.gid
    return mapping


def _map_custom_fields(client, project_gid: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    name_to_gid: dict[str, str] = {}
    option_map: dict[str, dict[str, str]] = {}
    field_settings = client.custom_field_settings.list_for_project(
        project_gid, opt_fields="custom_field.name,custom_field.enum_options"
    )
    for setting in field_settings:
        field_data = setting.get("custom_field") or {}
        field_name = field_data.get("name")
        field_gid = field_data.get("gid")
        if field_name and field_gid:
            name_to_gid[field_name] = field_gid
            options_map: dict[str, str] = {}
            for option in field_data.get("enum_options") or []:
                option_name = option.get("name")
                option_gid = option.get("gid")
                if option_name and option_gid:
                    options_map[option_name] = option_gid
            if options_map:
                option_map[field_name] = options_map
                option_map[field_gid] = options_map
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


def _create_tags(client, tag_specs: list[TagSpec]) -> dict[str, str]:
    settings = get_settings()
    name_to_gid: dict[str, str] = {}
    for tag_spec in tag_specs:
        payload: dict[str, Any] = {"name": tag_spec.name, "workspace": settings.workspace_gid}
        if tag_spec.color:
            payload["color"] = tag_spec.color
        if tag_spec.notes:
            payload["notes"] = tag_spec.notes
        created_tag = client.tags.create(payload)
        name_to_gid[tag_spec.name] = created_tag.gid
    return name_to_gid


def _build_task_payload(
    project_gid: str,
    task_spec: TaskSpec,
    section_name_to_gid: dict[str, str],
    custom_field_name_to_gid: dict[str, str],
    custom_field_option_map: dict[str, dict[str, str]],
    tag_name_to_gid: dict[str, str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": task_spec.name,
        "projects": [project_gid],
    }
    for key in ("notes", "assignee", "due_on", "due_at"):
        value = getattr(task_spec, key)
        if value is not None:
            payload[key] = value

    if task_spec.followers is not None:
        payload["followers"] = task_spec.followers
    if task_spec.tags is not None:
        payload["tags"] = [tag_name_to_gid[tag_name] for tag_name in task_spec.tags]
    if task_spec.custom_fields is not None:
        payload["custom_fields"] = _translate_custom_fields(
            task_spec.custom_fields,
            custom_field_name_to_gid,
            custom_field_option_map,
        )

    memberships = []
    section_gid = task_spec.section
    if not section_gid and task_spec.section_name:
        section_gid = section_name_to_gid.get(task_spec.section_name)
    if section_gid:
        memberships.append({"project": project_gid, "section": section_gid})
    if memberships:
        payload["memberships"] = memberships

    return payload


def _create_subtasks_recursive(
    client,
    parent_task_gid: str,
    project_gid: str,
    subtask_specs: list[TaskSpec],
    custom_field_name_to_gid: dict[str, str],
    custom_field_option_map: dict[str, dict[str, str]],
    tag_name_to_gid: dict[str, str],
) -> None:
    for subtask_spec in subtask_specs:
        sub_payload = {"name": subtask_spec.name, "parent": parent_task_gid}
        for key in ("notes", "assignee", "due_on", "due_at"):
            value = getattr(subtask_spec, key)
            if value is not None:
                sub_payload[key] = value
        if subtask_spec.followers is not None:
            sub_payload["followers"] = subtask_spec.followers
        if subtask_spec.tags is not None:
            sub_payload["tags"] = [tag_name_to_gid[tag_name] for tag_name in subtask_spec.tags]
        if subtask_spec.custom_fields is not None:
            sub_payload["custom_fields"] = _translate_custom_fields(
                subtask_spec.custom_fields,
                custom_field_name_to_gid,
                custom_field_option_map,
            )
        if subtask_spec.inherit_project_membership:
            sub_payload["projects"] = [project_gid]
        created_task = client.tasks.create(sub_payload)
        if subtask_spec.subtasks:
            _create_subtasks_recursive(
                client,
                created_task.gid,
                project_gid,
                subtask_spec.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )


def create_project_from_json(project_spec: ProjectSpec) -> ProjectResult:
    """Create a project and return structured metadata."""
    client = get_client()
    settings = get_settings()

    project_meta = project_spec.project or ProjectMeta()
    project_payload = {
        "name": project_meta.name or "Untitled Project",
        "workspace": settings.workspace_gid,
        "team": settings.team_gid,
    }
    if project_meta.notes:
        project_payload["notes"] = project_meta.notes
    if project_meta.privacy:
        project_payload["privacy_setting"] = project_meta.privacy

    project = client.projects.create(project_payload)

    created_sections: list[SectionResult] = []
    section_name_to_gid: dict[str, str] = {}

    for section_spec in project_spec.sections or []:
        section = _create_section(client, project.gid, section_spec.name or "Section")
        if section:
            created_sections.append(section)
            if section.name:
                section_name_to_gid[section.name] = section.gid

    section_name_to_gid.update(_map_section_names(client, project.gid))

    for field_spec in project_spec.custom_fields or []:
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
        created_field = client.custom_fields.create(field_payload)
        client.custom_field_settings.add_to_project(project.gid, created_field["gid"])

    custom_field_name_to_gid, custom_field_option_map = _map_custom_fields(client, project.gid)

    tag_name_to_gid = _create_tags(client, project_spec.tags or [])

    created_tasks: list[TaskResult] = []
    for task_spec in project_spec.tasks or []:
        if not task_spec.name:
            logger.warning("Skipping task with no name: %s", task_spec)
            continue
        payload = _build_task_payload(
            project.gid,
            task_spec,
            section_name_to_gid,
            custom_field_name_to_gid,
            custom_field_option_map,
            tag_name_to_gid,
        )
        created_task = client.tasks.create(payload)
        created_tasks.append(created_task)
        if task_spec.subtasks:
            _create_subtasks_recursive(
                client,
                created_task.gid,
                project.gid,
                task_spec.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )

    return ProjectResult(project=project, sections=created_sections, tasks=created_tasks)


def create_tasks_in_project(
    project_gid: str,
    task_specs: list[TaskSpec],
    tag_specs: list[TagSpec] | None = None,
) -> list[TaskResult]:
    """Add tasks to an existing project.

    Parameters
    ----------
    project_gid : str
        Identifier of the target project.
    task_specs : list[TaskSpec]
        Task definitions to create.
    tag_specs : list[TagSpec], optional
        Tags to create prior to task creation.
    """
    client = get_client()
    section_name_to_gid = _map_section_names(client, project_gid)
    custom_field_name_to_gid, custom_field_option_map = _map_custom_fields(client, project_gid)
    tag_name_to_gid = _create_tags(client, tag_specs or [])

    created_tasks: list[TaskResult] = []
    for task_spec in task_specs:
        if not task_spec.name:
            logger.warning("Skipping task with no name: %s", task_spec)
            continue
        payload = _build_task_payload(
            project_gid,
            task_spec,
            section_name_to_gid,
            custom_field_name_to_gid,
            custom_field_option_map,
            tag_name_to_gid,
        )
        created_task = client.tasks.create(payload)
        created_tasks.append(created_task)
        if task_spec.subtasks:
            _create_subtasks_recursive(
                client,
                created_task.gid,
                project_gid,
                task_spec.subtasks,
                custom_field_name_to_gid,
                custom_field_option_map,
                tag_name_to_gid,
            )
    return created_tasks


def create_tag(tag_spec: TagSpec) -> TagResult:
    """Create a tag in the configured workspace."""
    client = get_client()
    settings = get_settings()
    payload: dict[str, Any] = {"name": tag_spec.name, "workspace": settings.workspace_gid}
    if tag_spec.color:
        payload["color"] = tag_spec.color
    if tag_spec.notes:
        payload["notes"] = tag_spec.notes
    return client.tags.create(payload)


def add_tags_to_task(task_gid: str, tag_gids: list[str]) -> list[TagResult]:
    """Attach existing tags to a task."""
    client = get_client()
    results: list[TagResult] = []
    for tag_gid in tag_gids:
        tag = client.tasks.add_tag(task_gid, tag_gid)
        results.append(tag)
    return results

