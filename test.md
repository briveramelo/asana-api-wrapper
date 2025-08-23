asana-json-provisioner

A tiny, JSON-driven wrapper for provisioning Asana projects and tasks with all constants (auth, workspace, team) set in your codebase.

Supports:
	•	Create a project from a single JSON spec (and then add tasks to it)
	•	Add tasks to an existing project from JSON
	•	Optional sections by GID (with best-effort name support)
	•	Subtasks (recursive), due dates, notes, followers, tags, and custom fields
	•	Basic retry/backoff for Asana rate limits

Requires Python 3.9+

⸻

Repository Layout

.
├── README.md
├── pyproject.toml
├── LICENSE
├── .env.example
├── examples
│   ├── project_with_tasks.json
│   └── tasks_only.json
└── src
    └── asana_json_provisioner
        ├── __init__.py
        ├── client.py
        ├── config.py
        ├── models.py
        ├── wrapper.py
        └── cli.py


⸻

README.md

# asana-json-provisioner

Provision Asana projects and tasks from plain JSON. You keep credentials and IDs in code (or .env), and hand the tool a single JSON object.

## Features
- Create projects via JSON (workspace/team handled in code)
- Add tasks to existing projects via JSON
- Subtasks (recursive), notes, due dates, followers, tags, custom fields
- Optional placement into sections (by GID, or best-effort by name)
- CLI + Python API

## Install

