# asana-json-provisioner

Provision **Asana projects** and **tasks** from plain JSON. Keep credentials and IDs in code or environment variables, hand this tool a JSON spec, and it will create projects, sections, tasks, and subtasks for you.

---

## Features

- Create **projects** from a single JSON file
- Add **tasks** to an existing project from JSON
- Supports:
    - **Sections** (by GID, or best-effort by name)
    - **Subtasks** (recursive)
    - **Notes**, **due dates**, **assignees**
    - **Followers**, **tags**, **custom fields**
- CLI (`provision`) and Python API
- Simple exponential backoff for Asana **rate limits**

---

## Requirements

- Python **3.9+**
- An Asana **Personal Access Token (PAT)**
- Access to the target **workspace** and **team** (GIDs)

> Actions are attributed to the PAT’s user. For automation clarity, consider a dedicated “bot” account.

---

## Installation

Using **Poetry** (recommended):

```bash
git clone https://github.com/yourname/asana-json-provisioner.git
cd asana-json-provisioner
poetry install
```

> If the CLI complains about `typer` not being found, add it to your environment:
> `poetry add typer` (or add `typer>=0.12` to dependencies in `pyproject.toml`).

To run the CLI:

```bash
poetry run provision --help
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

---

## Quickstart

### 1) Create a project (and optional sections + tasks) from JSON

```bash
poetry run provision create-project --file examples/project_with_tasks.json
```

### 2) Add tasks to an existing project

```bash
poetry run provision add-tasks --project 120987654321 --file examples/tasks_only.json
```

> Prefer **GIDs** for users, sections, tags, and custom fields. Name-based lookups vary by org and SDK version and are best used as a fallback.

---

## How it works

- `config.py` loads required env vars and fails fast if missing.
- `client.py` constructs the Asana client and wraps SDK calls with a simple **429 backoff** (honoring `Retry-After` when present).
- `wrapper.py` builds payloads, creates projects, sections, tasks, and **recursive subtasks**, and supports section placement by **GID** or best-effort **name**.
- `cli.py` provides two commands via **Typer**:
    - `create-project --file <project.json>`
    - `add-tasks --project <PROJECT_GID> --file <tasks.json>`

---

## Auth notes

- Uses an **Asana Personal Access Token (PAT)** via `ASANA_ACCESS_TOKEN`.
- For multi-user apps or public distribution, switch to **OAuth 2.0** and request minimal scopes.
- Consider a dedicated “bot” PAT for clearer attribution in activity logs.

---

## Rate limits

Asana enforces API rate limits. This tool retries with exponential backoff and honors `Retry-After`. For very large imports, consider batching or queueing.

---

## Troubleshooting

- **401 Unauthorized**: Check `ASANA_ACCESS_TOKEN`. Try running a smoke test (`users.me`) if you add a verify step.
- **403 Forbidden**: The PAT’s user lacks access to the workspace/team/project.
- **404 Not Found**: A referenced **GID** (user, section, tag, custom field) is invalid or outside scope.
- **429 Too Many Requests**: The tool will back off and retry. Reduce concurrency or input size.

---

## License

MIT — see `LICENSE`.
