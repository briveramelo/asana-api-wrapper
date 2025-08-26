#!/usr/bin/env python3
"""
Generate a hard-coded Asana "Rosetta Stone" mapping for LLM use.

Example:
    python main.py generate-mapping \
        --workspace-gid 1200... \
        --project "Asana API Test" \
        --out asana_mapping.json
"""

import logging

from src.core.asana_client import get_client
from src.core.config import get_settings
from src.core.models import CustomFieldInfo, MappingResult, ProjectRecord

logger = logging.getLogger("asana-mapper")
logging.basicConfig(level=logging.INFO)

def _index_by_name_thin(items: list[ProjectRecord]) -> dict[str, str]:
    """Build a mapping from item name to its GID, logging duplicate names."""
    mapping: dict[str, str] = {}
    duplicate_counts: dict[str, int] = {}
    for item in items:
        name = (item.name or "").strip()
        gid = item.gid
        if not name or not gid:
            continue
        if name in mapping:
            duplicate_counts[name] = duplicate_counts.get(name, 1) + 1
            if duplicate_counts[name] == 2:
                logger.warning("Duplicate name encountered; keeping first mapping for: %r", name)
            continue
        mapping[name] = gid
    return mapping

def _collect_sections(client, project_gid: str) -> dict[str, str]:
    """Return a mapping of section name to GID for the given project."""
    section_items = client.sections.list_for_project(project_gid)
    return _index_by_name_thin(section_items)

def _collect_custom_fields_for_project(client, project_gid: str) -> dict[str, CustomFieldInfo]:
    """Gather custom field metadata for a project keyed by field name."""
    option_fields = (
        "custom_field.name,custom_field.resource_subtype,"
        "custom_field.enum_options.name,custom_field.enum_options.gid"
    )
    field_settings = client.custom_field_settings.list_for_project(
        project_gid, opt_fields=option_fields
    )

    fields_by_name: dict[str, CustomFieldInfo] = {}
    for setting in field_settings:
        field_data = setting.get("custom_field") or {}
        field_name = (field_data.get("name") or "").strip()
        if not field_name:
            continue
        field_gid = field_data.get("gid")
        resource_subtype = field_data.get("resource_subtype")
        option_map: dict[str, str] = {}

        enum_options = field_data.get("enum_options") or []
        if not enum_options and resource_subtype in ("enum", "multi_enum"):
            field_details = client.custom_fields.get(
                field_gid,
                opt_fields="name,resource_subtype,enum_options.name,enum_options.gid",
            )
            enum_options = (field_details or {}).get("enum_options") or []

        for option in enum_options:
            option_name = (option.get("name") or "").strip()
            option_gid = option.get("gid")
            if option_name and option_gid:
                option_map[option_name] = option_gid

        fields_by_name[field_name] = CustomFieldInfo(
            field_gid=field_gid,
            resource_subtype=resource_subtype,
            options=option_map or None,
        )
    return fields_by_name

def _collect_users(client, workspace_gid: str) -> dict[str, str]:
    """Return a mapping of username to GID for the workspace."""
    user_items = client.users.list_for_workspace(workspace_gid)
    return _index_by_name_thin(user_items)

def _collect_tags(client, workspace_gid: str) -> dict[str, str]:
    """Return a mapping of tag name to GID for the workspace."""
    tag_items = client.tags.list_for_workspace(workspace_gid)
    return _index_by_name_thin(tag_items)

def generate_asana_mapping(
    workspace_gid: str | None = None,
    projects: list[str] | None = None,
) -> MappingResult:
    """Generate a lightweight mapping of Asana identifiers."""
    client = get_client()
    settings = get_settings()

    workspace_gid = workspace_gid or getattr(settings, "default_workspace_gid", None)
    if not workspace_gid:
        raise SystemExit("You must pass --workspace-gid or set settings.default_workspace_gid")

    all_projects = client.projects.list_for_workspace(workspace_gid, opt_fields="name")
    projects_by_name = _index_by_name_thin(all_projects)

    if projects and len(projects) > 1 and projects[0]:
        missing = [name for name in projects if name not in projects_by_name]
        if missing:
            logger.warning(
                "These project names were not found in workspace %s: %s",
                workspace_gid,
                missing,
            )
        selected_projects = {
            name: projects_by_name[name] for name in projects if name in projects_by_name
        }
    else:
        selected_projects = projects_by_name

    mapping_result = MappingResult(
        projects=selected_projects,
        sections={},
        custom_fields={},
        tags=_collect_tags(client, workspace_gid),
        users=_collect_users(client, workspace_gid),
    )

    for project_name, project_gid in selected_projects.items():
        mapping_result.sections[project_name] = _collect_sections(client, project_gid)
        mapping_result.custom_fields[project_name] = _collect_custom_fields_for_project(
            client, project_gid
        )

    logger.info(
        "Generated mapping with projects=%d, users=%d, tags=%d",
        len(selected_projects),
        len(mapping_result.users),
        len(mapping_result.tags),
    )

    return mapping_result

