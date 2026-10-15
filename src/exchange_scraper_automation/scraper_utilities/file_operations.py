# file_operations.py

import csv
import fnmatch
import gzip
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone

import pandas as pd

# from utilities.file_tracker import get_target_date


def normalize_date_columns(csv_file, date_columns=None, logger=None):
    """
    Normalize date columns according to the target database datatype.

    INT / BIGINT:
        28-SEP-2026 -> Unix epoch seconds
        1795392000  -> preserved
        -1          -> preserved

    DATE:
        28-SEP-2026 -> 2026-09-28
        2026-09-28  -> 2026-09-28
        1795392000  -> 2026-11-23

    Blank values remain blank so PostgreSQL can insert NULL.
    """

    if date_columns is None:
        date_columns = {}

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

    if not rows:
        return csv_file

    headers = [header.strip().lower() for header in rows[0]]
    rows[0] = headers

    date_indexes = {
        column: (headers.index(column), data_type)
        for column, data_type in date_columns.items()
        if column in headers
    }

    if not date_indexes:
        return csv_file

    converted_count = 0

    for row in rows[1:]:
        for column, (index, data_type) in date_indexes.items():

            if index >= len(row):
                row.extend([""] * (index + 1 - len(row)))

            value = row[index].strip()

            if not value:
                row[index] = ""
                continue

            try:
                # -------------------------------------------------
                # Already numeric value
                # -------------------------------------------------
                if value.lstrip("-").isdigit():

                    numeric_value = int(value)

                    if data_type in ("INT", "BIGINT"):
                        # Preserve epoch / sentinel values such as -1
                        row[index] = str(numeric_value)

                    elif data_type == "DATE":
                        # Convert Unix epoch seconds -> YYYY-MM-DD
                        date_value = datetime.fromtimestamp(
                            numeric_value, tz=timezone.utc
                        )

                        row[index] = date_value.strftime("%Y-%m-%d")
                        converted_count += 1

                    continue

                # -------------------------------------------------
                # Normal date string
                # -------------------------------------------------
                try:
                    date_value = datetime.strptime(value, "%d-%b-%Y")
                except ValueError:
                    date_value = datetime.strptime(value, "%Y-%m-%d")

                date_value = date_value.replace(tzinfo=timezone.utc)

                if data_type in ("INT", "BIGINT"):
                    row[index] = str(int(date_value.timestamp()))

                elif data_type == "DATE":
                    row[index] = date_value.strftime("%Y-%m-%d")

                converted_count += 1

            except (ValueError, OverflowError, OSError):
                if logger:
                    logger.warning(
                        f"Invalid date value | "
                        f"File={os.path.basename(csv_file)} | "
                        f"Column={column} | "
                        f"Value={value}"
                    )

    with open(csv_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    if logger and converted_count:
        logger.info(
            f"Date fields normalized: "
            f"{os.path.basename(csv_file)} "
            f"[Values converted: {converted_count}]"
        )

    return csv_file


def convert_xls_to_csv(input_file, output_file, logger=None):
    df = pd.read_excel(input_file, header=None)
    df.to_csv(output_file, index=False, header=False)
    if logger:
        logger.info(f"CSV Created : {output_file}")
        logger.info(f"Columns     : {len(df.columns)}")
        logger.info(f"Rows        : {len(df)}")

    return output_file


def convert_dat_to_csv(input_file, output_file, headers=None, logger=None):
    rows = []
    max_columns = 0

    with open(input_file, "r", encoding="utf-8", errors="replace") as dat_file:
        for line in dat_file:
            line = line.strip()

            if not line:
                continue

            columns = line.split(",")
            rows.append(columns)
            max_columns = max(max_columns, len(columns))

    if headers:
        if len(headers) != max_columns:
            raise ValueError(
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
        logger.info(f"CSV Created : {output_file}")

        logger.info(f"Columns     : {max_columns}")

        logger.info(f"Rows        : {len(rows)}")

    return output_file


def extract_zip(zip_file_path, extract_to, logger=None):
    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    if logger:
        logger.info(f"Extracted to: {extract_to}")

    return extract_to


def copy_csv_to_final(
    source_file, final_files_dir, logger=None, output_file_name=None, skip_rows=0
):
    os.makedirs(final_files_dir, exist_ok=True)

    if output_file_name:
        file_name = output_file_name
    else:
        file_name = os.path.basename(source_file)

    final_file = os.path.join(final_files_dir, file_name)

    if skip_rows > 0:
        with open(source_file, "r", encoding="utf-8-sig", newline="") as src:
            rows = list(csv.reader(src))

        rows = rows[skip_rows:]

        with open(final_file, "w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst)
            writer.writerows(rows)
    else:
        shutil.copy2(source_file, final_file)

    if logger:
        logger.info(f"CSV Copied : {final_file}")

    return final_file


def copy_files_from_folder(
    source_folder,
    final_files_dir,
    logger=None,
    selected_file="all",
    output_file_name=None,
    skip_rows=0,
):
    final_files = []
    for root, _, files in os.walk(source_folder):
        for file_name in files:
            # -------------------------------------------------
            # FILE SELECTION
            # -------------------------------------------------
            if selected_file != "all":
                if not fnmatch.fnmatch(file_name.lower(), selected_file.lower()):
                    continue

            source_file = os.path.join(root, file_name)
            extension = os.path.splitext(file_name)[1].lower()

            # -------------------------------------------------
            # CSV
            # -------------------------------------------------
            if extension == ".csv":
                final_file = copy_csv_to_final(
                    source_file=source_file,
                    final_files_dir=final_files_dir,
                    logger=logger,
                    output_file_name=output_file_name,
                    skip_rows=skip_rows,
                )
                final_files.append(final_file)

            # -------------------------------------------------
            # XLS / XLSX
            # -------------------------------------------------

            elif extension in (".xls", ".xlsx"):
                if output_file_name:
                    csv_name = output_file_name
                else:
                    csv_name = os.path.splitext(file_name)[0] + ".csv"

                final_csv = os.path.join(final_files_dir, csv_name)
                convert_xls_to_csv(
                    input_file=source_file, output_file=final_csv, logger=logger
                )
                final_files.append(final_csv)

    if not final_files:
        raise FileNotFoundError(
            f"No matching file found in ZIP extraction folder: "
            f"{source_folder}\n"
            f"Expected: {selected_file}"
        )

    return final_files


# =========================================================
# GZ HANDLING
# =========================================================
def extract_gz(gz_file_path, final_files_dir, logger=None, output_file_name=None):
    os.makedirs(final_files_dir, exist_ok=True)

    gz_file_name = os.path.basename(gz_file_path)

    if not gz_file_name.lower().endswith(".gz"):
        raise ValueError(f"Expected .gz file: {gz_file_path}")

    # Remove only .gz
    # output_file_name = gz_file_name[:-3]
    if output_file_name:
        output_name = output_file_name
    else:
        output_name = gz_file_name[:-3]

    # output_file = os.path.join(final_files_dir,output_file_name)
    output_file = os.path.join(final_files_dir, output_name)

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


def normalize_final_csv(csv_file, logger=None):
    return lowercase_csv_columns(csv_file, logger)


# =========================================================
# POST PROCESS
# =========================================================
def post_process(
    file_path,
    final_files_dir,
    logger=None,
    headers=None,
    selected_file="all",
    table_name=None,
    skip_rows=0,
    config=None,
):
    extension = os.path.splitext(file_path)[1].lower()

    output_file_name = None
    if table_name:
        file_name = os.path.basename(file_path)

        # Find 8 digit date in filename
        date_match = re.search(r"\d{8}", file_name)

        if date_match:
            date_value = date_match.group(0)

            # YYYYMMDD
            if 1900 <= int(date_value[:4]) <= 2100:
                final_date = date_value

            # DDMMYYYY
            else:
                final_date = date_value[4:8] + date_value[2:4] + date_value[0:2]

            output_file_name = f"{table_name}_{final_date}.csv"

        else:
            # No date found → current target market date
            if config is None:
                raise ValueError(
                    "config is required when target date is needed for post-processing."
                )
            final_date = datetime.now()
            output_file_name = f"{table_name}_{final_date}.csv"

    # -----------------------------------------------------
    # DAT
    # -----------------------------------------------------

    if extension == ".dat":
        file_name = os.path.basename(file_path)

        if output_file_name:
            csv_name = output_file_name
        else:
            csv_name = os.path.splitext(file_name)[0] + ".csv"

        final_csv = os.path.join(final_files_dir, csv_name)

        result = convert_dat_to_csv(
            input_file=file_path, output_file=final_csv, headers=headers, logger=logger
        )

        return lowercase_csv_columns(result, logger)

    # -----------------------------------------------------
    # ZIP
    # -----------------------------------------------------

    if extension == ".zip":
        zip_name = os.path.splitext(os.path.basename(file_path))[0]
        extracted_folder = os.path.join(os.path.dirname(file_path), zip_name)

        extracted_folder = extract_zip(
            zip_file_path=file_path, extract_to=extracted_folder, logger=logger
        )

        csv_files = copy_files_from_folder(
            source_folder=extracted_folder,
            final_files_dir=final_files_dir,
            logger=logger,
            selected_file=selected_file,
            output_file_name=output_file_name,
            skip_rows=skip_rows,
        )

        # Convert every generated CSV header to lowercase
        for csv_file in csv_files:
            # lowercase_csv_columns(csv_file, logger)
            normalize_final_csv(csv_file, logger)

        return csv_files

    # -----------------------------------------------------
    # GZ
    # -----------------------------------------------------

    if extension == ".gz":
        result = extract_gz(
            gz_file_path=file_path,
            final_files_dir=final_files_dir,
            logger=logger,
            output_file_name=output_file_name,
        )

        # Only process if resulting file is CSV
        if result.lower().endswith(".csv"):
            lowercase_csv_columns(result, logger)
            normalize_date_columns(
                result,
                logger=logger,
            )

        return result

    # -----------------------------------------------------
    # CSV
    # -----------------------------------------------------

    if extension == ".csv":
        result = copy_csv_to_final(
            source_file=file_path,
            final_files_dir=final_files_dir,
            logger=logger,
            output_file_name=output_file_name,
            skip_rows=skip_rows,
        )

        # return lowercase_csv_columns(result, logger)
        return normalize_final_csv(result, logger)

    # -----------------------------------------------------
    # OTHER
    # -----------------------------------------------------

    if logger:
        logger.info(f"No post-processing required: " f"{file_path}")

    return file_path
