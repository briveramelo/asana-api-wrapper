"""Utilities to export OpenAPI schema for llm_tools endpoints."""

from pathlib import Path

from fastapi import FastAPI
import yaml

from src.web.endpoints import router


def export_openapi_yaml(out: Path) -> Path:
    """Generate and write the OpenAPI schema for llm_tools.

    Parameters
    ----------
    out : Path
        Destination file path.

    Returns
    -------
    Path
        The path to the written file.
    """
    app = FastAPI()
    app.include_router(router)
    schema = app.openapi()
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(schema, f, sort_keys=False)
    return out
