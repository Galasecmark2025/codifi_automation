# file_transfer.py

from __future__ import annotations

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

from exchange_scraper_automation.file_management.filename_patterns import (
    filename_template_regex,
)
from exchange_scraper_automation.observability.logger import Logger
from exchange_scraper_automation.security.secret_manager import SecretManager


@dataclass(frozen=True)
class TransferConfig:
    """Configuration required to download a file over FTP or SFTP."""

    protocol: str
    hostname: str
    port: int
    userid: str
    password: str
    filenamepath: str
    destination_dir: Path
    timeout: int = 30

    @classmethod
    def from_dict(
        cls,
        data,
        destination_dir,
        filenamepath: str,
        secret_manager: SecretManager,
    ):

        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, dict):
            Logger.error(f"Expected dict or JSON string, got {type(data).__name__}")

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
        )

        missing = [
            key
            for key in required
            if data.get(key) is None or not str(data[key]).strip()
        ]

        if missing:
            Logger.error(
                f"Missing required transfer configuration fields: {missing}. "
                f"Received keys: {sorted(data.keys())}"
            )

        # filenamepath comes from the database task row.
        remote_file_pattern = str(filenamepath).strip()

        if not remote_file_pattern or remote_file_pattern.endswith("/"):
            Logger.error("Missing or invalid filenamepath on the database task row.")

        decrypted_password = str(data["password"])

        if secret_manager is not None:
            # Require a valid encrypted token and decrypt it.
            decrypted_password = secret_manager.decrypt(decrypted_password)
        elif decrypted_password.startswith(SecretManager.PREFIX):
            Logger.error(
                "An encrypted SFTP password was provided, but no SecretManager was configured."
            )

        return cls(
            protocol=data["protocol"],
            hostname=data["hostname"],
            port=int(data.get("port") or 22),
            userid=data["userid"],
            password=decrypted_password,
            filenamepath=remote_file_pattern,
            destination_dir=Path(destination_dir).expanduser(),
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
        """Download the remote file specified by filenamepath."""

        cfg = self.config
        destination_dir = Path(cfg.destination_dir).expanduser()
        destination_dir.mkdir(parents=True, exist_ok=True)

        remote_file_path_template = str(cfg.filenamepath).strip()

        remote_dir = posixpath.dirname(remote_file_path_template) or "/"
        filename_template = posixpath.basename(remote_file_path_template)

        if not filename_template:
            Logger.error(f"filenamepath must include a filename: {cfg.filenamepath}")

        Logger.info(
            f"Searching remote files | "
            f"Protocol={cfg.protocol.upper()} | "
            f"Host={cfg.hostname} | "
            f"Directory={remote_dir} | "
            f"Pattern={filename_template}"
        )

        try:
            remote_filename = self._find_remote_file(
                remote_dir,
                filename_template,
            )

            final_path = destination_dir / remote_filename
            remote_file_path = posixpath.join(remote_dir, remote_filename)

            self._validate_remote_path(remote_file_path)
            Logger.info(
                f"Selected remote file | Remote={remote_file_path} | Local={final_path}"
            )

            self._download_remote_file(remote_file_path, final_path)
            Logger.info(
                f"Download completed successfully | Local={final_path} | Size={final_path.stat().st_size} bytes"
            )

            return final_path

        except Exception as error:
            Logger.error(
                f"Download failed | Protocol={cfg.protocol.upper()} | "
                f"Directory={remote_dir} Error={error}\n{traceback.format_exc()}"
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
            Logger.error(f"remote_filename must identify a file: {remote_path}")

    def _download_remote_file(
        self,
        remote_file_path: str,
        destination: Path,
    ):
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
                Logger.error("Download did not produce a local file.")

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
            Logger.error(f"Unsupported transfer protocol: {cfg.protocol}")

        filename_regex = filename_template_regex(filename_pattern)

        matches = [
            entry
            for entry in entries
            if filename_regex.fullmatch(entry.filename)
            and not (
                getattr(entry, "st_mode", 0)
                and not __import__("stat").S_ISREG(entry.st_mode)
            )
        ]

        if not matches:
            Logger.error(
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
    ):
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
    ):
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


def download_task_file(
    task_details: dict,
    destination_dir: str | Path,
    filenamepath: str,
    secret_manager: SecretManager,
):
    """
    Public entry point for FTP/SFTP downloads.

    Accepts the full task configuration dictionary. Fields used only by later
    processing, such as `file_to_pick`, remain in `task_details` for the caller
    and are not interpreted by this downloader.
    """

    config = TransferConfig.from_dict(
        task_details,
        destination_dir=destination_dir,
        filenamepath=filenamepath,
        secret_manager=secret_manager,
    )
    downloader = RemoteFileDownloader(config)
    return downloader.download()
