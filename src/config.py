from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    access_token: str
    workspace_gid: str
    project_gid: str
    team_gid: str
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


def get_settings() -> Settings:
    token = os.getenv("ASANA_ACCESS_TOKEN")
    workspace = os.getenv("WORKSPACE_GID")
    project = os.getenv("PROJECT_GID")
    team = os.getenv("TEAM_GID")

    missing = [key for key, value in {
        "ASANA_ACCESS_TOKEN": token,
        "WORKSPACE_GID": workspace,
        # "PROJECT_GID": project,
        # "TEAM_GID": team,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Settings(access_token=token, workspace_gid=workspace, project_gid=project, team_gid=team)
