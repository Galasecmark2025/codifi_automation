# task_paths.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exchange_scraper_automation.data_paths import resolve_alias_data_path


@dataclass(frozen=True, slots=True)
class TaskPaths:
    download_dir: Path

    @classmethod
    def from_alias(cls, alias_name: str) -> TaskPaths:
        data_dir = resolve_alias_data_path(alias_name)
        data_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            download_dir=data_dir,
        )
