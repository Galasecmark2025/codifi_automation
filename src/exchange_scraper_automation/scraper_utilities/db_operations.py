# db_operations.py

import csv
import os
from datetime import datetime, timezone

from psycopg import sql

from exchange_scraper_automation.scraper_utilities.logger import Logger

USE_DYNAMIC_MARGIN_TABLE = True
USE_DYNAMIC_SPREAD_SCRIPMASTER_TABLE = True

logger = Logger

BHAVCOPY_TABLES = [
    "tbl_TempBhavCopyNSEEQ",
    "tbl_TempBhavCopyNSEFO",
    "tbl_TempBhavCopyNSECU",
    "tbl_TempBhavCopyNSECO",
    "tbl_TempBhavCopyNSESLB",
    "tbl_TempBhavCopyBSEEQ",
    "tbl_TempBhavCopyBSEFO",
    "tbl_TempBhavCopyBSECU",
    "tbl_TempBhavCopyBSECO",
    "tbl_TempBhavCopyBSESLB",
]


def update_task_status(connection, task_id, status):
    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE tbl_masterdata
            SET status = %s, lastupdatetime = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')
            WHERE taskid = %s;
            """,
            (status, task_id),
        )

        connection.commit()

        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()


def get_table_column_types(connection, table_name):
    query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (table_name,))
        rows = cursor.fetchall()

    if not rows:
        raise ValueError(f"Table not found or has no columns: {table_name}")

    return {column_name.lower(): data_type.lower() for column_name, data_type in rows}


def normalize_date_columns(
    connection,
    csv_file,
    table_name,
    logger=None,
):
    """
    Normalize only configured date columns that exist in the CSV.

    INTEGER/BIGINT columns:
        Date strings -> Unix epoch seconds.

    DATE columns:
        Supported date strings -> YYYY-MM-DD.

    Blank values remain blank.
    Existing numeric values are preserved for integer columns.
    """

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    if not rows:
        return csv_file

    headers = [header.strip() for header in rows[0]]
    header_indexes = {header.lower(): index for index, header in enumerate(headers)}

    column_types = get_table_column_types(
        connection=connection,
        table_name=table_name,
    )

    configured_columns = {column.lower() for column in COLUMN_SPECIFICATIONS}

    matching_columns = {
        column: (
            header_indexes[column],
            column_types[column],
        )
        for column in configured_columns
        if column in header_indexes and column in column_types
    }

    if not matching_columns:
        return csv_file

    converted_count = 0

    for row_number, row in enumerate(rows[1:], start=2):
        # Ensure the row has enough fields for its CSV header.
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))

        for column, (index, data_type) in matching_columns.items():
            value = row[index].strip()

            if not value:
                continue

            is_integer_type = data_type in {
                "smallint",
                "integer",
                "bigint",
            }

            is_date_type = data_type == "date"

            # Ignore configured columns whose DB type does not
            # require date normalization.
            if not is_integer_type and not is_date_type:
                continue

            # Existing numeric values in integer columns are preserved.
            if is_integer_type and value.lstrip("-").isdigit():
                continue

            try:
                date_value = None

                # Support common exchange date formats.
                for date_format in (
                    "%d-%b-%Y",
                    "%Y-%m-%d",
                    "%Y%m%d",
                ):
                    try:
                        date_value = datetime.strptime(value, date_format)
                        break
                    except ValueError:
                        continue

                if date_value is None:
                    # For DATE columns, also accept Unix epoch seconds.
                    if is_date_type and value.lstrip("-").isdigit():
                        date_value = datetime.fromtimestamp(int(value), tz=timezone.utc)
                    else:
                        raise ValueError(f"Unsupported date format: {value}")

                if is_integer_type:
                    date_value = date_value.replace(tzinfo=timezone.utc)
                    row[index] = str(int(date_value.timestamp()))

                elif is_date_type:
                    row[index] = date_value.strftime("%Y-%m-%d")

                converted_count += 1

            except (ValueError, OverflowError, OSError) as exc:
                raise ValueError(
                    f"Invalid date value in "
                    f"{os.path.basename(csv_file)} "
                    f"[Row: {row_number}, "
                    f"Column: {column}, Value: {value}]: {exc}"
                ) from exc

    with open(csv_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows([headers, *rows[1:]])

    if logger:
        logger.info(
            f"Date fields normalized: "
            f"{os.path.basename(csv_file)} "
            f"[Values converted: {converted_count}]"
        )

    return csv_file


def normalize_date_columns(csv_file, date_columns=None, logger=None):
    """
    Convert exchange date values to the representation
    required by the database.

    For ScripMaster INTEGER date fields:
        28-SEP-2026 -> epoch seconds

    Existing integer/epoch values are preserved.
    Blank values remain blank for PostgreSQL NULL.
    """

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

            # normalize_csv_file() should already have fixed row length,
            # but keep this protection here as well.
            if index >= len(row):
                row.extend([""] * (index + 1 - len(row)))

            value = row[index].strip()

            if not value:
                row[index] = ""
                continue

            # Already an integer / epoch value.
            if value.lstrip("-").isdigit():
                # continue
                if data_type in ("INT", "BIGINT"):
                    continue

                elif data_type == "DATE":
                    date_value = datetime.fromtimestamp(int(value), tz=timezone.utc)
                    row[index] = date_value.strftime("%Y-%m-%d")
                    converted_count += 1
                    continue

            try:
                try:
                    # Format: 28-SEP-2026
                    date_value = datetime.strptime(value, "%d-%b-%Y")
                except ValueError:
                    # Format: 2022-09-23
                    date_value = datetime.strptime(value, "%Y-%m-%d")

                date_value = date_value.replace(tzinfo=timezone.utc)

                if data_type == "INT":
                    row[index] = str(int(date_value.timestamp()))
                    converted_count += 1

            except ValueError:
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


def get_table_columns(connection, table_name):
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (table_name,))
        rows = cursor.fetchall()

    if not rows:
        raise ValueError(f"Table not found or has no columns: {table_name}")

    return [row[0] for row in rows]


def prepare_csv_for_table(connection, csv_file, table_name):
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file is empty: {csv_file}")

    csv_headers = [header.strip() for header in rows[0]]

    db_columns = get_table_columns(connection=connection, table_name=table_name)

    csv_header_map = {header.lower(): index for index, header in enumerate(csv_headers)}

    db_column_map = {column.lower(): column for column in db_columns}

    missing_columns = [
        column for column in db_columns if column.lower() not in csv_header_map
    ]

    extra_columns = [
        header for header in csv_headers if header.lower() not in db_column_map
    ]

    if missing_columns:
        logger.warning(f"CSV missing columns for {table_name}: " f"{missing_columns}")

    if extra_columns:
        logger.warning(
            f"CSV extra columns ignored for {table_name}: " f"{extra_columns}"
        )

    reordered_rows = [db_columns]

    for row in rows[1:]:
        reordered_row = []
        for db_column in db_columns:
            csv_index = csv_header_map.get(db_column.lower())

            if csv_index is None:
                reordered_row.append("")
            elif csv_index < len(row):
                reordered_row.append(row[csv_index])
            else:
                reordered_row.append("")

        reordered_rows.append(reordered_row)

    with open(csv_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(reordered_rows)

    logger.info(f"CSV mapped to database structure: " f"{os.path.basename(csv_file)}")

    return db_columns


def truncate_table(connection, table_name):
    query = sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(table_name))
    with connection.cursor() as cursor:
        cursor.execute(query)


def bulk_insert_csv(connection, table_name, csv_file):
    db_columns = get_table_columns(connection=connection, table_name=table_name)

    column_sql = sql.SQL(", ").join(sql.Identifier(column) for column in db_columns)

    query = sql.SQL(
        "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
    ).format(sql.Identifier(table_name), column_sql)

    with connection.cursor() as cursor:
        with open(csv_file, "r", encoding="utf-8", errors="replace") as file:
            with cursor.copy(query) as copy:
                while True:
                    data = file.read(1024 * 1024)
                    if not data:
                        break

                    copy.write(data)


COLUMN_SPECIFICATIONS = [
    "xprydt",
    "exrcstartdt",
    "exrcenddt",
    "bookclsrstartdt",
    "bookclsrenddt",
    "nodlvrystartdt",
    "nodlvryenddt",
    "startdt",
    "enddt",
    "mtrtydt",
    "pdctstartdt",
    "admssndt",
    "traddt",
    "bizdt",
    "fininstrmactlxprydt",
]


def normalize_csv_file(csv_file, logger=None):
    """
    Ensure every CSV data row has the same number of columns
    as the header. Fill missing fields with empty values.
    """

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    if not rows:
        raise ValueError(f"CSV file is empty: {csv_file}")

    headers = rows[0]
    expected_columns = len(headers)
    normalized_rows = [headers]

    for row_number, row in enumerate(rows[1:], start=2):
        actual_columns = len(row)

        if actual_columns < expected_columns:
            missing = expected_columns - actual_columns
            row.extend([""] * missing)

            if logger:
                logger.warning(
                    f"Missing values filled with empty fields: "
                    f"{os.path.basename(csv_file)} "
                    f"[Row: {row_number}, Missing: {missing}]"
                )

        elif actual_columns > expected_columns:
            raise ValueError(
                f"Extra data found in CSV: "
                f"{os.path.basename(csv_file)} "
                f"[Row: {row_number}, Expected: {expected_columns}, "
                f"Found: {actual_columns}]"
            )

        normalized_rows.append(row)

    with open(csv_file, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(normalized_rows)

    if logger:
        logger.info(f"CSV normalized successfully: " f"{os.path.basename(csv_file)}")

    return csv_file


def upload_csv_file(connection, csv_file, table_name):
    table_name = table_name.lower()
    file_name = os.path.basename(csv_file)

    logger.info("=" * 70)
    logger.info(f"Processing file: {file_name}")
    logger.info(f"Target table: {table_name}")
    logger.info("=" * 70)

    if not os.path.isfile(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    try:
        normalize_csv_file(
            csv_file=csv_file,
            logger=logger,
        )

        normalize_date_columns(
            connection=connection,
            csv_file=csv_file,
            table_name=table_name,
            logger=logger,
        )

        prepare_csv_for_table(
            connection=connection,
            csv_file=csv_file,
            table_name=table_name,
        )

        truncate_table(
            connection=connection,
            table_name=table_name,
        )

        bulk_insert_csv(
            connection=connection,
            table_name=table_name,
            csv_file=csv_file,
        )

        connection.commit()
        logger.info(f"Upload successful: {file_name}")

        return "UPLOADED"

    except Exception as exc:
        connection.rollback()
        logger.error(f"Upload failed: {file_name} | Error: {exc}")

        return "FAILED"
