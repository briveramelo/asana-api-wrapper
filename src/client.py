from __future__ import annotations
import time
import logging
from typing import Callable, Any, Dict, List, Optional
import requests
from .config import get_settings

logger = logging.getLogger(__name__)

_ASANA_BASE_URL = "https://app.asana.com/api/1.0"
_USER_AGENT = "asana-json-provisioner/0.1.0"

# -----------------------------
# Low-level HTTP helpers
# -----------------------------

class _HttpClient:
    def __init__(self, access_token: str, default_timeout: float = 30.0) -> None:
        self.base = _ASANA_BASE_URL.rstrip("/")
        self.timeout = default_timeout
        self.sess = requests.Session()
        self.sess.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        })

    def request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        url = f"{self.base}/{path.lstrip('/')}"
        resp = self.sess.request(method, url, params=params, json=json, timeout=self.timeout)
        # Raise to trigger _with_backoff logic on 4xx/5xx (including 429)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Attach response for the backoff helper to inspect
            e.response = resp
            raise
        payload = resp.json() if resp.content else {}
        # Asana wraps everything in {'data': ...}
        return payload.get("data", payload)


def _wrap_data(payload: dict) -> dict:
    """Accept both {'data': {...}} and flattened {...}; always return {'data': {...}}."""
    return payload if "data" in payload else {"data": payload}


# -----------------------------
# Public drop-in: get_client()
# -----------------------------

def get_client() -> Any:
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
    http = _HttpClient(access_token)

    # ---------- Proxies that mimic the classic SDK surface ----------

    class ProjectsProxy:
        def __init__(self, http_client: _HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> dict:
            # Accept flattened or {"data": {...}}
            body = _wrap_data(_normalize_project_payload(payload, settings))
            return _with_backoff(self._http.request, "POST", "/projects", json=body)

    class SectionsProxy:
        def __init__(self, http_client: _HttpClient) -> None:
            self._http = http_client

        def create_section_for_project(self, project_gid: str, payload: dict) -> dict:
            body = _wrap_data(payload)
            path = f"/projects/{project_gid}/sections"
            return _with_backoff(self._http.request, "POST", path, json=body)

        # Backwards compatible alias
        def create_in_project(self, project_gid: str, payload: dict) -> dict:
            return self.create_section_for_project(project_gid, payload)

        def get_sections_for_project(self, project_gid: str) -> List[dict]:
            path = f"/projects/{project_gid}/sections"
            return _with_backoff(self._http.request, "GET", path)

        def find_by_project(self, project_gid: str) -> List[dict]:
            return self.get_sections_for_project(project_gid)

    class TasksProxy:
        def __init__(self, http_client: _HttpClient) -> None:
            self._http = http_client

        def create(self, payload: dict) -> dict:
            body = _wrap_data(payload)
            return _with_backoff(self._http.request, "POST", "/tasks", json=body)

        def create_subtask(self, parent_task_gid: str, payload: dict) -> dict:
            body = _wrap_data(payload)
            path = f"/tasks/{parent_task_gid}/subtasks"
            return _with_backoff(self._http.request, "POST", path, json=body)

    class ClientWrapper:
        def __init__(self, http_client: _HttpClient) -> None:
            self._http = http_client
            self.projects = ProjectsProxy(http_client)
            self.sections = SectionsProxy(http_client)
            self.tasks = TasksProxy(http_client)

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
            section_name_to_gid: Dict[str, str] = {}
            for s in blueprint.get("sections", []):
                name = s["name"]
                created = self.sections.create_section_for_project(project_gid, {"name": name})
                section_name_to_gid[name] = created["gid"]

            # ---- 3) Tasks ----
            created_tasks: List[dict] = []
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
# Retry / backoff identical signature
# -----------------------------

def _with_backoff(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Run an HTTP call with simple 429 (rate-limit) backoff using Retry-After if present."""
    max_attempts = 5
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # keep broad to avoid coupling to 'requests' types elsewhere
            resp = getattr(e, "response", None)
            headers = getattr(resp, "headers", {}) or {}
            status = (
                    getattr(resp, "status", None)
                    or getattr(resp, "status_code", None)
                    or getattr(e, "status", None)
            )
            retry_after = headers.get("Retry-After")
            if str(status) == "429" or retry_after:
                # Respect server-provided Retry-After seconds when available
                sleep_for = float(retry_after) if retry_after else delay
                logger.warning("Rate limit hit (attempt %s/%s). Sleeping for %.2fs...", attempt, max_attempts, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 8.0)
                continue
            # Surface other HTTP errors
            logger.error("Asana API error: %s", e)
            raise
    raise RuntimeError("Exceeded max retry attempts for Asana API call")


# -----------------------------
# Utility
# -----------------------------

def _normalize_project_payload(payload: dict, settings: Any) -> dict:
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