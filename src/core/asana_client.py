import logging
from typing import Optional

from src.core.HttpClient import HttpClient, with_backoff
from src.core.config import get_settings
from src.core.models import ProjectRecord, ProjectResult, SectionResult, TagResult, TaskResult

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

        def list_for_workspace(self, workspace_gid: str) -> list[TagResult]:
            # GET /workspaces/{workspace_gid}/tags
            path = f"/workspaces/{workspace_gid}/tags"
            items = self._http.request_paginated("GET", path)
            return [TagResult.model_validate(item) for item in items]

        def create(self, payload: dict) -> TagResult:
            # POST /tags
            body = _wrap_data(payload)
            result = with_backoff(self._http.request, "POST", "/tags", json=body)
            return TagResult.model_validate(result)

    class ProjectsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> ProjectRecord:
            # Accept flattened or {"data": {...}}
            body = _wrap_data(_normalize_project_payload(payload, settings))
            result = with_backoff(self._http.request, "POST", "/projects", json=body)
            return ProjectRecord.model_validate(result)

        def list_for_workspace(self, workspace_gid: str, *, opt_fields: Optional[str] = None) -> list[ProjectRecord]:
            # GET /workspaces/{workspace_gid}/projects
            params = {"opt_fields": opt_fields} if opt_fields else None
            path = f"/workspaces/{workspace_gid}/projects"
            items = self._http.request_paginated("GET", path, params=params)
            return [ProjectRecord.model_validate(item) for item in items]

    class SectionsProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create_section_for_project(self, project_gid: str, payload: dict) -> SectionResult:
            body = _wrap_data(payload)
            path = f"/projects/{project_gid}/sections"
            result = with_backoff(self._http.request, "POST", path, json=body)
            return SectionResult.model_validate(result)

        # Backwards compatible alias
        def create_in_project(self, project_gid: str, payload: dict) -> SectionResult:
            return self.create_section_for_project(project_gid, payload)

        def get_sections_for_project(self, project_gid: str) -> list[SectionResult]:
            path = f"/projects/{project_gid}/sections"
            items = with_backoff(self._http.request, "GET", path)
            return [SectionResult.model_validate(item) for item in items]

        def find_by_project(self, project_gid: str) -> list[SectionResult]:
            return self.get_sections_for_project(project_gid)

        def list_for_project(self, project_gid: str) -> list[SectionResult]:
            # GET /projects/{project_gid}/sections
            path = f"/projects/{project_gid}/sections"
            items = self._http.request_paginated("GET", path)
            return [SectionResult.model_validate(item) for item in items]

    class TasksProxy:
        def __init__(self, http_client: HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> TaskResult:
            body = _wrap_data(payload)
            result = with_backoff(self._http.request, "POST", "/tasks", json=body)
            return TaskResult.model_validate(result)

        def create_subtask(self, parent_task_gid: str, payload: dict) -> TaskResult:
            body = _wrap_data(payload)
            path = f"/tasks/{parent_task_gid}/subtasks"
            result = with_backoff(self._http.request, "POST", path, json=body)
            return TaskResult.model_validate(result)

        def add_tag(self, task_gid: str, tag_gid: str) -> TagResult:
            # POST /tasks/{task_gid}/addTag
            body = _wrap_data({"tag": tag_gid})
            path = f"/tasks/{task_gid}/addTag"
            result = with_backoff(self._http.request, "POST", path, json=body)
            return TagResult.model_validate(result)

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
        def provision(self, blueprint: dict) -> ProjectResult:
            """Create a full project tree from a dict of the form shown in the prompt.

            Returns a summary with created Global IDs (GIDs).
            """
            project_payload = dict(blueprint.get("project", {}))
            project = self.projects.create(project_payload)
            project_gid = project.gid

            section_name_to_gid: dict[str, str] = {}
            created_sections: list[SectionResult] = []
            for section_spec in blueprint.get("sections", []):
                name = section_spec["name"]
                created_section = self.sections.create_section_for_project(project_gid, {"name": name})
                created_sections.append(created_section)
                section_name_to_gid[name] = created_section.gid

            created_tasks: list[TaskResult] = []
            for task_spec in blueprint.get("tasks", []):
                memberships = []
                section_name = task_spec.get("section_name")
                if section_name:
                    section_gid = section_name_to_gid.get(section_name)
                    if not section_gid:
                        raise ValueError(f"Section '{section_name}' not found in created sections.")
                    memberships.append({"project": project_gid, "section": section_gid})
                else:
                    memberships.append({"project": project_gid})

                task_payload = {
                    key: value
                    for key, value in task_spec.items()
                    if key not in {"section_name", "subtasks"}
                }
                task_payload["memberships"] = memberships
                task_payload.setdefault("projects", [project_gid])

                task = self.tasks.create(task_payload)
                created_tasks.append(task)

                for subtask_spec in task_spec.get("subtasks", []):
                    subtask_payload = {key: value for key, value in subtask_spec.items()}
                    self.tasks.create_subtask(task.gid, subtask_payload)

            return ProjectResult(project=project, sections=created_sections, tasks=created_tasks)

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