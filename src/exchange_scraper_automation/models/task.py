from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from exchange_scraper_automation.observability.logger import Logger


@dataclass(frozen=True, slots=True)
class Task:
    task_id: int
    alias_name: str
    exchange_id: int
    master_type: str
    task_type: str
    filename_path: str | None
    status: str | None
    enabled: bool
    dependent_task_id: int | None
    details: dict[str, Any]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Task:
        """Convert a database row into a validated Task object."""

        task_type = str(row.get("tasktype")).strip().upper()

        # Insertion tasks use filenamepath and the mapping function,
        # not tasktypedetails.
        if task_type == "INSERTLOAD_DATA":
            details = {}
        else:
            raw_details = row.get("tasktypedetails")

            if isinstance(raw_details, str):
                try:
                    raw_details = json.loads(raw_details)
                except json.JSONDecodeError as error:
                    Logger.error(
                        f"Invalid tasktypedetails JSON: " f"TaskID={row.get('taskid')}"
                    )

            if not isinstance(raw_details, dict):
                Logger.error(
                    f"tasktypedetails must be a JSON object: "
                    f"TaskID={row.get('taskid')}"
                )

            details = raw_details

        required_fields = {
            "taskid": row.get("taskid"),
            "aliasname": row.get("aliasname"),
            "exchangeid": row.get("exchangeid"),
            "mastertype": row.get("mastertype"),
            "tasktype": task_type,
        }

        for field_name, value in required_fields.items():
            if value is None or not str(value).strip():
                Logger.error(f"Missing {field_name} in task row")

        return cls(
            task_id=int(row["taskid"]),
            alias_name=str(row["aliasname"]).strip(),
            exchange_id=int(row["exchangeid"]),
            master_type=str(row["mastertype"]).strip().upper(),
            task_type=task_type,
            filename_path=(
                str(row["filenamepath"]).strip() if row.get("filenamepath") else None
            ),
            status=row.get("status"),
            enabled=bool(row.get("enabled")),
            dependent_task_id=row.get("dependenttaskid"),
            details=details,
        )
