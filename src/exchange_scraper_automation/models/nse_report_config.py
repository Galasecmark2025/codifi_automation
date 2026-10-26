"""Typed configuration for NSE report downloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from exchange_scraper_automation.observability.logger import Logger


@dataclass(frozen=True, slots=True)
class NSEReportConfig:
    """The NSE config fields needed to locate and validate a report.

    Expected JSON keys are: tab, market, section, segment, protocol,
    data_type, report_label, and url_contains. Filename and extension rules
    come from the task's database ``filenamepath`` column, not this config.
    """

    tab: str
    market: str
    section: str
    segment: str
    protocol: str
    data_type: str
    report_label: str
    url_contains: str
    headers: tuple[str, ...] | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | str) -> "NSEReportConfig":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                Logger.error(f"Invalid NSE tasktypedetails JSON: {error}")

        if not isinstance(value, Mapping):
            Logger.error("NSE tasktypedetails must be a JSON object.")

        required_fields = (
            "tab",
            "market",
            "section",
            "segment",
            "protocol",
            "data_type",
            "report_label",
            "url_contains",
        )
        missing = [
            field
            for field in required_fields
            if not isinstance(value.get(field), str) or not value[field].strip()
        ]
        if missing:
            Logger.error(
                "Missing or empty required NSE config fields: " + ", ".join(missing)
            )

        raw_headers = value.get("headers")
        if raw_headers is None:
            headers = None
        elif isinstance(raw_headers, str):
            headers = tuple(
                part.strip() for part in raw_headers.split(",") if part.strip()
            )
        elif isinstance(raw_headers, (list, tuple)):
            headers = tuple(
                str(part).strip() for part in raw_headers if str(part).strip()
            )
        else:
            Logger.error(
                "NSE config 'headers' must be a list, comma-separated string, or null."
            )

        return cls(
            tab=value["tab"].strip(),
            market=value["market"].strip().lower(),
            section=value["section"].strip(),
            segment=value["segment"].strip(),
            protocol=value["protocol"].strip().lower(),
            data_type=value["data_type"].strip(),
            report_label=value["report_label"].strip(),
            url_contains=value["url_contains"].strip(),
            headers=headers,
        )
