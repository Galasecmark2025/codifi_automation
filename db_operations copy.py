import os, csv, re, json, hashlib
from datetime import datetime
from connect_with_db import get_connection


FINAL_FILES_DIR = "final_files"
TRACKER_FILE = "file_tracker.json"


def get_table_name(file_name):

    table_name = os.path.splitext(file_name)[0]

    table_name = table_name.lower()

    table_name = re.sub(r"[^a-zA-Z0-9_]","_",table_name)

    if table_name[0].isdigit():
        table_name = "table_" + table_name

    return table_name


def get_csv_headers(csv_file):

    with open(csv_file, "r", encoding="utf-8", errors="replace") as file:
        reader = csv.reader(file)
        headers = next(reader)

    return headers

def calculate_file_hash(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while True:
            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


def load_tracker():
    if not os.path.exists(TRACKER_FILE):
        return {}

    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return {}


def save_tracker(tracker):
    with open(TRACKER_FILE, "w", encoding="utf-8") as file:
        json.dump(tracker, file, indent=4)


def truncate_table(connection, table_name):
    query = f'TRUNCATE TABLE "{table_name}";'

    with connection.cursor() as cursor:
        cursor.execute(query)

    connection.commit()

    print(f"Truncated   : {table_name}")


def create_table(connection, table_name, headers):
    columns = []
    for header in headers:
        header = header.strip()
        if not header:
            header = "unknown_column"

        columns.append(f'"{header}" TEXT')

    columns_sql = ", ".join(columns)

    query = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            {columns_sql}
        );
    """

    with connection.cursor() as cursor:
        cursor.execute(query)

    connection.commit()
    print(f"Table ready : {table_name}")


def bulk_insert_csv(connection,table_name,csv_file):

    query = f"""
        COPY "{table_name}"
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE
        );
    """

    with connection.cursor() as cursor:

        with open(csv_file, "r", encoding="utf-8", errors="replace") as file:

            with cursor.copy(query) as copy:
                while True:
                    data = file.read(1024 * 1024)

                    if not data: break

                    copy.write(data)

    connection.commit()

    print(f"Uploaded    : {os.path.basename(csv_file)}")


def upload_csv_file(connection, csv_file, tracker):

    file_name = os.path.basename(csv_file)

    table_name = get_table_name(file_name)

    print("\n--------------------------------")
    print("File  :", file_name)
    print("Table :", table_name)

    # Calculate hash of current file
    file_hash = calculate_file_hash(csv_file)

    # Check whether this exact file was already uploaded
    previous_file = tracker.get(table_name)

    if previous_file and previous_file.get("hash") == file_hash:
        print("Already uploaded. Skipping.")
        return

    headers = get_csv_headers(csv_file)

    print("Columns:", len(headers))

    # Create table if it does not exist
    create_table(connection, table_name, headers)

    # New/changed file found:
    # remove old data before inserting new data
    truncate_table(connection, table_name)

    try:

        bulk_insert_csv(
            connection,
            table_name,
            csv_file
        )

        # Update tracker ONLY after successful upload
        tracker[table_name] = {
            "file_name": file_name,
            "hash": file_hash,
            "uploaded_at": datetime.now().isoformat()
        }

        save_tracker(tracker)

        print("Tracker updated.")

    except Exception:
        connection.rollback()
        raise

def upload_all_csv_files():
    tracker = load_tracker()

    connection = get_connection()

    try:
        for root, directories, files in os.walk(FINAL_FILES_DIR):
            for file_name in files:
                if not file_name.lower().endswith(".csv"):
                    continue

                csv_file = os.path.join(root,file_name)

                try:
                    upload_csv_file(connection,csv_file,tracker)

                except Exception as error:
                    connection.rollback()
                    print(f"\nFailed : {file_name}")
                    print(f"Error  : {error}")

    finally:
        connection.close()
        print("\nDatabase connection closed.")


# if __name__ == "__main__":
#     upload_all_csv_files()