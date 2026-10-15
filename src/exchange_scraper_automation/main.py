# main.py

from __future__ import annotations

import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from exchange_scraper_automation.config.config import Config
from exchange_scraper_automation.scraper_utilities.bse.scrape_bse import scrape_bse
from exchange_scraper_automation.scraper_utilities.connect_with_db import get_connection
from exchange_scraper_automation.scraper_utilities.db_operations import (
    update_task_status,
    upload_csv_file,
)
from exchange_scraper_automation.scraper_utilities.file_operations import post_process
from exchange_scraper_automation.scraper_utilities.file_transfer import (
    download_task_file,
)
from exchange_scraper_automation.scraper_utilities.logger import Logger
from exchange_scraper_automation.scraper_utilities.nse.scrape_nse import scrape_nse


class TaskProcessor:
    """Fetch, dispatch, and update scheduled tasks."""

    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def parse_task_details(task: dict[str, Any]) -> dict[str, Any]:
        """Return tasktypedetails as a dictionary."""
        details = task.get("tasktypedetails")

        if isinstance(details, str):
            details = json.loads(details)

        if not isinstance(details, dict):
            raise ValueError(f"Invalid tasktypedetails: TaskID={task.get('taskid')}")

        if str(task.get("tasktype") or "").strip().upper() == "INSERTLOAD_DATA":
            return details

        protocol = details.get("protocol")
        if not isinstance(protocol, str) or not protocol.strip():
            raise ValueError(
                f"Missing protocol in tasktypedetails: TaskID={task.get('taskid')}"
            )

        details["protocol"] = protocol.strip().lower()
        return details

    def get_due_tasks(self, connection: Any) -> list[dict[str, Any]]:
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

    def insert_task(
        self,
        task: dict[str, Any],
        task_details: dict[str, Any],
        connection: Any,
    ) -> dict[str, bool]:
        """Upload a CSV file to the configured database table."""

        filepath = task_details.get("filepath")
        table_name = task_details.get("tablename")

        if not filepath:
            raise ValueError(f"Missing filepath: TaskID={task.get('taskid')}")

        if not table_name:
            raise ValueError(f"Missing tablename: TaskID={task.get('taskid')}")

        final_data_dir = Path(__file__).resolve().parent / "final_data"
        csv_filename = Path(filepath).expanduser().name
        csv_file = final_data_dir / csv_filename

        if not csv_file.is_file():
            raise FileNotFoundError(
                f"CSV file not found: {csv_file} | " f"TaskID={task.get('taskid')}"
            )

        Logger.info(
            f"Starting database upload | "
            f"TaskID={task.get('taskid')} | "
            f"File={csv_file} | Table={table_name}"
        )

        result = upload_csv_file(
            connection=connection,
            csv_file=str(csv_file),
            table_name=table_name,
        )

        if result == "UPLOADED":
            Logger.info(f"Database upload completed | " f"TaskID={task.get('taskid')}")
            return {"success": True}

        Logger.warning(
            f"Database upload failed | "
            f"TaskID={task.get('taskid')} | "
            f"Result={result}"
        )
        return {"success": False}

    def process_url_download(
        self,
        task: dict[str, Any],
        alias_name: str,
        connection: Any,
    ) -> dict[str, Any] | None:
        """Route URL-based downloads to the exchange-specific scraper."""
        if "NSE" in alias_name.upper():
            return scrape_nse(
                task=task,
                config=self.config,
                connection=connection,
            )

        if "BSE" in alias_name.upper():
            return scrape_bse(
                task=task,
                config=self.config,
                logger=Logger,
                connection=connection,
            )

        Logger.warning(
            f"Skipping URL task: exchange is not supported | "
            f"TaskID={task.get('taskid')} | Alias={alias_name}"
        )
        return None

    def process_transfer_download(
        self,
        task: dict[str, Any],
        task_details: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Download an FTP/SFTP file, then run the existing post-processing.

        `local_filename` is the downloaded file's name, so its extension must
        match the downloaded content (for example, .zip or .csv.gz). The final
        CSV name is produced by the existing post_process() logic.
        """
        downloaded_file = download_task_file(task_details)

        final_files_dir = (
            task_details.get("final_files_dir")
            or task_details.get("filepath")
            or task_details.get("local_path")
        )
        if not final_files_dir:
            raise ValueError(
                "Missing final_files_dir (or filepath/local_path) for "
                f"FTP/SFTP post-processing. TaskID={task.get('taskid')}"
            )

        selected_file = task_details.get("file_to_pick") or "all"

        processed_result = post_process(
            file_path=str(downloaded_file),
            final_files_dir=str(Path(final_files_dir).expanduser()),
            logger=Logger,
            headers=task_details.get("headers"),
            selected_file=selected_file,
            table_name=task_details.get("tablename"),
            skip_rows=int(task_details.get("skip_rows", 0)),
            config=self.config,
        )

        Logger.info(
            f"FTP/SFTP download and post-processing completed | "
            f"TaskID={task.get('taskid')} | Downloaded={downloaded_file} | "
            f"Processed={processed_result}"
        )
        return {
            "success": True,
            "downloaded_file": str(downloaded_file),
            "processed_file": str(processed_result),
        }

    def dispatch_task(
        self,
        task: dict[str, Any],
        connection: Any,
    ) -> dict[str, Any] | None:
        """Dispatch tasks by type first, then by protocol for downloads."""

        task_id = task.get("taskid")
        alias_name = str(task.get("aliasname") or "")
        task_type = str(task.get("tasktype") or "").strip().upper()

        task_details = self.parse_task_details(task)

        Logger.info(
            f"Dispatching task | TaskID={task_id} | "
            f"TaskType={task_type} | Alias={alias_name}"
        )

        # Decide the operation using task type first.
        match task_type:
            case "INSERTLOAD_DATA":
                # return
                return self.insert_task(
                    task=task,
                    task_details=task_details,
                    connection=connection,
                )

            case "DOWN":
                protocol = task_details["protocol"]

                Logger.info(
                    f"Download protocol selected | "
                    f"TaskID={task_id} | Protocol={protocol}"
                )

                match protocol:
                    case "url":
                        return self.process_url_download(
                            task=task,
                            alias_name=alias_name,
                            connection=connection,
                        )

                    case "ftp" | "sftp":
                        return self.process_transfer_download(
                            task=task,
                            task_details=task_details,
                        )

                    case _:
                        Logger.warning(
                            f"Unsupported download protocol | "
                            f"TaskID={task_id} | Protocol={protocol}"
                        )
                        return None

            case _:
                Logger.warning(
                    f"Unsupported task type | TaskID={task_id} | "
                    f"TaskType={task_type}"
                )
                return None

    def process_tasks(self, connection: Any) -> None:
        """Run due tasks and mark successful tasks as completed."""
        Logger.info("=" * 70)
        Logger.info("TASK WORKER STARTED")
        Logger.info("=" * 70)

        # connection = get_connection(self.config)
        try:
            tasks = self.get_due_tasks(connection)
            if not tasks:
                Logger.info("No due tasks found.")
                return

            # connection = get_connection(self.config)

            for task in tasks:
                task_id = task.get("taskid")
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
                        f"Failed to process task {task_id}: {error}\n"
                        f"{traceback.format_exc()}"
                    )

        except Exception as error:
            Logger.error(f"Task worker failed: {error}\n{traceback.format_exc()}")
        # finally:
        #     if connection is not None:
        #         connection.close()

            Logger.info("=" * 70)
            Logger.info("TASK WORKER FINISHED")
            Logger.info("=" * 70)


class TaskApplication:
    """Own the worker lifecycle and HTTP trigger listener."""

    def __init__(self, config: Config):
        self.config = config
        self.processor = TaskProcessor(config)
        self.worker_lock = threading.Lock()
        self.connection: Any = None

    def start_worker(self) -> bool:
        """Start one background worker, ignoring overlapping triggers."""
        if not self.worker_lock.acquire(blocking=False):
            Logger.info("Worker is already running. Ignoring new trigger.")
            return False

        def worker() -> None:
            try:
                self.processor.process_tasks(self.connection)
            finally:
                self.worker_lock.release()

        thread = threading.Thread(
            target=worker,
            name="TaskWorker",
            daemon=True,
        )
        thread.start()
        Logger.info("Task worker thread started.")
        return True

    def start_listener(self) -> None:
        """Start the HTTP listener exposing /trigger and /health."""
        application = self

        class TriggerRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/trigger":
                    self.send_response(404)
                    self.end_headers()
                    return

                Logger.info("Trigger received: POST /trigger")
                application.start_worker()

                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {
                    "status": "accepted",
                    "message": "Task processing started",
                }
                self.wfile.write(json.dumps(response).encode("utf-8"))

            def do_GET(self) -> None:
                if self.path != "/health":
                    self.send_response(404)
                    self.end_headers()
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "running"}).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:
                # The application logger handles request-related messages.
                return

        host = self.config.get_server_host()
        port = self.config.get_server_port()
        self.connection = get_connection(self.config)
        server = ThreadingHTTPServer((host, port), TriggerRequestHandler)

        Logger.info("=" * 70)
        Logger.info("TASK LISTENER STARTED")
        Logger.info(f"Host: {host}")
        Logger.info(f"Port: {port}")
        Logger.info("Trigger endpoint: POST /trigger")
        Logger.info("Health endpoint: GET /health")
        Logger.info("=" * 70)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            Logger.info("Listener shutdown requested.")
        finally:
            server.server_close()
            Logger.info("Task listener stopped.")


def main() -> None:
    """Application entry point."""
    config = Config()
    config_file = Path(__file__).resolve().parent / "config" / "config.ini"

    if not config.load(str(config_file)):
        print("Failed to load configuration")
        raise SystemExit(1)

    Logger.configure(config)
    Logger.info("=" * 70)
    Logger.info("EXCHANGE SCRAPER AUTOMATION STARTING")
    Logger.info("=" * 70)

    application = TaskApplication(config)
    application.start_listener()


if __name__ == "__main__":
    main()
