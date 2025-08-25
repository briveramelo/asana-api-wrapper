import logging
from typing import Optional

from src.core.HttpClient import HttpClient, with_backoff
from src.core.config import get_settings

logger = logging.getLogger(__name__)


def get_client() -> any:
    """Return a minimal Asana client compatible with the legacy SDK-style usage.

    Keeps the same attribute names/methods you referenced:
      - client.projects.create(payload)
      - client.sections.create_section_for_project(project_gid, payload)
      - client.sections.get_sections_for_project(project_gid)
      - client.tasks.create(payload)

    Also provides: client.provision(blueprint) to apply your full JSON tree.

    Configuration is read from get_settings(), which should expose:
      - access_token (required)
      - log_level (optional, e.g., "INFO")
      - default_workspace_gid (optional) or default_team_gid (optional)
    """
    settings = get_settings()
    access_token = getattr(settings, "access_token", None)
    if not access_token:
        raise RuntimeError("Missing settings.access_token for Asana API.")

    logging.basicConfig(level=getattr(logging, getattr(settings, "log_level", "INFO").upper(), logging.INFO))
    http = HttpClient(access_token)

    # ---------- Proxies that mimic the classic SDK surface ----------

    class WorkspacesProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

    def list(self) -> list[dict]:
        # GET /workspaces
        return self._http.request_paginated("GET", "/workspaces")

    class UsersProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def list_for_workspace(self, workspace_gid: str) -> list[dict]:
            # GET /workspaces/{workspace_gid}/users
            path = f"/workspaces/{workspace_gid}/users"
            return self._http.request_paginated("GET", path)

    class TagsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def list_for_workspace(self, workspace_gid: str) -> list[dict]:
            # GET /workspaces/{workspace_gid}/tags
            path = f"/workspaces/{workspace_gid}/tags"
            return self._http.request_paginated("GET", path)

    class ProjectsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> dict:
            # Accept flattened or {"data": {...}}
            body = _wrap_data(_normalize_project_payload(payload, settings))
            return with_backoff(self._http.request, "POST", "/projects", json=body)

        def list_for_workspace(self, workspace_gid: str, *, opt_fields: Optional[str] = None) -> list[dict]:
            # GET /workspaces/{workspace_gid}/projects
            params = {"opt_fields": opt_fields} if opt_fields else None
            path = f"/workspaces/{workspace_gid}/projects"
            return self._http.request_paginated("GET", path, params=params)

    class SectionsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create_section_for_project(self, project_gid: str, payload: dict) -> dict:
            body = _wrap_data(payload)
            path = f"/projects/{project_gid}/sections"
            return with_backoff(self._http.request, "POST", path, json=body)

        # Backwards compatible alias
        def create_in_project(self, project_gid: str, payload: dict) -> dict:
            return self.create_section_for_project(project_gid, payload)

        def get_sections_for_project(self, project_gid: str) -> list[dict]:
            path = f"/projects/{project_gid}/sections"
            return with_backoff(self._http.request, "GET", path)

        def find_by_project(self, project_gid: str) -> list[dict]:
            return self.get_sections_for_project(project_gid)

        def list_for_project(self, project_gid: str) -> list[dict]:
            # GET /projects/{project_gid}/sections
            path = f"/projects/{project_gid}/sections"
            return self._http.request_paginated("GET", path)

    class TasksProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> dict:
            body = _wrap_data(payload)
            return with_backoff(self._http.request, "POST", "/tasks", json=body)

        def create_subtask(self, parent_task_gid: str, payload: dict) -> dict:
            body = _wrap_data(payload)
            path = f"/tasks/{parent_task_gid}/subtasks"
            return with_backoff(self._http.request, "POST", path, json=body)

    class CustomFieldSettingsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def list_for_project(self, project_gid: str, *, opt_fields: Optional[str] = None) -> list[dict]:
            # GET /projects/{project_gid}/custom_field_settings
            params = {"opt_fields": opt_fields} if opt_fields else None
            path = f"/projects/{project_gid}/custom_field_settings"
            return self._http.request_paginated("GET", path, params=params)

        def add_to_project(self, project_gid: str, custom_field_gid: str) -> dict:
            # POST /projects/{project_gid}/addCustomFieldSetting
            body = _wrap_data({"custom_field": custom_field_gid})
            path = f"/projects/{project_gid}/addCustomFieldSetting"
            return with_backoff(self._http.request, "POST", path, json=body)

    class CustomFieldsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> dict:
            # POST /custom_fields
            body = _wrap_data(payload)
            return with_backoff(self._http.request, "POST", "/custom_fields", json=body)

        def get(self, custom_field_gid: str, *, opt_fields: Optional[str] = None) -> dict:
            # GET /custom_fields/{gid}
            params = {"opt_fields": opt_fields} if opt_fields else None
            path = f"/custom_fields/{custom_field_gid}"
            return with_backoff(self._http.request, "GET", path, params=params)

    class ClientWrapper:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client
            self.projects = ProjectsProxy(http_client)
            self.sections = SectionsProxy(http_client)
            self.tasks = TasksProxy(http_client)
            self.workspaces = WorkspacesProxy(http_client)
            self.users = UsersProxy(http_client)
            self.tags = TagsProxy(http_client)
            self.custom_field_settings = CustomFieldSettingsProxy(http_client)
            self.custom_fields = CustomFieldsProxy(http_client)

        # High-level convenience to satisfy "just pass this JSON and have it created"
        def provision(self, blueprint: dict) -> dict:
            """Create a full project tree from a dict of the form shown in the prompt.

            Returns a summary with created Global IDs (GIDs).
            """
            # ---- 1) Project ----
            project_payload = dict(blueprint.get("project", {}))
            project = self.projects.create(project_payload)
            project_gid = project["gid"]

            # ---- 2) Sections ----
            section_name_to_gid: dict[str, str] = {}
            for s in blueprint.get("sections", []):
                name = s["name"]
                created = self.sections.create_section_for_project(project_gid, {"name": name})
                section_name_to_gid[name] = created["gid"]

            # ---- 3) Tasks ----
            created_tasks: list[dict] = []
            for t in blueprint.get("tasks", []):
                # Build memberships to drop the task in the desired section immediately
                memberships = []
                section_name = t.get("section_name")
                if section_name:
                    section_gid = section_name_to_gid.get(section_name)
                    if not section_gid:
                        raise ValueError(f"Section '{section_name}' not found in created sections.")
                    memberships.append({"project": project_gid, "section": section_gid})
                else:
                    # At minimum, associate the task with the project
                    memberships.append({"project": project_gid})

                task_payload = {
                    k: v
                    for k, v in t.items()
                    if k
                       not in {
                           "section_name",
                           "subtasks",
                       }
                }
                task_payload["memberships"] = memberships

                # Optional: ensure 'projects' set for legacy behavior
                task_payload.setdefault("projects", [project_gid])

                task = self.tasks.create(task_payload)
                created_tasks.append(task)

                # ---- 3a) Subtasks ----
                for st in t.get("subtasks", []):
                    subtask_payload = {k: v for k, v in st.items()}
                    # Inherit the project through the parent automatically; no need to set memberships.
                    self.tasks.create_subtask(task["gid"], subtask_payload)

            return {
                "project": project,
                "sections": [{"name": k, "gid": v} for k, v in section_name_to_gid.items()],
                "tasks": created_tasks,
            }

    return ClientWrapper(http)

