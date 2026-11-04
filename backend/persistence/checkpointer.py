
import os
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "checkpoints"
    / "incident_workflows.sqlite"
)


def get_database_path() -> Path:
    configured = os.getenv(
        "INCIDENT_CHECKPOINT_DB",
        str(DEFAULT_DB_PATH),
    )

    path = Path(configured)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def create_checkpointer():
    connection = await aiosqlite.connect(
        str(get_database_path())
    )

    checkpointer = AsyncSqliteSaver(connection)

    return checkpointer, connection
