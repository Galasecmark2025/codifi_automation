"""Project data-directory constants and path resolution helpers."""

from __future__ import annotations

from pathlib import Path, logging

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "ExchangeData"

logger = logging.getLogger(__name__)


def resolve_data_path(configured_path: str | Path) -> Path:
    """Resolve configured local paths relative to the project's data directory."""
    raw_path = str(configured_path).strip()

    if not raw_path:
        logger.error("Configured data path cannot be empty.")

    path = Path(raw_path).expanduser()

    # Relative paths such as NSE/CM -> project/data/NSE/CM
    if not path.is_absolute():
        if path.parts and path.parts[0].lower() == "ExchangeData":
            return PROJECT_ROOT / path

        if path.parts and path.parts[0].lower() == "final_data":
            return DATA_ROOT.joinpath(*path.parts[1:])

        return DATA_ROOT / path

    # Keep paths already under the new data directory.
    try:
        path.relative_to(DATA_ROOT)
        return path
    except ValueError:
        pass

    # Support old absolute paths inside this project.
    try:
        project_relative_path = path.relative_to(PROJECT_ROOT)
    except ValueError:
        project_relative_path = None

    if project_relative_path is not None:
        parts = project_relative_path.parts

        if parts and parts[0].lower() == "ExchangeData":
            return path

        if parts and parts[0].lower() == "final_data":
            return DATA_ROOT.joinpath(*parts[1:])

    # Treat configured paths such as /NSE/CM and /data/MCX
    # as logical paths under the project's data directory.
    parts = path.parts[1:]

    if parts and parts[0].lower() in {"ExchangeData", "final_data"}:
        parts = parts[1:]

    return DATA_ROOT.joinpath(*parts)


from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "ExchangeData"


def resolve_alias_data_path(alias_name: str) -> Path:
    """Resolve the output directory using the first word of aliasname."""

    alias = str(alias_name).strip()

    if not alias:
        logger.error("Task aliasname cannot be empty.")

    # Use only the first word of the alias.
    folder_name = alias.split(maxsplit=1)[0]

    # Prevent invalid or unsafe directory names.
    if folder_name in {".", ".."} or "/" in folder_name or "\\" in folder_name:
        logger.error(f"Invalid task aliasname: {alias!r}")

    return DATA_ROOT / folder_name
