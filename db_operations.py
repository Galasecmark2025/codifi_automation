import os
import csv
import re
import json
import hashlib

from datetime import datetime

from connect_with_db import get_connection

from logger import get_logger

logger = get_logger("db_operations")

# ============================================================
# CONFIGURATION
# ============================================================

FINAL_FILES_DIR = "final_files"
TRACKER_FILE = "file_tracker.json"

# ============================================================
# EXTRACT DATE FROM FILE NAME
# ============================================================

def get_file_date(file_name):

    logger.info(f"Checking date in filename: {file_name}")

    # --------------------------------------------------------
    # NSE/BSE Bhavcopy format
    #
    # Example:
    # BhavCopy_NSE_CM_0_0_0_20260821_F_0000.csv
    #
    # Date = 20260821
    # Format = YYYYMMDD
    # --------------------------------------------------------

    match = re.search(
        r"_(\d{8})_F_\d+\.",
        file_name,
        re.IGNORECASE
    )

    if match:

        date_string = match.group(1)

        try:

            file_date = datetime.strptime(
                date_string,
                "%Y%m%d"
            ).date()

            logger.info(
                f"Detected date : {file_date} "
                f"(YYYYMMDD)"
            )

            return file_date

        except ValueError:

            pass

    # --------------------------------------------------------
    # NSE VaR format
    #
    # Example:
    # C_VAR1_21082026_1.csv
    #
    # Date = 21082026
    # Format = DDMMYYYY
    # --------------------------------------------------------

    match = re.search(
        r"_(\d{8})_\d+\.",
        file_name,
        re.IGNORECASE
    )

    if match:

        date_string = match.group(1)

        try:

            file_date = datetime.strptime(
                date_string,
                "%d%m%Y"
            ).date()

            logger.info(
                f"Detected date : {file_date} "
                f"(DDMMYYYY)"
            )

            return file_date

        except ValueError:

            pass

    # --------------------------------------------------------
    # Date not found
    # --------------------------------------------------------

    logger.info(
        f"WARNING: Could not detect date "
        f"from filename: {file_name}"
    )

    return None


# ============================================================
# GET REPORT NAME WITHOUT DATE
# ============================================================

def get_report_key(file_name):

    name = os.path.splitext(
        file_name
    )[0].lower()

    # --------------------------------------------------------
    # Bhavcopy:
    #
    # bhavcopy_nse_cm_0_0_0_20260821_f_0000
    #
    # becomes:
    #
    # bhavcopy_nse_cm_0_0_0
    # --------------------------------------------------------

    name = re.sub(
        r"_\d{8}_f_\d+$",
        "",
        name,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # VaR:
    #
    # c_var1_21082026_1
    #
    # becomes:
    #
    # c_var1
    # --------------------------------------------------------

    name = re.sub(r"_\d{8}_\d+$","",name)

    return name


# ============================================================
# TABLE NAME
# ============================================================

def get_table_name(file_name):

    table_name = os.path.splitext(
        file_name
    )[0]

    table_name = table_name.lower()

    table_name = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        table_name
    )

    if table_name[0].isdigit():

        table_name = (
            "table_" + table_name
        )

    return table_name


# ============================================================
# CSV HEADERS
# ============================================================

