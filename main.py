import json
from pathlib import Path
import typer

from src.config import get_settings
from src.wrapper import create_project_from_json, create_tasks_in_project
from src.asana_mapping_generator import generate_asana_mapping

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


@app.command("generate-mapping")
def generate_mapping(
    out: Path = typer.Option("asana_mapping.json", help="Output JSON file path."),
):
    settings = get_settings()
    mapping = generate_asana_mapping(
        workspace_gid=settings.workspace_gid,
        projects=[settings.project_gid]
    )
    with out.open("w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False, sort_keys=True)
    typer.echo(f"Wrote mapping to {out}")


if __name__ == "__main__":
    app()
