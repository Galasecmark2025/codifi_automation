"""HTTP trigger listener and background task-worker lifecycle."""

from __future__ import annotations

import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from exchange_scraper_automation.application.task_processor import TaskProcessor
from exchange_scraper_automation.config import Config
from exchange_scraper_automation.database.connection import get_connection
from exchange_scraper_automation.observability.logger import Logger


class TaskApplication:
    """Own the worker lifecycle and HTTP trigger listener."""

    def __init__(self, config: Config):
        self.config = config
        self.processor = TaskProcessor(config)
        self.worker_lock = threading.Lock()

    def start_worker(self) -> bool:
        """Start one background worker, ignoring overlapping triggers."""
        if not self.worker_lock.acquire(blocking=False):
            Logger.info("Worker is already running. Ignoring new trigger.")
            return False

        def worker() -> None:
            connection = None
            try:
                connection = get_connection(self.config)
                connection = self.processor.process_tasks(connection)

            except Exception:
                Logger.error(
                    f"Task worker terminated unexpectedly.\n"
                    f"{traceback.format_exc()}"
                )

            finally:
                if connection is not None:
                    try:
                        connection.close()
                        Logger.info("Worker database connection closed.")
                    except Exception:
                        Logger.error(
                            f"Failed to close worker database connection.\n"
                            f"{traceback.format_exc()}"
                        )

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
                started = application.start_worker()

                if started:
                    status_code = 202
                    response = {
                        "status": "accepted",
                        "message": "Task processing started",
                    }
                else:
                    status_code = 409
                    response = {
                        "status": "conflict",
                        "message": "Task processing is already running",
                    }

                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

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
        # self.connection = get_connection(self.config)
        server = ThreadingHTTPServer((host, port), TriggerRequestHandler)

        Logger.info(
            f"{'=' * 70}\n"
            "TASK LISTENER STARTED\n"
            f"Host: {host}\n"
            f"Port: {port}\n"
            "Trigger endpoint: POST /trigger\n"
            "Health endpoint: GET /health\n"
            f"{'=' * 70}"
        )

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            Logger.info("Listener shutdown requested.")
        finally:
            server.server_close()
            Logger.info("Task listener stopped.")
