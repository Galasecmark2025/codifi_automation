"""Task retrieval, routing, file processing, and task-status updates."""

from __future__ import annotations

import glob
import json
import traceback
from pathlib import Path, PurePosixPath
from typing import Any

import psycopg
from psycopg.rows import dict_row

from exchange_scraper_automation.config import Config
from exchange_scraper_automation.data_paths import resolve_alias_data_path
from exchange_scraper_automation.database.connection import get_connection
from exchange_scraper_automation.database.operations import (
    update_task_status,
    upload_csv_file,
)
from exchange_scraper_automation.exchanges.bse.scrape_bse import scrape_bse
from exchange_scraper_automation.exchanges.nse.scrape_nse import scrape_nse
from exchange_scraper_automation.file_management.file_operations import post_process
from exchange_scraper_automation.models.task import Task
from exchange_scraper_automation.models.task_paths import TaskPaths
from exchange_scraper_automation.observability.logger import Logger
from exchange_scraper_automation.security.secret_manager import SecretManager
from exchange_scraper_automation.transfers.file_transfer import download_task_file


class TaskProcessor:
    """Fetch, dispatch, and update scheduled tasks."""

    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def parse_task_details(task: Task) -> dict[str, Any]:
        """Parse task details only when the task requires them."""

        task_type = str(task.task_type).strip().upper()

        # INSERTLOAD_DATA uses database columns and mapping functions,
        # so it must not depend on tasktypedetails JSON.
        if task_type == "INSERTLOAD_DATA":
            return {}

        details = task.details

        if isinstance(details, str):
            details = json.loads(details)

        if not isinstance(details, dict):
            Logger.error(f"Invalid tasktypedetails: TaskID={task.task_id}")

        protocol = details.get("protocol")
        if not isinstance(protocol, str) or not protocol.strip():
            Logger.error(f"Missing protocol in tasktypedetails: TaskID={task.task_id}")

        details["protocol"] = protocol.strip().lower()
        return details

    def prepare_local_directories(self, task: Task) -> TaskPaths:
        """Resolve and prepare local paths without modifying Task."""

        paths = TaskPaths.from_alias(task.alias_name)

        directory = paths.download_dir
        directory.mkdir(parents=True, exist_ok=True)

        if not directory.is_dir():
            Logger.error(
                f"TaskID={task.task_id}: Invalid directory: {directory}"
            )

        Logger.info(
            f"Local directories ready | "
            f"TaskID={task.task_id} | "
            f"Alias={task.alias_name} | "
            f"DownloadDir={paths.download_dir} | "
        )

        return paths

    def get_due_tasks(self, connection: Any):
        """Call the database function and return due tasks as dictionaries."""

        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT public.stp_get_due_tasks(%s::refcursor);",
                ("due_tasks",),
            )
            cursor.execute("FETCH ALL FROM due_tasks;")
            rows = cursor.fetchall()

        Logger.info(f"Due tasks received from database: {len(rows)}")
        return rows

    def insert_task(self, task: Task, connection: Any):
        """Find the configured local file and upload it to the mapped table."""

        task_id = task.task_id
        alias_name = str(task.alias_name).strip()
        exchange_id = task.exchange_id
        master_type = str(task.master_type).strip().upper()
        raw_filenamepath = str(task.filename_path).strip()

        # -------------------------------------------------
        # VALIDATE REQUIRED DATABASE COLUMNS
        # -------------------------------------------------
        if not alias_name:
            Logger.error(f"Missing aliasname: TaskID={task_id}")

        if exchange_id is None:
            Logger.error(f"Missing exchangeid: TaskID={task_id}")

        if not master_type:
            Logger.error(f"Missing mastertype: TaskID={task_id}")

        if not raw_filenamepath:
            Logger.error(f"Missing filenamepath: TaskID={task_id}")

        # -------------------------------------------------
        # FETCH TABLE MAPPING FROM POSTGRESQL
        # -------------------------------------------------
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT finalfuncname, inputtablename FROM public.fn_get_masterdata_function_info(%s, %s)
                """,
                (exchange_id, master_type),
            )
            mapping = cursor.fetchone()

        if not mapping:
            Logger.error(
                f"No master-data mapping returned | "
                f"TaskID={task_id} | ExchangeID={exchange_id} | MasterType={master_type}"
            )

        table_name = str(mapping.get("inputtablename")).strip()
        final_func_name = str(mapping.get("inputtablename")).strip()

        if not table_name:
            Logger.error(
                f"Mapping has no inputtablename | "
                f"TaskID={task_id} | ExchangeID={exchange_id} | MasterType={master_type}"
            )

        Logger.info(
            f"Master-data mapping resolved | "
            f"TaskID={task_id} | "
            f"ExchangeID={exchange_id} | "
            f"MasterType={master_type} | "
            f"Table={table_name} | "
            f"FinalFunction={final_func_name}"
        )

        # -------------------------------------------------
        # RESOLVE THE LOCAL DIRECTORY FROM ALIASNAME
        # -------------------------------------------------
        final_data_dir = resolve_alias_data_path(alias_name)

        if not final_data_dir.is_dir():
            Logger.error(
                f"Data directory does not exist | "
                f"TaskID={task_id} | Directory={final_data_dir}"
            )

        # -------------------------------------------------
        # CONVERT FILENAMEPATH TO A LOCAL FILE PATTERN
        # -------------------------------------------------
        # The stored value can contain a directory, escaped
        # characters, and date placeholders.
        normalized_path = raw_filenamepath.replace("\\", "")
        filename_pattern = PurePosixPath(normalized_path).name

        if not filename_pattern:
            Logger.error(
                f"Invalid filenamepath | "
                f"TaskID={task_id} | Value={raw_filenamepath!r}"
            )

        # Treat both date placeholders as eight-digit filename
        # sections when searching for downloaded files.
        filename_pattern = filename_pattern.replace("<DDMMYYYY>", "*").replace(
            "<DDMMYY>", "*"
        )

        def find_matching_files(pattern: str) -> list[Path]:
            return [
                Path(match)
                for match in glob.glob(str(final_data_dir / pattern))
                if Path(match).is_file()
            ]

        matched_pattern = filename_pattern
        matches = find_matching_files(matched_pattern)

        # A configured .csv filename can be satisfied by a
        # compressed .csv.gz file if the plain CSV isn't present.
        if not matches and filename_pattern.lower().endswith(".csv"):
            matched_pattern = filename_pattern + ".gz"
            matches = find_matching_files(matched_pattern)

        Logger.info(
            f"File pattern resolution | "
            f"TaskID={task_id} | "
            f"FilenamePath={raw_filenamepath!r} | "
            f"Pattern={matched_pattern!r} | "
            f"Directory={str(final_data_dir)!r} | "
            f"Matches={[str(path) for path in matches]}"
        )

        if not matches:
            Logger.error(
                f"No local file matched filenamepath | "
                f"TaskID={task_id} | "
                f"FilenamePath={raw_filenamepath!r} | "
                f"Pattern={matched_pattern!r} | "
                f"Directory={str(final_data_dir)}"
            )

        # When multiple dated files match, select the newest
        # according to the local file modification time.
        source_file = max(
            matches,
            key=lambda path: path.stat().st_mtime,
        )

        # -------------------------------------------------
        # PREPARE THE CSV FOR UPLOAD
        # -------------------------------------------------
        csv_file = source_file
        temporary_csv = None

        try:
            Logger.info(
                f"Starting database upload | "
                f"TaskID={task_id} | "
                f"Source={source_file} | "
                f"UploadFile={csv_file} | "
                f"Table={table_name}"
            )

            result = upload_csv_file(
                connection=connection,
                csv_file=str(csv_file),
                table_name=table_name,
            )

            if result == "UPLOADED":
                Logger.info(
                    f"Database upload completed | "
                    f"TaskID={task_id} | Table={table_name}"
                )
                return {"success": True}

            Logger.warning(
                f"Database upload failed | "
                f"TaskID={task_id} | "
                f"Table={table_name} | Result={result}"
            )
            return {"success": False}

        finally:
            # Remove the temporary decompressed CSV.
            if temporary_csv is not None:
                temporary_csv.unlink(missing_ok=True)

    def process_url_download(
        self,
        task: Task,
        task_details: dict[str, Any],
        alias_name: str,
        connection: Any,
    ):
        """Route URL-based downloads to the exchange-specific scraper."""

        paths = self.prepare_local_directories(task)

        if "NSE" in task.alias_name.upper():
            return scrape_nse(
                task=task,
                paths=paths,
                config=self.config,
                connection=connection,
            )

        if "BSE" in task.alias_name.upper():
            return scrape_bse(
                task=task,
                config=self.config,
                paths=paths,
                logger=Logger,
                connection=connection,
            )

        Logger.warning(
            f"Skipping URL task: exchange is not supported | "
            f"TaskID={task.task_id} | Alias={task.alias_name}"
        )
        return None

    def process_transfer_download(
        self,
        task: Task,
        task_details: dict[str, Any],
    ):
        """
        Download an FTP/SFTP file, then run the existing post-processing.

        `local_filename` is the downloaded file's name, so its extension must
        match the downloaded content (for example, .zip or .csv.gz). The final
        CSV name is produced by the existing post_process() logic.
        """
        paths = self.prepare_local_directories(task)

        download_dir = paths.download_dir

        try:
            download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            Logger.error(
                f"Unable to create download directory: {download_dir} | TaskID={task.task_id}"
            )

        if not download_dir.is_dir():
            Logger.error(
                f"Download path is not a directory: {download_dir}"
            )

        Logger.info(
            f"Download directory ready | "
            f"TaskID={task.task_id} | "
            f"Directory={download_dir}"
        )

        filenamepath = task.filename_path

        if not filenamepath:
            Logger.error(
                f"Missing filenamepath column in database task | TaskID={task.task_id}"
            )

        secret_manager = SecretManager(self.config.get_sftp_encryption_key())

        downloaded_file = download_task_file(
            task_details,
            destination_dir=download_dir,
            filenamepath=filenamepath,
            secret_manager=secret_manager,
        )

        selected_file = task_details.get("file_to_pick") or "all"

        processed_result = post_process(
            file_path=str(downloaded_file),
            logger=Logger,
            headers=task_details.get("headers"),
            selected_file=selected_file,
            skip_rows=int(task_details.get("skip_rows", 0)),
            config=self.config,
        )

        Logger.info(
            f"FTP/SFTP download and post-processing completed | "
            f"TaskID={task.task_id} | Downloaded={downloaded_file} | "
            f"Processed={processed_result}"
        )
        return {
            "success": True,
            "downloaded_file": str(downloaded_file),
            "processed_file": str(processed_result),
        }

    def dispatch_task(self, task: Task, connection: Any):
        """Dispatch tasks by type first, then by protocol for downloads."""

        task_id = task.task_id
        alias_name = str(task.alias_name)
        task_type = str(task.task_type).strip().upper()

        task_details = self.parse_task_details(task)

        Logger.info(
            f"Dispatching task | TaskID={task_id} | TaskType={task_type} | Alias={alias_name}"
        )

        # Decide the operation using task type first.
        match task_type:
            case "INSERTLOAD_DATA":
                # return
                return self.insert_task(
                    task=task,
                    connection=connection,
                )

            case "DOWN":
                # return
                protocol = task_details["protocol"]

                Logger.info(
                    f"Download protocol selected | TaskID={task_id} | Protocol={protocol}"
                )

                match protocol:
                    case "https":
                        # return
                        return self.process_url_download(
                            task=task,
                            task_details=task_details,
                            alias_name=alias_name,
                            connection=connection,
                        )

                    case "sftp":
                        # return
                        return self.process_transfer_download(
                            task=task,
                            task_details=task_details,
                        )

                    case "ftp":
                        # return
                        pass

                    case _:
                        Logger.warning(
                            f"Unsupported download protocol | TaskID={task_id} | Protocol={protocol}"
                        )
                        return None

            case _:
                Logger.warning(
                    f"Unsupported task type | TaskID={task_id} | TaskType={task_type}"
                )
                return None

    def process_tasks(self, connection: Any):
        """Process due tasks and return the active database connection."""
        Logger.info(
            f"{'=' * 70}\n"
            "TASK WORKER STARTED\n"
            f"{'=' * 70}"
        )

        try:
            # tasks = self.get_due_tasks(connection)
            rows = self.get_due_tasks(connection)
            tasks = [Task.from_row(row) for row in rows]
            if not tasks:
                Logger.info("No due tasks found.")
            else:
                for task in tasks:
                    task_id = task.task_id
                    try:
                        result = self.dispatch_task(task, connection)

                        if isinstance(result, dict) and result.get("success") is True:
                            update_task_status(
                                connection=connection,
                                task_id=task_id,
                                status="COMPLETED",
                            )
                            Logger.info(f"Task marked COMPLETED: TaskID={task_id}")

                    except Exception as error:
                        Logger.error(
                            f"Task processing failed | "
                            f"TaskID={task.task_id} | "
                            f"ErrorType={type(error).__name__} | "
                            f"Error={error}"
                        )

                        if isinstance(
                            error,
                            (psycopg.OperationalError, psycopg.InterfaceError),
                        ):
                            try:
                                connection = self.reconnect(connection)
                                Logger.info(
                                    f"Database connection recovered | TaskID={task_id}"
                                )
                            except Exception:
                                Logger.error(
                                    f"Database reconnection failed after task error | TaskID={task_id}\n{traceback.format_exc()}"
                                )
                                raise
                        else:
                            try:
                                if not connection.closed:
                                    connection.rollback()
                            except Exception:
                                Logger.error(
                                    f"Database rollback failed | TaskID={task_id}\n"
                                    f"{traceback.format_exc()}"
                                )

        except Exception as error:
            Logger.error(f"Task worker failed: {error}\n{traceback.format_exc()}")
        finally:
            Logger.info(
                f"{'=' * 70}\n"
                "TASK WORKER FINISHED\n"
                f"{'=' * 70}"
            )

        # A reconnect may replace the original connection; return the active one
        # so TaskApplication can close the correct connection when the worker ends.
        return connection

    def reconnect(self, connection):
        if connection is not None:
            try:
                connection.close()
            except Exception:
                Logger.warning("Could not close the previous database connection.")

        Logger.warning("Re-establishing PostgreSQL connection.")
        return get_connection(self.config)
