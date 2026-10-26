"""Typed, branch-tolerant configuration for BSE download tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from exchange_scraper_automation.observability.logger import Logger


@dataclass(frozen=True, slots=True)
class BSEReportConfig:
    """Known BSE config fields across standard UDiFF, SLBM, VAR, and direct URL tasks.

    Fields are optional because BSE task types use different subsets of the JSON
    configuration. The expected downloaded filename is deliberately not stored
    here; it comes from the task's database ``filenamepath`` column.
    """

    protocol: str | None = None
    file_type: str | None = None
    segment: str | None = None
    data_type: str | None = None
    url: str | None = None
    file_name: str | None = None
    download_path: str | None = None
    api_url: str | None = None
    api_key: str | None = None
    api_filename_key: str | None = None
    file_name_key: str | None = None
    file_path_key: str | None = None
    zip_file: str | None = None
    skip_rows: int = 0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | str) -> "BSEReportConfig":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                Logger.error(f"Invalid BSE tasktypedetails JSON: {error}")

        if not isinstance(value, Mapping):
            Logger.error("BSE tasktypedetails must be a JSON object.")

        text_fields = (
            "protocol",
            "file_type",
            "segment",
            "data_type",
            "url",
            "file_name",
            "download_path",
            "api_url",
            "api_key",
            "api_filename_key",
            "file_name_key",
            "file_path_key",
            "zip_file",
        )
        normalized: dict[str, Any] = {}
        for field_name in text_fields:
            raw_value = value.get(field_name)
            normalized[field_name] = (
                str(raw_value).strip()
                if raw_value is not None and str(raw_value).strip()
                else None
            )

        if normalized["protocol"] is not None:
            normalized["protocol"] = normalized["protocol"].lower()

        try:
            normalized["skip_rows"] = int(value.get("skip_rows") or 0)
        except (TypeError, ValueError) as error:
            Logger.error("BSE config 'skip_rows' must be an integer.")

        if normalized["skip_rows"] < 0:
            Logger.error("BSE config 'skip_rows' cannot be negative.")

        return cls(**normalized)
