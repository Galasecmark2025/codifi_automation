"""Filename templates with exact matching and date placeholders."""

import re
from pathlib import PurePosixPath

from exchange_scraper_automation.observability.logger import Logger

DATE_TOKENS = {
    "<DDMMYYYY>": r"\d{8}",
    "<YYYYMMDD>": r"\d{8}",
}


def filename_template_regex(filename_template: str) -> re.Pattern[str]:
    """
    Build an exact-match regex from a filename template.

    Literal characters must match exactly. Only supported date tokens
    are variable-length patterns.
    """

    value = str(filename_template).strip()

    if not value:
        Logger.error("Filename template cannot be empty.")

    parts = re.split(r"(<[^<>]+>)", value)
    regex_parts = []

    for part in parts:
        if not part:
            continue

        if part in DATE_TOKENS:
            regex_parts.append(DATE_TOKENS[part])
        elif part.startswith("<") and part.endswith(">"):
            Logger.error(f"Unsupported filename placeholder: {part}")
        else:
            regex_parts.append(re.escape(part))

    return re.compile("^" + "".join(regex_parts) + "$")


def expected_filename(filenamepath: str) -> str:
    """Return the filename component of a configured filenamepath."""

    filename = PurePosixPath(str(filenamepath).strip()).name

    if not filename:
        Logger.error(f"filenamepath must identify a filename: {filenamepath!r}")

    return filename


def validate_filenamepath(
    filenamepath: str,
    actual_filename: str,
) -> None:
    """Validate a discovered filename against its configured template."""

    expected = expected_filename(filenamepath)
    actual = PurePosixPath(actual_filename).name
    pattern = filename_template_regex(expected)

    if not pattern.fullmatch(actual):
        Logger.error(
            f"filenamepath mismatch | "
            f"ExpectedTemplate={expected!r} | Actual={actual!r}"
        )
