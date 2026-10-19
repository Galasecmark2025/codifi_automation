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
    """Insert CSV data into the table using the existing column order."""

    query = sql.SQL(
        "COPY {} FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')").format(
        sql.Identifier("public", table_name)
    )
    # db_columns = get_table_columns(connection=connection, table_name=table_name)

    # column_sql = sql.SQL(", ").join(sql.Identifier(column) for column in db_columns)

    # query = sql.SQL(
    #     "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
    # ).format(sql.Identifier(table_name), column_sql)

    with connection.cursor() as cursor:
        with open(csv_file, "r", encoding="utf-8-sig", errors="replace", newline="") as file:
            with cursor.copy(query) as copy:
                while True:
                    data = file.read(1024 * 1024)
                    if not data:
                        break

                    copy.write(data)


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
        # prepare_csv_for_table(
        #     connection=connection,
        #     csv_file=csv_file,
        #     table_name=table_name,
        # )
        # normalize_csv_file(
        #     csv_file=csv_file,
        #     logger=logger,
        # )

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
