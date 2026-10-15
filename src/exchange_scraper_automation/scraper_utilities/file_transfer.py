# file_transfer.py

from __future__ import annotations

import fnmatch
import ftplib
import json
import os
import posixpath
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import paramiko

from exchange_scraper_automation.scraper_utilities.logger import Logger


@dataclass(frozen=True)
class TransferConfig:
    """Configuration required to download a file over FTP or SFTP."""

    protocol: str
    hostname: str
    port: int
    userid: str
    password: str
    remote_path: str
    remote_filename: str
    local_path: str
    local_filename: str
    timeout: int = 30

    @classmethod
    def from_dict(cls, data):

        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, dict):
            raise TypeError(f"Expected dict or JSON string, got {type(data).__name__}")

        # Handle task details wrapped in the database column.
        for key in ("tasktypedetails", "task_type_details"):
            if key in data:
                nested = data[key]
                if isinstance(nested, str):
                    nested = json.loads(nested)
                if isinstance(nested, dict):
                    data = nested
                    break

        # Normalize key casing and surrounding whitespace.
        data = {str(key).strip().lower(): value for key, value in data.items()}

        required = (
            "protocol",
            "hostname",
            "userid",
            "password",
            "remote_path",
            "remote_filename",
            "local_path",
            "local_filename",
        )

        missing = [
            key
            for key in required
            if data.get(key) is None or not str(data[key]).strip()
        ]

        if missing:
            raise ValueError(
                f"Missing required transfer configuration fields: {missing}. "
                f"Received keys: {sorted(data.keys())}"
            )

        return cls(
            protocol=data["protocol"],
            hostname=data["hostname"],
            port=int(data.get("port") or 22),
            userid=data["userid"],
            password=data["password"],
            remote_path=data["remote_path"],
            remote_filename=data["remote_filename"],
            local_path=data["local_path"],
            local_filename=data["local_filename"],
            timeout=int(data.get("timeout") or 30),
        )


