"""BSE download, validation, and post-processing using Task and TaskPaths."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests

from exchange_scraper_automation.file_management.file_operations import \
    post_process
from exchange_scraper_automation.file_management.filename_patterns import \
    validate_filenamepath
from exchange_scraper_automation.models.bse_report_config import \
    BSEReportConfig
from exchange_scraper_automation.models.task import Task
from exchange_scraper_automation.models.task_paths import TaskPaths
from exchange_scraper_automation.observability.logger import Logger


def get_task_details(task: Task) -> BSEReportConfig:
    """Parse tasktypedetails into the typed BSE configuration model."""
    details = task.details
    if not details:
        Logger.error(f"Task {task.task_id} has empty tasktypedetails.")
    try:
        return BSEReportConfig.from_mapping(details)
    except ValueError as error:
        Logger.error(f"Invalid BSE tasktypedetails for TaskID={task.task_id}: {error}")


def get_filenamepath(task: Task) -> str:
    """Return the database filenamepath used to validate the remote file name."""
    filenamepath = str(task.filename_path).strip()
    if not filenamepath:
        Logger.error(f"Missing filenamepath database column | TaskID={task.task_id}")
    return filenamepath


def filename_pattern(filenamepath: str) -> str:
    """Convert date placeholders in filenamepath to wildcards for API selection."""
    basename = PurePosixPath(filenamepath.replace("\\", "/")).name
    return (
        basename.replace("<YYYYMMDD>", "*")
        .replace("<DDMMYYYY>", "*")
        .replace("<DDMMYY>", "*")
        .replace("<YYYY-MM-DD>", "*")
    )


def get_bse_file_name(api_data: dict[str, Any], file_type: str) -> str:
    """Find a file name in the standard BSE UDiFF API response."""
    for item in api_data.get("dsUdiff", []):
        if item.get("Filetype") == file_type:
            file_name = item.get("filename")
            if file_name:
                return str(file_name)
    Logger.error(f"No BSE UDiFF file found for: {file_type}")


def get_url_file_name(download_url: str) -> str:
    """Extract a URL basename while excluding query strings and URL-encoding."""
    file_name = unquote(PurePosixPath(urlparse(download_url).path).name)
    if not file_name:
        Logger.error(f"Could not determine filename from URL: {download_url}")
    return file_name


def build_download_url(
    download_path: str,
    file_name: str,
    base_api: str,
) -> str:
    """Join a configured BSE download path and file name safely."""
    if download_path.startswith(("http://", "https://")):
        if download_path.endswith("/"):
            return f"{download_path}{file_name}"
        return f"{download_path}/{file_name}"

    base_url = f"{base_api.rstrip('/')}/"
    return urljoin(base_url, f"{download_path.strip('/')}/{file_name}")


def request_bse_file(
    download_url: str,
    file_path: str,
    logger: Any,
    config: Any,
) -> str:
    """Download one BSE file and validate that a non-empty file was written."""
    session = requests.Session()
    session.headers.update(config.get_bse_scraper_headers())
    # session.headers.update(BSE_HEADERS)

    if not download_url:
        Logger.warning(f"Download URL is missing for BSE\n" f"File path: {file_path}")
        return False
    response = session.get(
        download_url,
        headers=config.get_bse_download_headers(),
        timeout=(30, 120),
    )
    response.raise_for_status()

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    temporary_path = f"{file_path}.part"
    try:
        with open(temporary_path, "wb") as output_file:
            output_file.write(response.content)

        file_size = os.path.getsize(temporary_path)
        if file_size == 0:
            Logger.error(f"BSE downloaded file is empty: {os.path.basename(file_path)}")
        os.replace(temporary_path, file_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

    logger.info(
        f"Downloaded      : {os.path.basename(file_path)}"
        f"Downloaded size : {os.path.getsize(file_path):,} bytes"
    )
    return file_path


def run_post_process(
    *,
    file_path: str,
    logger: Any,
    task_details: BSEReportConfig,
    config: Any,
    filenamepath: str | None = None,
    default_selected_file: str = "all",
) -> Any:
    """Post-process the downloaded file without relying on a table name in JSON."""
    if task_details.file_name:
        if not filenamepath:
            logger.error(
                "filenamepath is required to select a file from the ZIP archive."
            )

        if not file_path.lower().endswith(".zip"):
            logger.error(
                "tasktypedetails.file_name indicates archive selection, "
                f"but the downloaded file is not a ZIP: {file_path}"
            )

        selected_file = filename_pattern(filenamepath)
    else:
        selected_file = task_details.zip_file or default_selected_file
    skip_rows = int(task_details.skip_rows or 0)
    result = post_process(
        file_path=file_path,
        logger=logger,
        selected_file=selected_file,
        skip_rows=skip_rows,
        config=config,
    )
    if result is None:
        Logger.error(f"BSE post-processing failed: {os.path.basename(file_path)}")
    return result


def download_bse_file(
    *,
    task: Task,
    task_details: BSEReportConfig,
    api_data: dict[str, Any] | None,
    logger: Any,
    download_dir: str,
    config: Any,
) -> dict[str, Any]:
    """Download a direct URL or standard UDiFF file and process it."""
    filenamepath = get_filenamepath(task)
    file_type = str(task_details.file_type)

    configured_file_name = str(task_details.file_name).strip()

    if configured_file_name:
        # Use only the filename, not any directory in the configuration.
        configured_file_name = PurePosixPath(
            configured_file_name.replace("\\", "/")
        ).name

    direct_url = task_details.url

    if direct_url:
        download_url = str(direct_url).strip()
        remote_file_name = get_url_file_name(download_url)

    else:
        if not api_data:
            logger.error(
                f"BSE API data is required for TaskID={task.task_id} "
                f"(FileType={file_type!r})"
            )

        if not file_type:
            logger.error(
                f"Missing file_type in BSE task config | TaskID={task.task_id}"
            )

        download_path = str(task_details.download_path).strip()

        if not download_path:
            logger.error(
                f"Missing download_path in BSE task config | TaskID={task.task_id}"
            )

        remote_file_name = get_bse_file_name(
            api_data=api_data,
            file_type=file_type,
        )

        download_url = build_download_url(
            download_path,
            remote_file_name,
            config.get_bse_base_api(),
        )

    # Use the configured archive name when supplied.
    file_name = configured_file_name or remote_file_name

    if file_name:
        logger.info(
            f"BSE archive filename configured | "
            f"TaskID={task.task_id} | "
            f"Archive={file_name} | "
            f"ZIP member pattern={filename_pattern(filenamepath)}"
        )
    else:
        # For ordinary downloads, validate the actual remote filename.
        validate_filenamepath(
            filenamepath=filenamepath,
            actual_filename=remote_file_name,
        )
        Logger.info(
            f"BSE filename validation passed | TaskID={task.task_id} | "
            f"Filename={file_name} | FilenamePath={filenamepath}"
        )

    logger.info(
        f"{'-' * 32}\n"
        f"BSE File Type : {file_type or 'Direct URL'}\n"
        f"Segment       : {task_details.segment}\n"
        f"Data Type     : {task_details.data_type}\n"
        f"File Name     : {file_name}\n"
        f"URL           : {download_url}\n"
        f"{'-' * 32}"
    )

    os.makedirs(download_dir, exist_ok=True)

    # Save the downloaded file using its actual/configured archive name.
    file_path = os.path.join(download_dir, file_name)

    request_bse_file(
        download_url=download_url,
        file_path=file_path,
        logger=logger,
        config=config,
    )

    processed_result = run_post_process(
        file_path=file_path,
        logger=logger,
        task_details=task_details,
        config=config,
        filenamepath=filenamepath if configured_file_name else None,
    )
    return {
        "downloaded_file": file_path,
        "processed_file": processed_result,
    }


def get_bse_slbm_file_name(
    *,
    api_data: dict[str, Any],
    task_details: BSEReportConfig,
    filenamepath: str,
    task_id: int | str,
    logger: Any,
) -> str:
    """Select the newest SLBM API record whose filename matches filenamepath."""
    api_key = str(task_details.api_key).strip()
    filename_key = str(task_details.api_filename_key).strip()
    if not api_key or not filename_key:
        logger.error("BSE SLBM config requires api_key and api_filename_key.")
    records = api_data.get(api_key, [])
    if not records:
        logger.error(f"No records found in BSE API section: {api_key}")

    pattern = filename_pattern(filenamepath)
    matching_records = [
        record
        for record in records
        if record.get(filename_key)
        and fnmatch.fnmatchcase(str(record[filename_key]), pattern)
    ]
    if not matching_records:
        Logger.error(
            f"No BSE SLBM API filename matches filenamepath | TaskID={task_id} | "
            f"Pattern={pattern!r}"
        )

    latest_record = max(matching_records, key=lambda item: str(item.get("DtTM", "")))
    file_name = str(latest_record[filename_key])
    validate_filenamepath(filenamepath=filenamepath, actual_filename=file_name)
    logger.info(f"BSE SLBM file name | TaskID={task_id} | Filename={file_name}")
    return file_name


def download_bse_slbm(
    *,
    task: Task,
    api_data: dict[str, Any],
    task_details: BSEReportConfig,
    logger: Any,
    download_dir: str,
    config: Any,
) -> dict[str, Any]:
    filenamepath = get_filenamepath(task)
    file_name = get_bse_slbm_file_name(
        api_data=api_data,
        task_details=task_details,
        filenamepath=filenamepath,
        task_id=task.task_id,
        logger=logger,
    )
    download_path = str(task_details.download_path).strip()
    if not download_path:
        logger.error(f"Missing SLBM download_path | TaskID={task.task_id}")
    download_url = build_download_url(
        download_path,
        file_name,
        config.get_bse_base_api(),
    )
    # validate_bse_file(file_name, task, filenamepath)
    validate_filenamepath(filenamepath=filenamepath, actual_filename=file_name)

    logger.info(
        f"{'-' * 32}\n"
        "BSE File Type : SLBM\n"
        f"Segment       : {task_details.segment}\n"
        f"Data Type     : {task_details.data_type}\n"
        f"File Name     : {file_name}\n"
        f"URL           : {download_url}\n"
        f"{'-' * 32}"
    )

    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, file_name)
    request_bse_file(
        download_url=download_url,
        file_path=file_path,
        logger=logger,
        config=config,
    )
    processed_result = run_post_process(
        file_path=file_path,
        logger=logger,
        task_details=task_details,
        config=config,
    )
    return {"downloaded_file": file_path, "processed_file": processed_result}


def get_bse_var_url(
    *,
    api_data: dict[str, Any],
    task_details: BSEReportConfig,
    filenamepath: str,
    logger: Any,
) -> str:
    """Find the BSE VAR API URL matching the filenamepath pattern."""
    api_key = str(task_details.api_key).strip()
    filename_key = str(task_details.file_name_key).strip()
    file_path_key = str(task_details.file_path_key).strip()
    if not api_key or not filename_key or not file_path_key:
        logger.error(
            "BSE VAR config requires api_key, file_name_key, and file_path_key."
        )
    records = api_data.get(api_key, [])
    if not records:
        logger.error(f"No records found in BSE VAR API section: {api_key}")
    pattern = filename_pattern(filenamepath)
    matches = [
        item
        for item in records
        if item.get(filename_key)
        and fnmatch.fnmatchcase(str(item[filename_key]), pattern)
        and item.get(file_path_key)
    ]
    if not matches:
        Logger.error(
            f"No BSE VAR record matches filenamepath | "
            f"Pattern={pattern!r} | API section={api_key}"
        )

    selected = max(matches, key=lambda item: str(item.get("DtTM", "")))
    download_url = str(selected[file_path_key]).strip()
    if not download_url:
        logger.error(f"BSE VAR URL is missing for pattern: {pattern}")
    logger.info(f"BSE VAR API URL: {download_url}")
    return download_url


def download_bse_var(
    *,
    task: Task,
    api_data: dict[str, Any],
    task_details: BSEReportConfig,
    logger: Any,
    download_dir: str,
    config: Any,
) -> dict[str, Any]:
    filenamepath = get_filenamepath(task)
    api_url = get_bse_var_url(
        api_data=api_data,
        task_details=task_details,
        filenamepath=filenamepath,
        logger=logger,
    )
    file_name = get_url_file_name(api_url)
    validate_filenamepath(filenamepath=filenamepath, actual_filename=file_name)

    # Keep the prior BSE margin file route when the API provides only a filename
    # or relative path; honor an absolute API URL unchanged.
    base_api = f"{config.get_bse_base_api().rstrip('/')}/"

    if api_url.startswith(("http://", "https://")):
        download_url = api_url
    elif "/" in api_url.strip("/"):
        download_url = urljoin(base_api, api_url.lstrip("/"))
    else:
        download_url = urljoin(base_api, f"BSEDATA/margins/{file_name}")

    logger.info(
        f"{'-' * 32}\n"
        "BSE File Type : VAR\n"
        f"Segment       : {task_details.segment}\n"
        f"Data Type     : {task_details.data_type}\n"
        f"File Name     : {file_name}\n"
        f"API URL       : {api_url}\n"
        f"Download URL  : {download_url}\n"
        f"{'-' * 32}"
    )

    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, file_name)
    request_bse_file(
        download_url=download_url,
        file_path=file_path,
        logger=logger,
        config=config,
    )

    selection_rule = str(task_details.zip_file or "same_as_zip")
    zip_base_name = os.path.splitext(file_name)[0]
    if selection_rule == "same_as_zip":
        selected_file = f"{zip_base_name}.xls"
    elif selection_rule == "current_date":
        selected_file = f"VAR{datetime.now().strftime('%d%m%y')}.xls"
    elif selection_rule == "all":
        selected_file = "all"
    else:
        selected_file = selection_rule

    processed_result = post_process(
        file_path=file_path,
        logger=logger,
        selected_file=selected_file,
        skip_rows=int(task_details.skip_rows or 0),
        config=config,
    )
    if processed_result is None:
        Logger.error(f"BSE VAR post-processing failed: {file_name}")
    return {"downloaded_file": file_path, "processed_file": processed_result}


def fetch_bse_api_data(api_url: str, config: Any) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(config.get_bse_scraper_headers())
    response = session.get(api_url, timeout=(30, 60))
    response.raise_for_status()
    api_data = response.json()
    if not isinstance(api_data, dict):
        Logger.error("Unexpected BSE API response: expected a JSON object.")
    return api_data


def scrape_bse(
    task: Task,
    config: Any,
    paths: TaskPaths,
    logger: Any = None,
    connection: Any = None,
) -> dict[str, Any]:
    """Route a BSE Task using its JSON config and resolved local paths."""
    del connection  # Reserved for consistent NSE/BSE scraper interfaces.
    if logger is None:
        logger = Logger

    task_details = get_task_details(task)
    filenamepath = get_filenamepath(task)
    download_dir = os.fspath(paths.download_dir)
    os.makedirs(download_dir, exist_ok=True)

    file_type = str(task_details.file_type)
    segment = str(task_details.segment)
    data_type = str(task_details.data_type)
    protocol = str(task_details.protocol).strip().lower()

    logger.info(
        f"{'=' * 70}\n"
        "STARTING BSE SCRAPING\n"
        f"BSE TASK | TaskID={task.task_id} | Alias={task.alias_name} | "
        f"FileType={file_type} | Segment={segment} | "
        f"DataType={data_type} | Protocol={protocol} | "
        f"FilenamePath={filenamepath}"
    )

    for key, value in asdict(task_details).items():
        if key.lower() in {"password", "token", "secret"}:
            continue
        logger.info(f"{key} = {value}")

    try:
        # 1. Direct/static URL. `filenamepath` provides the expected filename pattern;
        # `file_name` is no longer required in tasktypedetails.
        if task_details.url:
            result = download_bse_file(
                task=task,
                task_details=task_details,
                api_data=None,
                logger=logger,
                download_dir=download_dir,
                config=config,
            )
            return {"success": True, "files": [result]}

        # The scheduler normally routes SFTP directly through TaskProcessor, not here.
        if protocol == "sftp":
            logger.error(
                f"BSE SFTP task must be routed through the transfer handler | "
                f"TaskID={task.task_id}"
            )
            return {"success": False, "files": []}

        if segment.upper() == "SLBM" and data_type.lower() == "bhavcopy":
            logger.info("Fetching BSE UDiFF API for SLBM")
            api_data = fetch_bse_api_data(config.get_bse_api_url(), config)
            result = download_bse_slbm(
                task=task,
                api_data=api_data,
                task_details=task_details,
                logger=logger,
                download_dir=download_dir,
                config=config,
            )
            return {"success": True, "files": [result]}

        if data_type.lower() == "margin" or file_type.upper() == "VAR":
            api_url = str(task_details.api_url).strip()
            if not api_url:
                logger.error(
                    f"BSE Margin/VAR task is missing api_url | TaskID={task.task_id}"
                )
            api_data = fetch_bse_api_data(api_url, config)
            result = download_bse_var(
                task=task,
                api_data=api_data,
                task_details=task_details,
                logger=logger,
                download_dir=download_dir,
                config=config,
            )
            return {"success": True, "files": [result]}

        # Standard BSE UDiFF task.
        logger.info(
            f"Fetching BSE UDiFF API | TaskID={task.task_id} | FileType={file_type}"
        )
        api_data = fetch_bse_api_data(config.get_bse_api_url(), config)
        if "dsUdiff" not in api_data:
            Logger.error("BSE API response does not contain dsUdiff.")

        logger.info(f"BSE API records found: {len(api_data['dsUdiff'])}")
        for index, item in enumerate(api_data["dsUdiff"], start=1):
            logger.info(
                f"API Record {index} | FileType={item.get('Filetype')} | "
                f"Filename={item.get('filename')}"
            )

        result = download_bse_file(
            task=task,
            task_details=task_details,
            api_data=api_data,
            logger=logger,
            download_dir=download_dir,
            config=config,
        )
        logger.info(f"BSE DOWNLOAD SUCCESS | TaskID={task.task_id}")
        return {"success": True, "files": [result]}

    except Exception as error:
        logger.error(
            f"BSE DOWNLOAD FAILED | TaskID={task.task_id} | "
            f"Alias={task.alias_name} | FileType={file_type} | "
            f"Segment={segment} | DataType={data_type} | "
            f"Protocol={protocol} | ErrorType={type(error).__name__} | Error={error}"
        )
        return {"success": False, "files": []}
