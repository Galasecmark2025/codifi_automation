# file_operations.py

import csv
import fnmatch
import gzip
import os
import re
import shutil
import zipfile
from datetime import datetime
from collections import Counter

import pandas as pd

def convert_xls_to_csv(input_file, output_file, logger=None):
    df = pd.read_excel(input_file, header=None)
    df.to_csv(output_file, index=False, header=False)
    if logger:
        logger.info(f"CSV Created : {output_file}")
        logger.info(f"Columns     : {len(df.columns)}")
        logger.info(f"Rows        : {len(df)}")

    return output_file



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

    first_row_is_complete = (
        len(first_row) == expected_columns
        and all(str(value).strip() for value in first_row)
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
        raise ValueError(f"No data records found in DAT file: {input_file}")

    # Recalculate the column count after skipping the first row.
    max_columns = max(len(row) for row in rows)

    if headers:
        if len(headers) != max_columns:
            raise ValueError(
                f"Header count ({len(headers)}) does not match, "
                f"data columns ({max_columns}) for {input_file}"
            )

        csv_headers = headers
    else:
        csv_headers = [
            f"column{i}" for i in range(1, max_columns + 1)
        ]

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
        raise ValueError(
            f"No data records found in TXT file: {input_file}"
        )

    # Recalculate the column count after skipping the first row.
    max_columns = max(len(row) for row in rows)

    # Use configured headers when supplied; otherwise generate them.
    if headers:
        if isinstance(headers, str):
            csv_headers = [
                value.strip() for value in headers.split(",")
            ]
        else:
            csv_headers = list(headers)

        if len(csv_headers) != max_columns:
            raise ValueError(
                f"Header count ({len(csv_headers)}) does not match "
                f"data columns ({max_columns}) in {input_file}"
            )
    else:
        csv_headers = [
            f"column{i}" for i in range(1, max_columns + 1)
        ]

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
                raise ValueError(
                    f"Unsafe ZIP member path: {member.filename}"
                )

        zip_ref.extractall(destination_dir)

    extracted_files = []

    for member in members:
        if member.is_dir():
            continue

        extracted_path = os.path.abspath(
            os.path.join(destination_dir, member.filename)
        )

        if os.path.isfile(extracted_path):
            extracted_files.append(extracted_path)

    if logger:
        logger.info(
            f"ZIP extracted to: {destination_dir} | "
            f"Files extracted: {len(extracted_files)}"
        )

    return extracted_files


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
    local_filename=None):
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
            input_file=file_path, 
            output_file=final_csv, 
            headers=headers, 
            logger=logger
        )

        return lowercase_csv_columns(result, logger)

    # -----------------------------------------------------
    # ZIP
    # -----------------------------------------------------
    if extension == ".zip":
        extracted_files = extract_zip_files(
            zip_file_path=file_path,
            extract_to=final_files_dir,
            logger=logger,
        )

        # -----------------------------------------------------
        # SPECIAL CASE: ZIP CONTAINS EXACTLY ONE TXT FILE
        # -----------------------------------------------------
        if (len(extracted_files) == 1 and os.path.splitext(extracted_files[0])[1].lower() == ".txt"):
            txt_file = extracted_files[0]

            csv_name = (output_file_name or os.path.splitext(os.path.basename(txt_file))[0] + ".csv")

            final_csv = os.path.join(final_files_dir, csv_name)

            result = convert_txt_to_csv(
                input_file=txt_file,
                output_file=final_csv,
                headers=headers,
                logger=logger,
            )

            normalize_final_csv(result, logger)

            return [result]

        csv_files = []

        for source_file in extracted_files:
            file_name = os.path.basename(source_file)

            # Select files from this archive using the configured pattern.
            if (
                selected_file.lower() != "all"
                and not fnmatch.fnmatch(
                    file_name.lower(),
                    selected_file.lower(),
                )
            ):
                continue

            file_extension = os.path.splitext(file_name)[1].lower()

            # -------------------------------------------------
            # CSV
            # -------------------------------------------------
            if file_extension == ".csv":
                output_name = (output_file_name or os.path.basename(source_file))

                destination_file = os.path.abspath(os.path.join(final_files_dir, output_name))

                # Avoid copying a file onto itself when it was
                # extracted directly into the destination directory.
                if (os.path.abspath(source_file) == destination_file and skip_rows == 0):
                    final_file = source_file
                else:
                    final_file = copy_csv_to_final(
                        source_file=source_file,
                        final_files_dir=final_files_dir,
                        logger=logger,
                        output_file_name=output_file_name,
                        skip_rows=skip_rows,
                    )

                csv_files.append(final_file)

            # -------------------------------------------------
            # XLS / XLSX
            # -------------------------------------------------
            elif file_extension in (".xls", ".xlsx"):
                csv_name = (output_file_name or os.path.splitext(file_name)[0] + ".csv")

                final_csv = os.path.join(final_files_dir, csv_name)

                convert_xls_to_csv(
                    input_file=source_file,
                    output_file=final_csv,
                    logger=logger,
                )

                csv_files.append(final_csv)

        if not csv_files:
            raise FileNotFoundError(
                "No matching CSV/XLS/XLSX files found in ZIP archive. "
                f"Archive={file_path} | Expected={selected_file}"
            )

        # Normalize headers on the processed CSV files.
        for csv_file in csv_files:
            normalize_final_csv(csv_file, logger)

        return csv_files

    # -----------------------------------------------------
    # GZ
    # -----------------------------------------------------

    if extension == ".gz":
        selected_name = os.path.basename(str(selected_file or "all"))
        selected_extension = os.path.splitext(selected_name)[1].lower()

        # Avoid using a wildcard pattern as a physical filename.
        is_specific_file = (
            selected_name.lower() != "all"
            and not any(char in selected_name for char in "*?[")
        )

        configured_name = (
            os.path.basename(local_filename)
            if local_filename
            else ""
        )

        if configured_name:
            configured_stem = os.path.splitext(configured_name)[0]
            raw_extension = selected_extension or ".txt"
            raw_filename = configured_stem + raw_extension
        elif is_specific_file:
            raw_filename = selected_name
        else:
            raw_filename = output_file_name

        result = extract_gz(
            gz_file_path=file_path,
            final_files_dir=final_files_dir,
            logger=logger,
            output_file_name=raw_filename,
        )

        result_extension = os.path.splitext(result)[1].lower()

        # -------------------------------------------------
        # TXT -> CSV
        # -------------------------------------------------
        if result_extension == ".txt":
            csv_name = (
                configured_name
                if configured_name.lower().endswith(".csv")
                else output_file_name
                or os.path.splitext(os.path.basename(result))[0] + ".csv"
            )

            final_csv = os.path.join(final_files_dir, csv_name)

            converted_csv = convert_txt_to_csv(
                input_file=result,
                output_file=final_csv,
                headers=headers,
                logger=logger,
            )

            normalize_final_csv(converted_csv, logger)

            logger.info(
                f"GZ download processing completed | "
                f"TXT={result} | CSV={converted_csv}"
            )

            return converted_csv

        # -------------------------------------------------
        # CSV
        # -------------------------------------------------
        if result_extension == ".csv":
            normalize_final_csv(result, logger)
            return result

        if logger:
            logger.warning(
                f"GZ extracted, but no CSV conversion rule matched | "
                f"Extracted file={result} | "
                f"Expected extension=.txt or .csv"
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