```bash
pip install -e .

Alternatively, install into a virtualenv/poetry as you prefer. The only hard dependency is the official asana client.

Configure

Copy and edit .env.example to .env:

ASANA_ACCESS_TOKEN=your_personal_access_token
WORKSPACE_GID=your_workspace_gid
TEAM_GID=your_team_gid

Create a Personal Access Token in Asana: https://app.asana.com/0/my-apps

You can also set these variables through your process manager or secrets manager (recommended for production).

JSON Schemas (informal)

Project spec (for project creation)

{
  "project": {
    "name": "New Marketing Campaign",
    "notes": "Optional project description",
    "privacy": "private"    
  },
  "tasks": [
    {
      "name": "Kickoff Meeting",
      "notes": "Agenda attached",
      "assignee": "12001234567890",           
      "due_on": "2025-09-01",                 
      "followers": ["1200...", "1201..."],  
      "tags": ["1200..."],                    
      "custom_fields": {"123456": "High"},  
      "section": "1200SECTIONGID",           
      "subtasks": [
        { "name": "Book room" },
        { "name": "Invite stakeholders" }
      ]
    }
  ],
  "sections": [
    { "name": "Backlog" },
    { "name": "In Progress" },
    { "name": "Done" }
  ]
}

Tasks-only spec (for adding tasks to an existing project)

[
  { "name": "Write Press Release", "notes": "Draft v1", "section": "1200SECTIONGID" },
  { "name": "Design Assets", "assignee": "1200USERGID" },
  { "name": "Schedule Social", "due_on": "2025-09-15" }
]

Notes:
	•	assignee, tags, followers, custom_fields, and section expect GIDs. Name lookups are possible but less reliable; see README for details.
	•	Use due_on for date (YYYY-MM-DD) or due_at for timestamp (RFC 3339).
	•	Subtasks may include the same properties as tasks (except section).

CLI Usage

Create a project from JSON (and optionally create sections + tasks):

provision create-project --file examples/project_with_tasks.json

Add tasks to an existing project:

provision add-tasks --project 120987654321 --file examples/tasks_only.json

Python Usage

from asana_json_provisioner.wrapper import create_project_from_json, create_tasks_in_project

project_spec = ...  # dict loaded from JSON
result = create_project_from_json(project_spec)
print(result["project"]["gid"])  # new project id

created = create_tasks_in_project("120987654321", tasks_spec=[{"name": "Hello"}])

Links (official docs)
	•	Asana REST API overview: https://developers.asana.com/docs
	•	Create a task: https://developers.asana.com/reference/tasks#create-a-task
	•	Create a project: https://developers.asana.com/reference/projects#create-a-project
	•	Sections: https://developers.asana.com/reference/sections
	•	Rate limits: https://developers.asana.com/docs/rate-limits

License

MIT. See LICENSE.




⸻

pyproject.toml

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "asana-json-provisioner"
version = "0.1.0"
description = "Provision Asana projects and tasks from JSON"
authors = [{ name = "Your Name" }]
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
  "asana>=3.2.1",
  "python-dotenv>=1.0.1",
]

[project.scripts]
provision = "asana_json_provisioner.cli:app"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]


⸻

LICENSE

MIT License

Copyright (c) 2025 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


⸻

.env.example

# Required
ASANA_ACCESS_TOKEN=replace_me
WORKSPACE_GID=replace_me
TEAM_GID=replace_me

# Optional
# LOG_LEVEL=INFO


⸻

examples/project_with_tasks.json

{
  "project": {
    "name": "New Marketing Campaign",
    "notes": "Q4 launch plan",
    "privacy": "private"
  },
  "sections": [
    { "name": "Backlog" },
    { "name": "In Progress" },
    { "name": "Done" }
  ],
  "tasks": [
    {
      "name": "Kickoff Meeting",
      "notes": "Agenda attached",
      "assignee": "12001234567890",
      "due_on": "2025-09-01",
      "followers": ["1200123", "1200456"],
      "tags": ["1200789"],
      "custom_fields": { "123456": "High" },
      "section_name": "Backlog",
      "subtasks": [
        { "name": "Book room" },
        { "name": "Invite stakeholders" }
      ]
    },
    {
      "name": "Design Assets",
      "notes": "Hero image + variants",
      "section_name": "In Progress"
    }
  ]
}


⸻

examples/tasks_only.json

[
  { "name": "Write Press Release", "notes": "Draft v1", "section": "1200SECTIONGID" },
  { "name": "Design Assets", "assignee": "1200USERGID" },
  { "name": "Schedule Social", "due_on": "2025-09-15" }
]


⸻

src/asana_json_provisioner/init.py

__all__ = [
    "get_client",
    "create_project_from_json",
    "create_tasks_in_project",
]

from .client import get_client
from .wrapper import create_project_from_json, create_tasks_in_project


⸻

src/asana_json_provisioner/config.py

from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    access_token: str
    workspace_gid: str
    team_gid: str
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


def get_settings() -> Settings:
    token = os.getenv("ASANA_ACCESS_TOKEN")
    workspace = os.getenv("WORKSPACE_GID")
    team = os.getenv("TEAM_GID")

    missing = [k for k, v in {
        "ASANA_ACCESS_TOKEN": token,
        "WORKSPACE_GID": workspace,
        "TEAM_GID": team,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Settings(access_token=token, workspace_gid=workspace, team_gid=team)


⸻

src/asana_json_provisioner/client.py

from __future__ import annotations
import time
import logging
from typing import Callable, Any
import asana
from .config import get_settings

logger = logging.getLogger(__name__)


def get_client() -> asana.Client:
    settings = get_settings()
    client = asana.Client.access_token(settings.access_token)
    client.options["headers"] = {
        **client.options.get("headers", {}),
        "User-Agent": "asana-json-provisioner/0.1.0",
    }
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    return client


def _with_backoff(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Run an Asana SDK call with simple 429 backoff."""
    max_attempts = 5
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # Broad to avoid tight coupling to SDK exceptions
            # Try to detect 429 and Retry-After
            retry_after = None
            status = getattr(getattr(e, "response", None), "status", None) or getattr(e, "status", None)
            headers = getattr(getattr(e, "response", None), "headers", None) or getattr(e, "headers", {})
            if isinstance(headers, dict):
                retry_after = headers.get("Retry-After")

            if str(status) == "429" or retry_after:
                sleep_for = float(retry_after) if retry_after else delay
                logger.warning("Rate limit hit (attempt %s/%s). Sleeping for %.2fs...", attempt, max_attempts, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 8)
                continue
            logger.error("Asana API error: %s", e)
            raise
    raise RuntimeError("Exceeded max retry attempts for Asana API call")


⸻

src/asana_json_provisioner/models.py

from __future__ import annotations
from typing import Dict, List, Optional, Any, TypedDict

class SectionSpec(TypedDict, total=False):
    name: str

class TaskSpec(TypedDict, total=False):
    name: str
    notes: str
    assignee: str              # GID
    due_on: str                # YYYY-MM-DD
    due_at: str                # RFC3339 timestamp
    followers: List[str]
    tags: List[str]
    custom_fields: Dict[str, Any]
    section: str               # section GID
    section_name: str          # fallback by name (best-effort)
    subtasks: List["TaskSpec"]

class ProjectMeta(TypedDict, total=False):
    name: str
    notes: str
    privacy: str               # "private" | "public_to_team" etc.

class ProjectSpec(TypedDict, total=False):
    project: ProjectMeta
    sections: List[SectionSpec]
    tasks: List[TaskSpec]


⸻

src/asana_json_provisioner/wrapper.py

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


⸻

src/asana_json_provisioner/cli.py

from __future__ import annotations
import json
from pathlib import Path
import typer
from .wrapper import create_project_from_json, create_tasks_in_project

app = typer.Typer(add_completion=False, help="Provision Asana objects from JSON")


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.command("create-project")
def create_project(file: Path = typer.Option(..., exists=True, readable=True, help="Path to project spec JSON")):
    spec = _load_json(file)
    result = create_project_from_json(spec)
    proj = result["project"]
    typer.echo(f"Created project: {proj['name']} (gid={proj['gid']})")
    if result.get("sections"):
        typer.echo(f"  Sections: {[s['name'] for s in result['sections']]}")
    if result.get("tasks"):
        typer.echo(f"  Tasks created: {len(result['tasks'])}")


@app.command("add-tasks")
def add_tasks(
    project: str = typer.Option(..., "--project", "-p", help="Target project GID"),
    file: Path = typer.Option(..., exists=True, readable=True, help="Path to tasks JSON list"),
):
    tasks_spec = _load_json(file)
    created = create_tasks_in_project(project_gid=project, tasks_spec=tasks_spec)
    typer.echo(f"Created {len(created)} tasks in project {project}")


if __name__ == "__main__":
    app()


⸻

Notes & Tips
	•	GIDs vs. names: Prefer GIDs for assignee, section, tags, followers, and custom field IDs. Name lookups vary across SDK versions and organizations.
	•	Rate limits: This repo implements a simple exponential backoff honoring Retry-After where provided. For heavy use, consider queueing and idempotency keys.
	•	Security: Do not commit real tokens. Use your secret manager in production.
	•	Testing: You can dry-run by printing payloads before calling the client.

