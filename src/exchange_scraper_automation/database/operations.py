# db_operations.py

import csv
import os
from datetime import datetime, timezone

from psycopg import sql

from exchange_scraper_automation.observability.logger import Logger

USE_DYNAMIC_MARGIN_TABLE = True
USE_DYNAMIC_SPREAD_SCRIPMASTER_TABLE = True

logger = Logger


def update_task_status(connection, task_id, status):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_masterdata
                SET status = %s,
                    lastupdatetime =
                        (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')
                WHERE taskid = %s;
                """,
                (status, task_id),
            )
            rows_updated = cursor.rowcount

        connection.commit()

        if rows_updated == 0:
            logger.warning(
                f"Task status not updated because task was not found | "
                f"TaskID={task_id}"
            )
            return False

        logger.info(
            f"Task status updated successfully | " f"TaskID={task_id} | Status={status}"
        )
        return True

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(f"Task status rollback failed | Error={rollback_exc}")

        logger.error(f"Task status update failed | TaskID={task_id} | Error={exc}")
        return False


def get_table_column_types(connection, table_name):
    query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s;
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (table_name.lower(),))
            rows = cursor.fetchall()

        if not rows:
            logger.error(f"Table not found or has no columns | Table={table_name}")
            return {}

        return {
            column_name.lower(): data_type.lower() for column_name, data_type in rows
        }

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(f"Schema-query rollback failed | Error={rollback_exc}")

        logger.error(
            f"Failed to fetch table column types | Table={table_name} | Error={exc}"
        )
        return {}


def get_table_columns(connection, table_name):
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (table_name.lower(),))
            rows = cursor.fetchall()

        if not rows:
            logger.error(f"Table not found or has no columns | Table={table_name}")
            return []

        return [row[0] for row in rows]

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(f"Column-query rollback failed | Error={rollback_exc}")

        logger.error(
            f"Failed to fetch table columns | Table={table_name} | Error={exc}"
        )
        return []


def prepare_csv_for_table(connection, csv_file, table_name):
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

    if not rows:
        logger.error(f"CSV file is empty: {csv_file}")

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


# def truncate_table(connection, table_name):
#     query = sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(table_name))
#     with connection.cursor() as cursor:
#         cursor.execute(query)


def truncate_table(connection, table_name):
    try:
        query = sql.SQL("TRUNCATE TABLE {}").format(
            sql.Identifier("public", table_name.lower())
        )

        with connection.cursor() as cursor:
            cursor.execute(query)

        logger.info(f"Table truncated successfully: {table_name}")
        return True

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(
                f"Rollback failed after truncate error | "
                f"Table={table_name} | Error={rollback_exc}"
            )

        logger.error(f"Table truncation failed | " f"Table={table_name} | Error={exc}")
        return False


def bulk_insert_csv(connection, table_name, csv_file):
    try:
        query = sql.SQL(
            "COPY {} FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
        ).format(sql.Identifier("public", table_name.lower()))

        with connection.cursor() as cursor:
            with open(
                csv_file, "r", encoding="utf-8-sig", errors="replace", newline=""
            ) as file:
                with cursor.copy(query) as copy:
                    while True:
                        data = file.read(1024 * 1024)

                        if not data:
                            break

                        copy.write(data)

        logger.info(
            f"CSV inserted successfully | "
            f"Table={table_name} | File={os.path.basename(csv_file)}"
        )
        return True

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(
                f"Rollback failed after insert error | "
                f"Table={table_name} | Error={rollback_exc}"
            )

        logger.error(
            f"CSV insertion failed | "
            f"Table={table_name} | "
            f"File={os.path.basename(csv_file)} | "
            f"Error={exc}"
        )
        return False


def normalize_csv_file(csv_file, logger=None):
    """
    Ensure every CSV data row has the same number of columns
    as the header. Fill missing fields with empty values.
    """

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    if not rows:
        logger.error(f"CSV file is empty: {csv_file}")

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
            logger.error(
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

    logger.info(
    f"{'=' * 70}\n"
        f"Processing file: {file_name}\n"
        f"Target table: {table_name}\n"
        f"{'=' * 70}"
    )

    if not os.path.isfile(csv_file):
        logger.error(f"CSV file not found | File={csv_file} | Table={table_name}")
        return "FAILED"

    try:
        # Stop immediately if truncate fails.
        if not truncate_table(connection, table_name):
            logger.error(
                f"Upload cancelled because truncation failed | "
                f"File={file_name} | Table={table_name}"
            )
            return "FAILED"

        # Stop if CSV insertion fails.
        if not bulk_insert_csv(connection, table_name, csv_file):
            logger.error(
                f"Upload failed during insertion | "
                f"File={file_name} | Table={table_name}"
            )
            return "FAILED"

        connection.commit()

        logger.info(
            f"Upload completed successfully | " f"File={file_name} | Table={table_name}"
        )
        return "UPLOADED"

    except Exception as exc:
        try:
            connection.rollback()
        except Exception as rollback_exc:
            logger.error(f"Rollback failed | Table={table_name} | Error={rollback_exc}")

        logger.error(
            f"Unexpected upload error | "
            f"File={file_name} | Table={table_name} | Error={exc}"
        )
        return "FAILED"