class RemoteFileDownloader:
    """
    Download a remote file unchanged over FTP/SFTP.

    Archive extraction and file selection are deliberately not handled here.
    Those operations belong to the existing file_operations.post_process()
    workflow. Extra task fields such as `file_to_pick` are therefore ignored.
    """

    def __init__(self, config: TransferConfig):
        self.config = config

    def download(self) -> Path:
        """Download the latest remote file matching the configured pattern."""

        cfg = self.config
        destination_dir = Path(cfg.local_path).expanduser()
        destination_dir.mkdir(parents=True, exist_ok=True)

        remote_pattern = self._expand_date_pattern(cfg.remote_filename)
        remote_dir = cfg.remote_path.rstrip("/") or "/"

        Logger.info(
            f"Searching remote files | Protocol={cfg.protocol.upper()} | "
            f"Host={cfg.hostname} | Directory={remote_dir} | "
            f"Pattern={remote_pattern}"
        )

        try:
            remote_filename = self._find_remote_file(
                remote_dir,
                remote_pattern,
            )

            # Preserve the selected remote filename locally.
            local_filename = remote_filename

            final_path = destination_dir / local_filename
            remote_file_path = posixpath.join(remote_dir, remote_filename)

            self._validate_remote_path(remote_file_path)

            Logger.info(
                f"Selected remote file | Remote={remote_file_path} | "
                f"Local={final_path}"
            )

            self._download_remote_file(remote_file_path, final_path)

            Logger.info(
                f"Download completed successfully | "
                f"Local={final_path} | Size={final_path.stat().st_size} bytes"
            )

            return final_path

        except Exception as error:
            Logger.error(
                f"Download failed | Protocol={cfg.protocol.upper()} | "
                f"Directory={remote_dir} | Pattern={remote_pattern} | "
                f"Error={error}\n{traceback.format_exc()}"
            )
            raise

    @staticmethod
    def _expand_date_pattern(filename: str) -> str:
        """Expand strftime placeholders such as %Y%m%d."""

        return datetime.now().strftime(filename)

    @staticmethod
    def _validate_remote_path(remote_path: str) -> None:
        """Reject a remote path that does not identify a file."""

        if not remote_path or remote_path.endswith("/"):
            raise ValueError(f"remote_filename must identify a file: {remote_path}")

    def _download_remote_file(
        self,
        remote_file_path: str,
        destination: Path,
    ) -> None:
        """Download to a temporary file and atomically replace the destination."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
        )
        os.close(fd)
        temporary_path = Path(temporary_name)

        try:
            if self.config.protocol == "sftp":
                self._download_sftp(remote_file_path, temporary_path)
            else:
                self._download_ftp(remote_file_path, temporary_path)

            if not temporary_path.is_file():
                raise OSError("Download did not produce a local file.")

            os.replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _find_remote_file(
        self,
        remote_dir: str,
        filename_pattern: str,
    ) -> str:
        """Return the newest remote filename matching the configured pattern."""

        cfg = self.config

        if cfg.protocol.lower() == "sftp":
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

            try:
                client.connect(
                    hostname=cfg.hostname,
                    port=cfg.port,
                    username=cfg.userid,
                    password=cfg.password,
                    timeout=cfg.timeout,
                    banner_timeout=cfg.timeout,
                    auth_timeout=cfg.timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )

                with client.open_sftp() as sftp:
                    entries = sftp.listdir_attr(remote_dir)

            finally:
                client.close()

        elif cfg.protocol.lower() == "ftp":
            with ftplib.FTP() as ftp:
                ftp.connect(
                    host=cfg.hostname,
                    port=cfg.port,
                    timeout=cfg.timeout,
                )
                ftp.login(cfg.userid, cfg.password)
                ftp.set_pasv(True)

                entries = []
                for name, facts in ftp.mlsd(remote_dir):
                    if facts.get("type") == "file":
                        entries.append(
                            SimpleNamespace(
                                filename=name,
                                st_mtime=0,
                                st_mode=0,
                            )
                        )

        else:
            raise ValueError(f"Unsupported transfer protocol: {cfg.protocol}")

        matches = [
            entry
            for entry in entries
            if fnmatch.fnmatchcase(entry.filename, filename_pattern)
            and not (
                getattr(entry, "st_mode", 0)
                and not __import__("stat").S_ISREG(entry.st_mode)
            )
        ]

        if not matches:
            raise FileNotFoundError(
                f"No files matching {filename_pattern!r} "
                f"found in remote directory {remote_dir!r}"
            )

        selected = max(
            matches,
            key=lambda entry: getattr(entry, "st_mtime", 0),
        )

        return selected.filename

    def _download_sftp(
        self,
        remote_file_path: str,
        destination: Path,
    ) -> None:
        """
        Download using SFTP with SSH host-key verification.

        The server's host key must already be trusted in the user's system
        known_hosts file (for example, ~/.ssh/known_hosts). Unknown host keys
        are rejected instead of being trusted automatically.
        """

        cfg = self.config
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        try:
            client.connect(
                hostname=cfg.hostname,
                port=cfg.port,
                username=cfg.userid,
                password=cfg.password,
                timeout=cfg.timeout,
                banner_timeout=cfg.timeout,
                auth_timeout=cfg.timeout,
                look_for_keys=False,
                allow_agent=False,
            )

            with client.open_sftp() as sftp:
                sftp.get(remote_file_path, str(destination))
        finally:
            client.close()

    def _download_ftp(
        self,
        remote_file_path: str,
        destination: Path,
    ) -> None:
        """Download using FTP passive mode."""

        cfg = self.config
        ftp = ftplib.FTP()

        try:
            ftp.connect(
                host=cfg.hostname,
                port=cfg.port,
                timeout=cfg.timeout,
            )
            ftp.login(cfg.userid, cfg.password)
            ftp.set_pasv(True)

            with destination.open("wb") as output_file:
                ftp.retrbinary(
                    f"RETR {remote_file_path}",
                    output_file.write,
                )
        finally:
            try:
                if ftp.sock is not None:
                    ftp.quit()
            except (ftplib.all_errors, OSError):
                ftp.close()


def download_task_file(task_details: dict) -> Path:
    """
    Public entry point for FTP/SFTP downloads.

    Accepts the full task configuration dictionary. Fields used only by later
    processing, such as `file_to_pick`, remain in `task_details` for the caller
    and are not interpreted by this downloader.
    """

    config = TransferConfig.from_dict(task_details)
    downloader = RemoteFileDownloader(config)
    return downloader.download()
