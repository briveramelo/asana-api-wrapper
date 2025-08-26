import json
from pathlib import Path
import typer

from src.core.config import get_settings
from src.core.wrapper import create_project_from_json, create_tasks_in_project
from src.core.asana_mapping_generator import generate_asana_mapping
from src.web.openapi_exporter import export_openapi_yaml
from src.core.models import ProjectSpec, TaskSpec

app = typer.Typer(add_completion=False, help="Provision Asana objects from JSON")


def _load_json(path: Path):
    """Load JSON data from a file path."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@app.command("create-project")
def create_project(
    file_path: Path = typer.Option(
        ..., exists=True, readable=True, help="Path to project spec JSON"
    ),
) -> None:
    """Create an Asana project from a specification file."""
    spec_data = _load_json(file_path)
    project_spec = ProjectSpec.model_validate(spec_data)
    project_result = create_project_from_json(project_spec)
    project_record = project_result.project
    typer.echo(f"Created project: {project_record.name} (gid={project_record.gid})")
    if project_result.sections:
        typer.echo(f"  Sections: {[section.name for section in project_result.sections]}")
    if project_result.tasks:
        typer.echo(f"  Tasks created: {len(project_result.tasks)}")


@app.command("add-tasks")
def add_tasks(
    project_gid: str = typer.Option(
        ..., "--project", "-p", help="Target project GID"
    ),
    file_path: Path = typer.Option(
        ..., exists=True, readable=True, help="Path to tasks JSON list"
    ),
) -> None:
    """Add tasks to a project using a JSON list."""
    task_data = _load_json(file_path)
    task_specs = [TaskSpec.model_validate(task) for task in task_data]
    created_tasks = create_tasks_in_project(
        project_gid=project_gid, task_specs=task_specs
    )
    typer.echo(f"Created {len(created_tasks)} tasks in project {project_gid}")


@app.command("generate-mapping")
def generate_mapping(
    output_path: Path = typer.Option("asana_mapping.json", help="Output JSON file path."),
) -> None:
    """Generate an identifier mapping and write it to disk."""
    settings = get_settings()
    mapping_result = generate_asana_mapping(
        workspace_gid=settings.workspace_gid,
        projects=[settings.project_gid],
    )
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(mapping_result.model_dump(), file, indent=2, ensure_ascii=False, sort_keys=True)
    typer.echo(f"Wrote mapping to {output_path}")


@app.command("export-openapi")
def export_openapi(
    output_path: Path = typer.Option(
        "llm_tools_openapi.yml", help="Output OpenAPI YAML file."
    ),
) -> None:
    """Export the OpenAPI schema to a YAML file."""
    export_openapi_yaml(output_path)
    typer.echo(f"Wrote OpenAPI schema to {output_path}")


if __name__ == "__main__":
    app()
