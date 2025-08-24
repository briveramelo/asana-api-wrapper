#!/usr/bin/env python3
"""
Generate a hard-coded Asana "Rosetta Stone" mapping for LLM use.

Example:
    python generate_asana_mapping.py \
        --workspace-gid 1200... \
        --project "Asana API Test" \
        --out asana_mapping.json
"""

from __future__ import annotations
import argparse
import json
import logging

from client import get_client 
from config import get_settings

logger = logging.getLogger("asana-mapper")
logging.basicConfig(level=logging.INFO)

def _index_by_name_thin(items: list[dict]) -> dict[str, str]:
    """
    Build a {name: gid} map. If duplicates exist, we keep the first and log a warning.
    """
    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    for it in items:
        name = (it.get("name") or "").strip()
        gid = it.get("gid")
        if not name or not gid:
            continue
        if name in out:
            seen[name] = seen.get(name, 1) + 1
            if seen[name] == 2:
                logger.warning("Duplicate name encountered; keeping first mapping for: %r", name)
            continue
        out[name] = gid
    return out

def _collect_sections(client, project_gid: str) -> dict[str, str]:
    sections = client.sections.list_for_project(project_gid)
    return _index_by_name_thin(sections)

def _collect_custom_fields_for_project(client, project_gid: str) -> dict[str, any]:
    """
    Returns:
    {
      "Priority": {
        "field_gid": "...",
        "resource_subtype": "enum",
        "options": {"High": "...", "Medium": "..."}
      },
      ...
    }
    """
    # Ask for nested field details up front; if not all details are present, fall back to /custom_fields/{gid}
    opt = "custom_field.name,custom_field.resource_subtype,custom_field.enum_options.name,custom_field.enum_options.gid"
    settings = client.custom_field_settings.list_for_project(project_gid, opt_fields=opt)

    by_name: dict[str, any] = {}
    for s in settings:
        cf = s.get("custom_field") or {}
        name = (cf.get("name") or "").strip()
        if not name:
            continue
        field_gid = cf.get("gid")
        resource_subtype = cf.get("resource_subtype")
        options_map: dict[str, str] = {}

        # Prefer enum options from the expanded response if present
        enum_opts = cf.get("enum_options") or []
        if not enum_opts and resource_subtype in ("enum", "multi_enum"):
            # Fallback: fetch the field to get options
            cf_full = client.custom_fields.get(field_gid, opt_fields="name,resource_subtype,enum_options.name,enum_options.gid")
            enum_opts = (cf_full or {}).get("enum_options") or []

        for opt in enum_opts:
            oname = (opt.get("name") or "").strip()
            ogid = opt.get("gid")
            if oname and ogid:
                options_map[oname] = ogid

        by_name[name] = {
            "field_gid": field_gid,
            "resource_subtype": resource_subtype,
            "options": options_map or None
        }
    return by_name

def _collect_users(client, workspace_gid: str) -> dict[str, str]:
    users = client.users.list_for_workspace(workspace_gid)
    return _index_by_name_thin(users)

def _collect_tags(client, workspace_gid: str) -> dict[str, str]:
    tags = client.tags.list_for_workspace(workspace_gid)
    return _index_by_name_thin(tags)

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a static Asana mapping file for LLMs.")
    ap.add_argument("--workspace-gid", help="Workspace GID. If omitted, uses settings.default_workspace_gid.")
    ap.add_argument("--project", action="append", dest="projects", help="Project name to include (repeatable). If omitted, includes ALL projects in the workspace.")
    ap.add_argument("--out", default="asana_mapping.json", help="Output JSON file path.")
    args = ap.parse_args()

    client = get_client()
    settings = get_settings()

    workspace_gid = args.workspace_gid or getattr(settings, "default_workspace_gid", None)
    if not workspace_gid:
        raise SystemExit("You must pass --workspace-gid or set settings.default_workspace_gid")

    # Fetch all projects in workspace (name + gid)
    all_projects = client.projects.list_for_workspace(workspace_gid, opt_fields="name")
    projects_by_name = _index_by_name_thin(all_projects)

    # Decide which projects to include
    if args.projects:
        missing = [p for p in args.projects if p not in projects_by_name]
        if missing:
            logger.warning("These project names were not found in workspace %s: %s", workspace_gid, missing)
        chosen = {p: projects_by_name[p] for p in args.projects if p in projects_by_name}
    else:
        chosen = projects_by_name

    # Build the mapping
    mapping: dict[str, any] = {
        "projects": chosen,               # {project_name: gid}
        "sections": {},                   # {project_name: {section_name: gid}}
        "custom_fields": {},              # {project_name: {field_name: {...}}}
        "tags": _collect_tags(client, workspace_gid),   # {tag_name: gid}
        "users": _collect_users(client, workspace_gid), # {user_name: gid}
    }

    for proj_name, proj_gid in chosen.items():
        mapping["sections"][proj_name] = _collect_sections(client, proj_gid)
        mapping["custom_fields"][proj_name] = _collect_custom_fields_for_project(client, proj_gid)

    # Persist to disk
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False, sort_keys=True)

    logger.info("Wrote %s with projects=%d, users=%d, tags=%d",
                args.out, len(chosen), len(mapping["users"]), len(mapping["tags"]))

if __name__ == "__main__":
    main()