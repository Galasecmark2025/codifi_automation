# main.py

from __future__ import annotations

import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import glob, re
import glob
import gzip
import shutil
import tempfile
import fnmatch

from psycopg.rows import dict_row

from exchange_scraper_automation.config import Config
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
from exchange_scraper_automation.scraper_utilities.resolve_output_filename import resolve_output_filename


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


def resolve_data_path(configured_path: str | Path) -> Path:
    """Resolve configured local paths relative to the project's data directory."""
    raw_path = str(configured_path).strip()

    if not raw_path:
        raise ValueError("Configured data path cannot be empty.")

    path = Path(raw_path).expanduser()

    # Relative paths such as NSE/CM -> project/data/NSE/CM
    if not path.is_absolute():
        if path.parts and path.parts[0].lower() == "data":
            return PROJECT_ROOT / path

        if path.parts and path.parts[0].lower() == "final_data":
            return DATA_ROOT.joinpath(*path.parts[1:])

        return DATA_ROOT / path

    # Keep paths already under the new data directory.
    try:
        path.relative_to(DATA_ROOT)
        return path
    except ValueError:
        pass

    # Support old absolute paths inside this project.
    try:
        project_relative_path = path.relative_to(PROJECT_ROOT)
    except ValueError:
        project_relative_path = None

    if project_relative_path is not None:
        parts = project_relative_path.parts

        if parts and parts[0].lower() == "data":
            return path

        if parts and parts[0].lower() == "final_data":
            return DATA_ROOT.joinpath(*parts[1:])

    # Treat configured paths such as /NSE/CM and /data/MCX
    # as logical paths under the project's data directory.
    parts = path.parts[1:]

    if parts and parts[0].lower() in {"data", "final_data"}:
        parts = parts[1:]

    return DATA_ROOT.joinpath(*parts)



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
            raise ValueError(f"Missing protocol in tasktypedetails: TaskID={task.get('taskid')}")

        details["protocol"] = protocol.strip().lower()
        return details

    
    def prepare_local_directories(self, task: dict[str, Any], task_details: dict[str, Any], ) -> tuple[Path, Path]:
        """Resolve and create download and final-output directories."""

        task_id = task.get("taskid")
        configured_local_path = task_details.get("local_path")

        if not configured_local_path:
            raise ValueError(
                f"Missing local_path in download configuration | "
                f"TaskID={task_id}"
            )

        download_dir = resolve_data_path(configured_local_path)

        configured_final_path = (task_details.get("final_files_dir") or configured_local_path)
        # final_files_dir = resolve_data_path(configured_final_path)
        final_files_dir = download_dir

        try:
            download_dir.mkdir(parents=True, exist_ok=True)
            final_files_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OSError(
                f"Unable to create download/output directories | "
                f"TaskID={task_id} | "
                f"DownloadDir={download_dir} | "
                f"FinalDir={final_files_dir}"
            ) from error

        if not download_dir.is_dir():
            raise NotADirectoryError(f"Download path is not a directory: {download_dir}")

        if not final_files_dir.is_dir():
            raise NotADirectoryError(f"Output path is not a directory: {final_files_dir}")

        # Store resolved paths so the downloader and scraper use the same values.
        task_details["local_path"] = str(download_dir)
        task_details["final_files_dir"] = str(final_files_dir)

        # Important: the scraper must receive the updated dictionary, even
        # when tasktypedetails originally arrived as a JSON string.
        task["tasktypedetails"] = task_details

        Logger.info(
            f"Local directories ready | "
            f"TaskID={task_id} | "
            f"DownloadDir={download_dir} | "
            f"FinalDir={final_files_dir}"
        )

        return download_dir, final_files_dir


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

        # Resolve the configured filepath against the project's data directory.
        raw_filepath = str(filepath).strip()
        resolved_filepath = resolve_data_path(raw_filepath)

        # Remove accidental backslashes before wildcards or underscores.
        filename_pattern = resolved_filepath.name.replace("\\", "")

        # Use the exchange/segment directory resolved from the configured filepath.
        final_data_dir = resolved_filepath.parent

        if not final_data_dir.is_dir():
            raise FileNotFoundError(
                f"Data directory does not exist: {final_data_dir}"
            )
        

        def find_matching_files(pattern: str) -> list[Path]:
            return [
                Path(match)
                for match in glob.glob(str(final_data_dir / pattern))
                if Path(match).is_file()
                # Ignore literal placeholder filenames containing wildcards.
                and not any(
                    char in Path(match).name
                    for char in "*?["
                )
            ]

        # First, look for the exact requested pattern.
        matched_pattern = filename_pattern
        matches = find_matching_files(matched_pattern)

        # If *.csv has no real matches, also try *.csv.gz.
        # This handles dated files such as NSE_FO_contract_22092026.csv.gz.
        if not matches and filename_pattern.endswith(".csv"):
            matched_pattern = filename_pattern + ".gz"
            matches = find_matching_files(matched_pattern)

        Logger.info(
            f"File pattern resolution | "
            f"TaskID={task.get('taskid')} | "
            f"Original={raw_filepath!r} | "
            f"Normalized={filename_pattern!r} | "
            f"MatchedPattern={matched_pattern!r} | "
            f"Directory={str(final_data_dir)!r} | "
            f"Matches={[str(path) for path in matches]}"
        )

        if not matches:
            raise FileNotFoundError(
                f"No file matched pattern | "
                f"TaskID={task.get('taskid')} | "
                f"Pattern={filename_pattern!r} | "
                f"Directory={str(final_data_dir)!r}"
            )

        # Choose the most recently modified matching file.
        source_file = max(
            matches,
            key=lambda path: path.stat().st_mtime,
        )

        # The upload function expects an uncompressed CSV.
        csv_file = source_file
        temporary_csv = None

        if source_file.name.endswith(".csv.gz"):
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".csv",
                prefix="upload_",
                dir=final_data_dir,
                delete=False,
            ) as temp_file:
                temporary_csv = Path(temp_file.name)

            try:
                with gzip.open(source_file, "rb") as compressed_file:
                    with temporary_csv.open("wb") as output_file:
                        shutil.copyfileobj(compressed_file, output_file)

                csv_file = temporary_csv

            except Exception:
                temporary_csv.unlink(missing_ok=True)
                raise

        Logger.info(
            f"Selected file | TaskID={task.get('taskid')} | "
            f"Source={source_file} | UploadFile={csv_file}"
        )


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
        task_details: dict[str, Any],
        alias_name: str,
        connection: Any, ) -> dict[str, Any] | None:
        """Route URL-based downloads to the exchange-specific scraper."""

        self.prepare_local_directories(task=task, task_details=task_details, )
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
        download_dir, final_files_dir = self.prepare_local_directories(task=task, task_details=task_details, )

        downloaded_file = download_task_file(task_details)

        # Validate and create the download destination before downloading.
        # local_path = task_details.get("local_path")
        # if not local_path:
        #     raise ValueError(
        #         f"Missing local_path in download configuration | "
        #         f"TaskID={task.get('taskid')}"
        #     )
        # download_dir = Path(local_path).expanduser()
        # download_dir = resolve_data_path(local_path)
        try:
            download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OSError(
                f"Unable to create download directory: {download_dir} | "
                f"TaskID={task.get('taskid')}"
            ) from error

        if not download_dir.is_dir():
            raise NotADirectoryError(
                f"Download path is not a directory: {download_dir}"
            )

        Logger.info(
            f"Download directory ready | "
            f"TaskID={task.get('taskid')} | "
            f"Directory={download_dir}"
        )

        # Pass the resolved directory to the downloader.
        task_details["local_path"] = str(download_dir)
        downloaded_file = download_task_file(task_details)

        configured_final_dir = task_details.get("final_files_dir")

        final_files_dir = (
            resolve_data_path(configured_final_dir)
            if configured_final_dir
            else download_dir
        )

        final_files_dir.mkdir(parents=True, exist_ok=True)

        selected_file = task_details.get("file_to_pick") or "all"

        resolved_local_filename = resolve_output_filename(
            local_filename=task_details.get("local_filename"),
            downloaded_file=downloaded_file,
        )

        Logger.info(
            f"Resolved output filename | "
            f"TaskID={task.get('taskid')} | "
            f"Downloaded={Path(downloaded_file).name} | "
            f"Output={resolved_local_filename}"
        )

        processed_result = post_process(
            file_path=str(downloaded_file),
            final_files_dir=str(final_files_dir),
            logger=Logger,
            headers=task_details.get("headers"),
            selected_file=selected_file,
            table_name=task_details.get("tablename"),
            skip_rows=int(task_details.get("skip_rows", 0)),
            config=self.config,
            local_filename=resolved_local_filename,
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

    def dispatch_task(self, task: dict[str, Any], connection: Any, ) -> dict[str, Any] | None:
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
                # return
                protocol = task_details["protocol"]

                Logger.info(
                    f"Download protocol selected | "
                    f"TaskID={task_id} | Protocol={protocol}"
                )

                match protocol:
                    case "url":
                        # return
                        return self.process_url_download(
                            task=task,
                            task_details=task_details,
                            alias_name=alias_name,
                            connection=connection,
                        )

                    case "ftp" | "sftp":
                        # return
                        return self.process_transfer_download(task=task, task_details=task_details, )

                    case _:
                        Logger.warning(f"Unsupported download protocol | TaskID={task_id} | Protocol={protocol}")
                        return None

            case _:
                Logger.warning(f"Unsupported task type | TaskID={task_id} | TaskType={task_type}")
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
    # config_file = Path(__file__).resolve().parent / "config" / "config.ini"

    if not config.load():
        print("Failed to load configuration")
        raise SystemExit(1)

    Logger.configure(config)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    Logger.info(f"Data root ready: {DATA_ROOT}")

    Logger.info("=" * 70)
    Logger.info("EXCHANGE SCRAPER AUTOMATION STARTING")
    Logger.info("=" * 70)

    application = TaskApplication(config)
    application.start_listener()


if __name__ == "__main__":
    main()
