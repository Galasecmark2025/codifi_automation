# file_operations.py

import csv
import fnmatch
import gzip
import os
import shutil
import zipfile
from collections import Counter

import pandas as pd

from exchange_scraper_automation.observability.logger import Logger


def convert_xls_to_csv(input_file, output_file, logger=None):
    df = pd.read_excel(input_file, header=None)
    df.to_csv(output_file, index=False, header=False)
    if logger:
        logger.info(
            f"CSV Created : {output_file}\n"
            f"Columns     : {len(df.columns)}\n"
            f"Rows        : {len(df)}"
        )

    return output_file


def detect_text_delimiter(input_file):
    """Detect the delimiter used in a text-based data file."""

    with open(
        input_file,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as file:
        sample = file.read(65536)

    if not sample.strip():
        Logger.error(f"Decompressed file is empty: {input_file}")

    try:
        return (
            csv.Sniffer()
            .sniff(sample, delimiters=",|;\t",)
            .delimiter
        )

    except csv.Error:
        # Fallback for files where Sniffer cannot determine the delimiter.
        first_line = next(
            (line for line in sample.splitlines() if line.strip()),
            "",
        )

        candidates = [",", "|", ";", "\t"]
        delimiter = max(
            candidates,
            key=lambda item: first_line.count(item),
        )

        return delimiter if first_line.count(delimiter) > 0 else ","


def get_processed_csv_name(filenamepath, source_file, logger=None):
    """Build the processed CSV name from the database filenamepath.

    The database filenamepath identifies the downloaded source file. For the
    processed output, outer archive/compression suffixes are removed and
    non-CSV source extensions are converted to .csv.
    """
    configured_name = ""

    if filenamepath:
        configured_name = os.path.basename(str(filenamepath).strip().replace("\\", "/"))

    # A filename pattern is useful for validation, but it cannot be used as an
    # actual output filename. In that case preserve the actual downloaded name.
    if not configured_name or any(char in configured_name for char in "*?["):
        configured_name = os.path.basename(source_file)
        if filenamepath and logger:
            logger.warning(
                "filenamepath is not a concrete filename; using the actual source "
                f"basename instead | filenamepath={filenamepath!r}"
            )

    name_lower = configured_name.lower()
    if name_lower.endswith(".zip") or name_lower.endswith(".gz"):
        configured_name = os.path.splitext(configured_name)[0]

    stem, extension = os.path.splitext(configured_name)
    if extension.lower() != ".csv":
        configured_name = f"{stem or configured_name}.csv"

    return os.path.basename(configured_name)


def convert_single_file_to_csv(
    source_file,
    output_dir,
    headers=None,
    logger=None,
    output_file_name=None,
):
    """Convert one source file to CSV using the requested output filename."""

    source_file = os.path.abspath(source_file)
    output_dir = os.path.abspath(output_dir)
    source_name = os.path.basename(source_file)
    source_extension = os.path.splitext(source_name)[1].lower()

    output_name = output_file_name or (os.path.splitext(source_name)[0] + ".csv")
    output_name = os.path.basename(output_name)
    output_file = os.path.join(output_dir, output_name)

    os.makedirs(output_dir, exist_ok=True)

    # CSV: keep it in place when the name already matches; otherwise move it
    # to the filename derived from the database filenamepath.
    if source_extension == ".csv":
        if source_file != os.path.abspath(output_file):
            os.replace(source_file, output_file)
        result = output_file

    # TXT: detect the delimiter and convert.
    elif source_extension == ".txt":
        delimiter = detect_text_delimiter(source_file)
        result = convert_txt_to_csv(
            input_file=source_file,
            output_file=output_file,
            delimeter=delimiter,
            headers=headers,
            logger=logger,
        )

    # DAT: convert to CSV.
    elif source_extension == ".dat":
        result = convert_dat_to_csv(
            input_file=source_file,
            output_file=output_file,
            headers=headers,
            logger=logger,
        )

    # Excel: convert to CSV.
    elif source_extension in {".xls", ".xlsx"}:
        result = convert_xls_to_csv(
            input_file=source_file,
            output_file=output_file,
            logger=logger,
        )

    else:
        message = f"Unsupported source file type: {source_file}"
        if logger:
            logger.error(message)
        return None

    return result


def skip_incomplete_first_row(rows, input_file, logger=None):
    """Skip a metadata row when the first row is incomplete."""

    if len(rows) < 2:
        return rows

    # Infer the expected column count from the remaining rows.
    column_counts = Counter(len(row) for row in rows[1:])
    expected_columns = max(
        column_counts,
        key=lambda count: (column_counts[count], count),
    )

    first_row = rows[0]

    first_row_is_complete = len(first_row) == expected_columns and all(
        str(value).strip() for value in first_row
    )

    if not first_row_is_complete:
        rows = rows[1:]

        if logger:
            logger.warning(
                f"Skipped incomplete first row | "
                f"File={input_file} | "
                f"First row columns={len(first_row)} | "
                f"Expected columns={expected_columns} | "
                f"Row={first_row!r}"
            )

    return rows


def convert_dat_to_csv(input_file, output_file, headers=None, logger=None):
    rows = []

    with open(input_file, "r", encoding="utf-8", errors="replace") as dat_file:
        for line in dat_file:
            line = line.strip()

            if not line:
                continue

            columns = line.split(",")
            rows.append(columns)

    # Skip an incomplete metadata/version/count row at the beginning.
    rows = skip_incomplete_first_row(
        rows=rows,
        input_file=input_file,
        logger=logger,
    )

    if not rows:
        Logger.error(f"No data records found in DAT file: {input_file}")

    # Recalculate the column count after skipping the first row.
    max_columns = max(len(row) for row in rows)

    if headers:
        if len(headers) != max_columns:
            Logger.error(
                f"Header count ({len(headers)}) does not match, "
                f"data columns ({max_columns}) for {input_file}"
            )

        csv_headers = headers
    else:
        csv_headers = [f"column{i}" for i in range(1, max_columns + 1)]

    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

        for row in rows:
            row += [""] * (max_columns - len(row))
            writer.writerow(row)

    if logger:
        logger.info(
            f"CSV Created : {output_file}\n"
            f"Columns     : {max_columns}\n"
            f"Rows        : {len(rows)}"
        )

    return output_file


def convert_txt_to_csv(
    input_file,
    output_file,
    delimeter="|",
    headers=None,
    logger=None,
):
    """Convert a delimited TXT file into a CSV file."""

    rows = []

    with open(
        input_file,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as txt_file:
        reader = csv.reader(txt_file, delimiter=delimeter)

        for row in reader:
            if not row or not any(value.strip() for value in row):
                continue

            # Skip the NEATCD file identifier/version record.
            if row[0].strip().upper() == "NEATCD":
                continue

            rows.append(row)

    # Skip an incomplete metadata/version/count row at the beginning.
    rows = skip_incomplete_first_row(
        rows=rows,
        input_file=input_file,
        logger=logger,
    )

    if not rows:
        Logger.error(f"No data records found in TXT file: {input_file}")

    # Recalculate the column count after skipping the first row.
    max_columns = max(len(row) for row in rows)

    # Use configured headers when supplied; otherwise generate them.
    if headers:
        if isinstance(headers, str):
            csv_headers = [value.strip() for value in headers.split(",")]
        else:
            csv_headers = list(headers)

        if len(csv_headers) != max_columns:
            Logger.error(
                f"Header count ({len(csv_headers)}) does not match "
                f"data columns ({max_columns}) in {input_file}"
            )
    else:
        csv_headers = [f"column{i}" for i in range(1, max_columns + 1)]

    os.makedirs(
        os.path.dirname(os.path.abspath(output_file)),
        exist_ok=True,
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

        for row in rows:
            row += [""] * (max_columns - len(row))
            writer.writerow(row)

    if logger:
        logger.info(
            f"TXT converted to CSV: {output_file} | "
            f"Rows: {len(rows)} | Columns: {max_columns}"
        )

    return output_file


def extract_zip(zip_file_path, extract_to, logger=None):
    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    if logger:
        logger.info(f"Extracted to: {extract_to}")

    return extract_to


def extract_zip_files(zip_file_path, extract_to, logger=None):
    """Extract all ZIP contents directly into the destination directory."""

    os.makedirs(extract_to, exist_ok=True)
    destination_dir = os.path.abspath(extract_to)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        members = zip_ref.infolist()

        # Prevent archive entries from writing outside the destination.
        for member in members:
            target_path = os.path.abspath(
                os.path.join(destination_dir, member.filename)
            )

            try:
                is_inside_destination = (
                    os.path.commonpath([destination_dir, target_path])
                    == destination_dir
                )
            except ValueError:
                is_inside_destination = False

            if not is_inside_destination:
                Logger.error(f"Unsafe ZIP member path: {member.filename}")

        zip_ref.extractall(destination_dir)

    extracted_files = []

    for member in members:
        if member.is_dir():
            continue

        extracted_path = os.path.abspath(os.path.join(destination_dir, member.filename))

        if os.path.isfile(extracted_path):
            extracted_files.append(extracted_path)

    if logger:
        logger.info(
            f"ZIP extracted to: {destination_dir} | "
            f"Files extracted: {len(extracted_files)}"
        )

    return extracted_files


# =========================================================
# GZ HANDLING
# =========================================================
def extract_gz(gz_file_path, output_dir, logger=None, output_file_name=None):
    os.makedirs(output_dir, exist_ok=True)

    gz_file_name = os.path.basename(gz_file_path)

    if not gz_file_name.lower().endswith(".gz"):
        Logger.error(f"Expected .gz file: {gz_file_path}")

    # Remove only .gz
    # output_file_name = gz_file_name[:-3]
    if output_file_name:
        output_name = output_file_name
    else:
        output_name = gz_file_name[:-3]

    output_file = os.path.join(output_dir, output_name)

    # Decompress directly into final_files
    with gzip.open(gz_file_path, "rb") as source:
        with open(output_file, "wb") as target:
            shutil.copyfileobj(source, target)

    if logger:
        logger.info(f"GZ Extracted : {output_file}")

    return output_file


def lowercase_csv_columns(csv_file, logger=None):
    """
    Convert all CSV column names to lowercase.
    """
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

    if not rows:
        return csv_file

    # Lowercase column names only
    rows[0] = [column.strip().lower() for column in rows[0]]

    with open(csv_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    if logger:
        logger.info(f"CSV columns converted to lowercase: {csv_file}")

    return csv_file


# def normalize_final_csv(csv_file, logger=None):
#     return lowercase_csv_columns(csv_file, logger)


# =========================================================
# POST PROCESS
# =========================================================
def post_process(
    file_path,
    logger=None,
    headers=None,
    selected_file="all",
    skip_rows=0,  # Retained for compatibility; row skipping is not applied.
    local_filename=None,
    filenamepath=None,
):
    """Post-process a downloaded file, naming the CSV from database filenamepath."""

    file_path = os.path.abspath(file_path)
    output_dir = os.path.dirname(file_path)
    os.makedirs(output_dir, exist_ok=True)

    # filenamepath is the source of truth. local_filename remains as a legacy
    # fallback for callers that have not yet been updated.
    naming_source = filenamepath or local_filename or file_path
    output_file_name = get_processed_csv_name(
        filenamepath=naming_source,
        source_file=file_path,
        logger=logger,
    )

    if skip_rows and logger:
        logger.warning(
            "skip_rows is no longer applied by post_process; file conversion "
            "uses the existing DAT/TXT row-validation logic."
        )

    extension = os.path.splitext(file_path)[1].lower()

    # DAT -> CSV
    if extension == ".dat":
        result = convert_single_file_to_csv(
            source_file=file_path,
            headers=headers,
            logger=logger,
            output_file_name=output_file_name,
        )
        if result:
            return lowercase_csv_columns(result, logger)
        return None

    # ZIP -> one or more selected CSV outputs.
    if extension == ".zip":
        extracted_files = extract_zip_files(
            zip_file_path=file_path,
            extract_to=output_dir,
            logger=logger,
        )

        selection_is_all = (
            not selected_file or str(selected_file).strip().lower() == "all"
        )
        if selection_is_all:
            selected_paths = extracted_files
        else:
            pattern = os.path.basename(str(selected_file).strip()).lower()
            selected_paths = [
                path
                for path in extracted_files
                if fnmatch.fnmatch(os.path.basename(path).lower(), pattern)
            ]

        if not selected_paths:
            message = (
                "No matching files found in ZIP archive. "
                f"Archive={file_path} | Expected={selected_file}"
            )
            if logger:
                logger.error(message)
            return None

        results = []
        for source_file in selected_paths:
            # A single selected member gets the database-derived output name.
            # Multiple members keep their own basenames to avoid collisions.
            member_output_name = (
                output_file_name
                if len(selected_paths) == 1
                else os.path.splitext(os.path.basename(source_file))[0] + ".csv"
            )
            result = convert_single_file_to_csv(
                source_file=source_file,
                output_dir=output_dir,
                headers=headers,
                logger=logger,
                output_file_name=member_output_name,
            )
            if result is None:
                return None
            results.append(result)

        return results[0] if len(results) == 1 else results

    # GZ -> decompress, then convert/rename based on filenamepath.
    if extension == ".gz":
        compressed_name = os.path.basename(file_path)
        compressed_stem = compressed_name[:-3]
        supported_extensions = {".csv", ".txt", ".dat", ".xls", ".xlsx"}

        configured_name = ""
        configured_source = filenamepath or local_filename
        if configured_source:
            configured_name = os.path.basename(
                str(configured_source).strip().replace("\\", "/")
            )
            if configured_name.lower().endswith(".gz"):
                configured_name = configured_name[:-3]

        selected_name = (
            os.path.basename(str(selected_file).strip())
            if selected_file and str(selected_file).strip().lower() != "all"
            else ""
        )
        is_concrete_selection = (
            selected_name
            and not any(char in selected_name for char in "*?[")
            and os.path.splitext(selected_name)[1].lower() in supported_extensions
        )

        if is_concrete_selection:
            extracted_name = selected_name
        elif (
            configured_name
            and not any(char in configured_name for char in "*?[")
            and os.path.splitext(configured_name)[1].lower() in supported_extensions
        ):
            extracted_name = configured_name
        elif os.path.splitext(compressed_stem)[1].lower() in supported_extensions:
            extracted_name = compressed_stem
        else:
            extracted_name = os.path.splitext(output_file_name)[0] + ".txt"

        if selected_file and str(selected_file).strip().lower() != "all":
            if not fnmatch.fnmatch(
                extracted_name.lower(),
                os.path.basename(str(selected_file)).lower(),
            ):
                message = (
                    "Decompressed file does not match selection. "
                    f"File={extracted_name} | Expected={selected_file}"
                )
                if logger:
                    logger.error(message)
                return None

        result = extract_gz(
            gz_file_path=file_path,
            output_dir=output_dir,
            logger=logger,
            output_file_name=extracted_name,
        )
        return convert_single_file_to_csv(
            source_file=result,
            output_dir=output_dir,
            headers=headers,
            logger=logger,
            output_file_name=output_file_name,
        )

    # CSV/TXT/Excel source files are already downloaded to the shared directory.
    if extension in {".csv", ".txt", ".xls", ".xlsx"}:
        return convert_single_file_to_csv(
            source_file=file_path,
            output_dir=output_dir,
            headers=headers,
            logger=logger,
            output_file_name=output_file_name,
        )

    if logger:
        logger.info(f"No post-processing required: {file_path}")
    return file_path