# -----------------------------
# Utility
# -----------------------------

def _normalize_project_payload(payload: dict, settings: any) -> dict:
    """Map friendly fields to Asana's expected project fields.

    - 'privacy': 'private'|'public' -> 'public': bool
    - inject workspace/team from settings if neither supplied
    """
    data = dict(payload.get("data", payload))

    # Map privacy -> public boolean
    privacy = data.pop("privacy", None)
    if privacy is not None:
        if isinstance(privacy, str):
            privacy = privacy.strip().lower()
            if privacy in ("private", "priv"):
                data["public"] = False
            elif privacy in ("public",):
                data["public"] = True
        elif isinstance(privacy, bool):
            data["public"] = privacy

    # Provide a default container (workspace or team) if caller did not
    has_workspace_or_team = any(k in data for k in ("workspace", "team"))
    if not has_workspace_or_team:
        default_team = getattr(settings, "default_team_gid", None)
        default_workspace = getattr(settings, "default_workspace_gid", None)
        if default_team:
            data["team"] = default_team
        elif default_workspace:
            data["workspace"] = default_workspace
        else:
            # Asana requires one of these to create a project
            raise RuntimeError(
                "Project payload needs 'team' or 'workspace'. "
                "Provide one in the payload or configure default_team_gid/default_workspace_gid in settings."
            )

    return data


def _wrap_data(payload: dict) -> dict:
    """Accept both {'data': {...}} and flattened {...}; always return {'data': {...}}."""
    return payload if "data" in payload else {"data": payload}