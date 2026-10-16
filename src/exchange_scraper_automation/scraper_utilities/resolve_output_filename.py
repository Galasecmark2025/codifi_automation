import fnmatch
from pathlib import Path

def resolve_output_filename(
    local_filename: str | None,
    downloaded_file: str | Path,
) -> str | None:
    """Resolve a wildcard output filename from the actual downloaded name."""

    if not local_filename:
        return local_filename

    output_pattern = Path(local_filename).name

    # Preserve explicitly configured filenames, e.g. cm_participant.csv.
    if not any(char in output_pattern for char in "*?["):
        return output_pattern

    source_name = Path(downloaded_file).name
    source_lower = source_name.lower()

    if source_lower.endswith(".gz"):
        # Example: NSE_FO_contract_22092026.csv.gz
        actual_name = source_name[:-3]

    elif source_lower.endswith(".zip"):
        # Example: BhavCopy_NSE_CM_0_0_0_20260922_F_0000.csv.zip
        actual_name = source_name[:-4]

    elif source_lower.endswith((".dat", ".txt")):
        # Converted text/data files are saved as CSV.
        actual_name = str(Path(source_name).with_suffix(".csv"))

    else:
        actual_name = source_name

    if not fnmatch.fnmatchcase(actual_name, output_pattern):
        raise ValueError(
            "Cannot resolve output filename | "
            f"Downloaded={source_name!r} | "
            f"OutputPattern={output_pattern!r} | "
            f"Candidate={actual_name!r}"
        )

    return actual_name

