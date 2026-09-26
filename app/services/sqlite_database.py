import os
from pathlib import Path


DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "resumeiq.sqlite3"
)


def database_path() -> Path:
    return Path(
        os.getenv("RESUMEIQ_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
    ).expanduser()