def get_csv_headers(csv_file):

    logger.info(
        f"Reading CSV headers: "
        f"{os.path.basename(csv_file)}"
    )

    with open(
        csv_file,
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:

        reader = csv.reader(file)

        headers = next(reader)

    logger.info(
        f"Headers found: {len(headers)}"
    )

    return headers


# ============================================================
# FILE HASH
# ============================================================

def calculate_file_hash(file_path):

    logger.info(
        f"Calculating file hash: "
        f"{os.path.basename(file_path)}"
    )

    sha256 = hashlib.sha256()

    with open(
        file_path,
        "rb"
    ) as file:

        while True:

            data = file.read(
                1024 * 1024
            )

            if not data:

                break

            sha256.update(
                data
            )

    file_hash = sha256.hexdigest()

    logger.info(
        f"Hash: {file_hash}"
    )

    return file_hash


# ============================================================
# LOAD TRACKER
# ============================================================

def load_tracker():

    logger.info(
        f"Loading tracker: {TRACKER_FILE}"
    )

    if not os.path.exists(
        TRACKER_FILE
    ):

        logger.info(
            "Tracker does not exist. "
            "Starting with empty tracker."
        )

        return {}

    try:

        with open(
            TRACKER_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            tracker = json.load(
                file
            )

        logger.info(
            f"Tracker loaded. "
            f"Entries: {len(tracker)}"
        )

        return tracker

    except (
        json.JSONDecodeError,
        OSError
    ) as error:

        logger.info(
            f"WARNING: Could not read tracker: "
            f"{error}"
        )

        return {}


# ============================================================
# SAVE TRACKER
# ============================================================

def save_tracker(tracker):

    logger.info(
        f"Saving tracker: {TRACKER_FILE}"
    )

    with open(
        TRACKER_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            tracker,
            file,
            indent=4
        )

    logger.info(
        "Tracker saved successfully."
    )


# ============================================================
# CREATE TABLE
# ============================================================

def create_table(
    connection,
    table_name,
    headers
):

    logger.info(
        f"Creating/checking table: "
        f"{table_name}"
    )

    columns = []

    for header in headers:

        header = header.strip()

        if not header:

            header = "unknown_column"

        columns.append(
            f'"{header}" TEXT'
        )

    columns_sql = ", ".join(
        columns
    )

    query = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            {columns_sql}
        );
    """

    with connection.cursor() as cursor:

        cursor.execute(
            query
        )

    connection.commit()

    logger.info(
        f"Table ready: {table_name}"
    )


# ============================================================
# TRUNCATE TABLE
# ============================================================

def truncate_table(
    connection,
    table_name
):

    logger.info(
        f"Truncating table: {table_name}"
    )

    query = (
        f'TRUNCATE TABLE "{table_name}";'
    )

    with connection.cursor() as cursor:

        cursor.execute(
            query
        )

    connection.commit()

    logger.info(
        f"Table truncated: {table_name}"
    )


# ============================================================
# BULK INSERT
# ============================================================

def bulk_insert_csv(
    connection,
    table_name,
    csv_file
):

    logger.info(
        f"Starting bulk insert: "
        f"{os.path.basename(csv_file)}"
    )

    query = f"""
        COPY "{table_name}"
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE
        );
    """

    with connection.cursor() as cursor:

        with open(
            csv_file,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as file:

            with cursor.copy(
                query
            ) as copy:

                while True:

                    data = file.read(
                        1024 * 1024
                    )

                    if not data:

                        break

                    copy.write(
                        data
                    )

    connection.commit()

    logger.info(
        f"Bulk insert completed: "
        f"{os.path.basename(csv_file)}"
    )


# ============================================================
# UPLOAD ONE CSV
# ============================================================

def upload_csv_file(
    connection,
    csv_file,
    tracker
):

    file_name = os.path.basename(
        csv_file
    )

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Processing file: {file_name}")
    logger.info("=" * 70)

    # --------------------------------------------------------
    # 1. Get date from filename
    # --------------------------------------------------------

    file_date = get_file_date(
        file_name
    )

    if file_date is None:

        logger.info(
            "ERROR: File date could not be "
            "determined."
        )

        logger.info(
            "Skipping file."
        )

        return

    # --------------------------------------------------------
    # 2. Get report key
    # --------------------------------------------------------

    report_key = get_report_key(
        file_name
    )

    logger.info(
        f"Report key: {report_key}"
    )

    # --------------------------------------------------------
    # 3. Get table name
    # --------------------------------------------------------

    table_name = get_table_name(
        file_name
    )

    logger.info(
        f"Table name: {table_name}"
    )

    # --------------------------------------------------------
    # 4. Calculate hash
    # --------------------------------------------------------

    file_hash = calculate_file_hash(
        csv_file
    )

    # --------------------------------------------------------
    # 5. Check tracker
    # --------------------------------------------------------

    previous_data = tracker.get(
        report_key
    )

    if previous_data:

        previous_file_name = (
            previous_data.get(
                "file_name"
            )
        )

        previous_date_string = (
            previous_data.get(
                "file_date"
            )
        )

        previous_hash = (
            previous_data.get(
                "hash"
            )
        )

        logger.info(
            f"Previous file: "
            f"{previous_file_name}"
        )

        logger.info(
            f"Previous date: "
            f"{previous_date_string}"
        )

        logger.info(
            f"Current date: "
            f"{file_date}"
        )

        # ----------------------------------------------------
        # Convert previous date
        # ----------------------------------------------------

        previous_date = None

        if previous_date_string:

            try:

                previous_date = datetime.strptime(
                    previous_date_string,
                    "%Y-%m-%d"
                ).date()

            except ValueError:

                logger.info(
                    "WARNING: Invalid previous "
                    "date in tracker."
                )

        # ----------------------------------------------------
        # DATE COMPARISON
        # ----------------------------------------------------

        if previous_date:

            if file_date < previous_date:

                logger.info(
                    "OLD FILE DETECTED"
                )

                logger.info(
                    f"Current : {file_date}"
                )

                logger.info(
                    f"Previous: {previous_date}"
                )

                logger.info(
                    "Skipping older file."
                )

                return

            elif file_date == previous_date:

                logger.info(
                    "Same trading date detected."
                )

                # Same date + same hash
                if previous_hash == file_hash:

                    logger.info(
                        "Same file hash detected."
                    )

                    logger.info(
                        "File already uploaded. "
                        "Skipping."
                    )

                    return

                logger.info(
                    "Same date but file content "
                    "has changed."
                )

                logger.info(
                    "File will be re-uploaded."
                )

            elif file_date > previous_date:

                logger.info(
                    "NEWER FILE DETECTED."
                )

                logger.info(
                    f"Current : {file_date}"
                )

                logger.info(
                    f"Previous: {previous_date}"
                )

                logger.info(
                    "Proceeding with upload."
                )

    else:

        logger.info(
            "No previous tracker entry found."
        )

        logger.info(
            "This is the first upload "
            f"for report: {report_key}"
        )

    # --------------------------------------------------------
    # 6. Read headers
    # --------------------------------------------------------

    headers = get_csv_headers(
        csv_file
    )

    logger.info(
        f"Column count: {len(headers)}"
    )

    # --------------------------------------------------------
    # 7. Create table
    # --------------------------------------------------------

    create_table(
        connection,
        table_name,
        headers
    )

    # --------------------------------------------------------
    # 8. Truncate current date table
    #
    # Important:
    # We are NOT deleting another date's table.
    #
    # Each filename still gets its own table.
    # --------------------------------------------------------

    truncate_table(
        connection,
        table_name
    )

    # --------------------------------------------------------
    # 9. Bulk insert
    # --------------------------------------------------------

    try:

        bulk_insert_csv(
            connection,
            table_name,
            csv_file
        )

        # ----------------------------------------------------
        # 10. Update tracker
        # ----------------------------------------------------

        tracker[report_key] = {

            "file_name": file_name,

            "file_date":
                file_date.isoformat(),

            "table_name":
                table_name,

            "hash":
                file_hash,

            "uploaded_at":
                datetime.now().isoformat()
        }

        save_tracker(
            tracker
        )

        logger.info(
            "Upload successful."
        )

        logger.info(
            f"Latest date stored: "
            f"{file_date}"
        )

    except Exception as error:

        connection.rollback()

        logger.info(
            f"UPLOAD FAILED: {error}"
        )

        raise


# ============================================================
# UPLOAD ALL CSV FILES
# ============================================================

def upload_all_csv_files():

    logger.info("")
    logger.info("=" * 70)
    logger.info("STARTING DATABASE UPLOAD")
    logger.info("=" * 70)

    tracker = load_tracker()

    logger.info(
        f"Scanning directory: "
        f"{FINAL_FILES_DIR}"
    )

    connection = get_connection()

    try:

        for root, directories, files in os.walk(
            FINAL_FILES_DIR
        ):

            for file_name in files:

                if not file_name.lower().endswith(
                    ".csv"
                ):

                    continue

                csv_file = os.path.join(
                    root,
                    file_name
                )

                try:

                    upload_csv_file(
                        connection,
                        csv_file,
                        tracker
                    )

                except Exception as error:

                    connection.rollback()

                    logger.info(
                        f"FAILED: {file_name}"
                    )

                    logger.info(
                        f"ERROR: {error}"
                    )

    finally:

        connection.close()

        logger.info("")
        logger.info(
            "=" * 70
        )

        logger.info(
            "DATABASE CONNECTION CLOSED"
        )

        logger.info(
            "DATABASE UPLOAD COMPLETED"
        )

        logger.info(
            "=" * 70
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    upload_all_csv_files()