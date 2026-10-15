import json
import os
import zipfile
from datetime import datetime

import requests

# from exchange_scraper_automation.scraper_utilities.run_selection import matches_selection
from exchange_scraper_automation.scraper_utilities.bse.bse_config import BSE_HEADERS
from exchange_scraper_automation.scraper_utilities.db_operations import (
    update_task_status,
)

# from exchange_scraper_automation.scraper_utilities.bse.bse_config import BSE_API_URL, BSE_HEADERS, BSE_REPORTS, BSE_SLBM, BSE_VAR
from exchange_scraper_automation.scraper_utilities.file_operations import post_process
from exchange_scraper_automation.scraper_utilities.logger import Logger

# logger = get_logger("bse")


# =========================================================
# GET BSE FILE NAME FROM API
# =========================================================
def get_bse_file_name(api_data, file_type):
    for item in api_data.get("dsUdiff", []):
        if item.get("Filetype") == file_type:
            file_name = item.get("filename")
            if file_name:
                return file_name

    raise ValueError(f"No BSE UDiFF file found for: {file_type}")


# =========================================================
# VALIDATE BSE FILE
# =========================================================
def validate_bse_file(file_name, task_details):
    expected_extension = task_details.get("file_extension")

    if expected_extension:
        if not file_name.lower().endswith(expected_extension.lower()):
            raise RuntimeError(
                "BSE FILE VALIDATION FAILED\n"
                f"File type        : "
                f"{task_details['file_type']}\n"
                f"Expected extension: "
                f"{expected_extension}\n"
                f"Actual filename   : "
                f"{file_name}"
            )


def get_task_details(task):
    task_details = task.get("tasktypedetails")

    if not task_details:
        raise ValueError(f"Task {task.get('taskid')} has empty tasktypedetails.")

    if isinstance(task_details, str):
        try:
            task_details = json.loads(task_details)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid tasktypedetails JSON "
                f"for TaskID={task.get('taskid')}: {error}"
            ) from error

    if not isinstance(task_details, dict):
        raise ValueError(
            f"tasktypedetails for TaskID={task.get('taskid')} "
            f"must be a JSON object."
        )

    return task_details


# =========================================================
# DOWNLOAD ONE BSE FILE
# =========================================================
def download_bse_file(
    task_details,
    api_data,
    logger,
    download_dir,
    final_files_dir,
    config,
):
    # file_type = report["file_type"]
    file_type = task_details["file_type"]
    # GET FILE NAME + URL

    if "url" in task_details and "file_name" in task_details:
        # Static/direct BSE file
        file_name = task_details["file_name"]
        download_url = task_details["url"]

    else:
        # API-based BSE file
        download_path = task_details["download_path"]

        file_name = get_bse_file_name(api_data=api_data, file_type=file_type)

        download_url = f"{download_path}{file_name}"
    # download_path = task_details["download_path"]

    # # -----------------------------------------------------
    # # GET FILE NAME
    # # -----------------------------------------------------

    # file_name = get_bse_file_name(api_data=api_data,file_type=file_type)

    # VALIDATE FILE

    validate_bse_file(file_name=file_name, task_details=task_details)

    # BUILD URL

    # download_url = (f"{download_path}{file_name}")

    logger.info("")
    logger.info("--------------------------------")
    logger.info(f"BSE File Type : {file_type}")
    logger.info(f"Segment       : {task_details['segment']}")
    logger.info(f"Data Type     : {task_details['data_type']}")
    logger.info(f"File Name     : {file_name}")
    logger.info(f"URL           : {download_url}")
    logger.info("--------------------------------")

    # CREATE SESSION
    session = requests.Session()
    session.headers.update(BSE_HEADERS)

    # DOWNLOAD
    response = session.get(
        download_url,
        headers={
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "image/apng,"
                "*/*;q=0.8"
            ),
            "Referer": ("https://www.bseindia.com/" "markets/marketinfo/bhavcopy"),
        },
        timeout=(30, 120),
    )

    response.raise_for_status()

    # SAVE FILE

    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, file_name)

    with open(file_path, "wb") as file:
        file.write(response.content)

    # VERIFY FILE

    if not os.path.exists(file_path):
        raise IOError(
            f"BSE download completed but " f"file was not created: {file_name}"
        )

    file_size = os.path.getsize(file_path)

    if file_size == 0:

        raise IOError(f"BSE downloaded file is empty: " f"{file_name}")

    logger.info(f"Downloaded    : {file_name}")

    logger.info(f"Downloaded size: " f"{file_size:,} bytes")

    # POST PROCESS

    result = post_process(
        file_path=file_path,
        final_files_dir=final_files_dir,
        logger=logger,
        selected_file=task_details.get("zip_file", "all"),
        table_name=task_details["table_name"],
        skip_rows=task_details.get("skip_rows", 0),
        config=config,
    )

    if result is None:
        raise RuntimeError(f"BSE post-processing failed: " f"{file_name}")

    # return result
    return {"result": result, "table_name": task_details["table_name"]}


# =========================================================
# GET BSE SLBM FILE NAME FROM API
# =========================================================


def get_bse_slbm_file_name(api_data, task_details, logger):

    api_key = task_details["api_key"]
    filename_key = task_details["api_filename_key"]

    records = api_data.get(api_key, [])

    if not records:
        raise ValueError(f"No records found in BSE API section: " f"{api_key}")

    # Get latest record

    latest_record = max(records, key=lambda item: item.get("DtTM", ""))

    file_name = latest_record.get(filename_key)

    if not file_name:
        raise ValueError(f"No filename found in BSE API section: " f"{api_key}")

    # Validate filename

    expected_prefix = task_details["file_prefix"]

    expected_extension = task_details["file_extension"]

    if not file_name.startswith(expected_prefix):
        raise RuntimeError(
            "BSE SLBM filename validation failed.\n"
            f"Expected prefix : {expected_prefix}\n"
            f"Actual filename : {file_name}"
        )

    if not file_name.lower().endswith(expected_extension.lower()):
        raise RuntimeError(
            "BSE SLBM extension validation failed.\n"
            f"Expected extension : {expected_extension}\n"
            f"Actual filename    : {file_name}"
        )

    logger.info(f"BSE SLBM File Name : {file_name}")

    return file_name


# =========================================================
# DOWNLOAD BSE SLBM
# =========================================================


def download_bse_slbm(
    api_data,
    task_details,
    logger,
    download_dir,
    final_files_dir,
    config,
):
    # GET ACTUAL FILE NAME FROM API

    file_name = get_bse_slbm_file_name(
        api_data=api_data, task_details=task_details, logger=logger
    )

    download_path = task_details["download_path"]

    download_url = f"{download_path}" f"{file_name}"

    # LOG

    logger.info("")
    logger.info("--------------------------------")
    logger.info("BSE File Type : SLBM")
    logger.info(f"Segment       : " f"{task_details['segment']}")
    logger.info(f"Data Type     : " f"{task_details['data_type']}")
    logger.info(f"File Name     : {file_name}")
    logger.info(f"URL           : {download_url}")
    logger.info("--------------------------------")

    # SESSION

    session = requests.Session()

    session.headers.update(BSE_HEADERS)

    # DOWNLOAD

    response = session.get(
        download_url,
        headers={
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "image/apng,"
                "*/*;q=0.8"
            ),
            "Referer": ("https://www.bseindia.com/"),
        },
        timeout=(30, 120),
    )

    response.raise_for_status()

    # SAVE FILE

    os.makedirs(download_dir, exist_ok=True)

    file_path = os.path.join(download_dir, file_name)

    with open(file_path, "wb") as file:
        file.write(response.content)

    # VERIFY FILE

    if not os.path.exists(file_path):
        raise IOError(f"BSE SLBM file was not created: " f"{file_name}")

    file_size = os.path.getsize(file_path)

    if file_size == 0:
        raise IOError(f"BSE SLBM file is empty: " f"{file_name}")

    logger.info(f"Downloaded     : {file_name}")

    logger.info(f"Downloaded size: " f"{file_size:,} bytes")

    # POST PROCESS

    result = post_process(
        file_path=file_path,
        final_files_dir=final_files_dir,
        logger=logger,
        table_name=task_details["table_name"],
        config=config,
    )

    if result is None:
        raise RuntimeError(f"BSE SLBM post-processing failed: " f"{file_name}")

    # return result
    return {"result": result, "table_name": task_details["table_name"]}


# =========================================================
# GET BSE VAR FILE URL
# =========================================================


def get_bse_var_url(api_data, task_details, logger):
    records = api_data.get(task_details["api_key"], [])

    if not records:
        raise ValueError(
            f"No records found in BSE VAR API section: " f"{task_details['api_key']}"
        )

    target_file_name = task_details["file_name"]

    for item in records:
        if item.get(task_details["file_name_key"]) == target_file_name:
            download_url = item.get(task_details["file_path_key"])

            if not download_url:
                raise ValueError(
                    f"BSE VAR record found but "
                    f"download URL is missing: "
                    f"{target_file_name}"
                )

            if not download_url.lower().endswith(task_details["file_extension"]):
                raise RuntimeError(
                    "BSE VAR file validation failed.\n"
                    f"Expected extension : "
                    f"{task_details['file_extension']}\n"
                    f"Actual URL         : "
                    f"{download_url}"
                )

            logger.info(f"BSE VAR download URL : {download_url}")

            return download_url

    raise ValueError(f"No BSE VAR file found for: " f"{target_file_name}")


# =========================================================
# DOWNLOAD BSE VAR
# =========================================================
def download_bse_var(
    api_data, task_details, logger, download_dir, final_files_dir, config
):
    # GET FILE NAME + API URL
    api_url = get_bse_var_url(
        api_data=api_data, task_details=task_details, logger=logger
    )
    file_name = api_url.rstrip("/").split("/")[-1]

    # BUILD ACTUAL BSE DOWNLOAD URL
    download_url = "https://www.bseindia.com/" f"BSEDATA/margins/{file_name}"

    # LOG
    logger.info("")
    logger.info("--------------------------------")
    logger.info("BSE File Type : VAR")
    logger.info(f"Segment       : {task_details['segment']}")
    logger.info(f"Data Type     : {task_details['data_type']}")
    logger.info(f"File Name     : {file_name}")
    logger.info(f"API URL       : {api_url}")
    logger.info(f"Download URL   : {download_url}")
    logger.info("--------------------------------")

    # SESSION
    session = requests.Session()
    session.headers.update(BSE_HEADERS)

    # DOWNLOAD
    response = session.get(
        download_url,
        headers={
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "image/apng,"
                "*/*;q=0.8"
            ),
            "Referer": ("https://www.bseindia.com/" "markets/equity/eqreports/margin"),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        },
        timeout=(30, 120),
    )

    response.raise_for_status()

    # SAVE FILE
    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, file_name)
    with open(file_path, "wb") as file:
        file.write(response.content)

    # VERIFY FILE
    if not os.path.exists(file_path):
        raise IOError(f"BSE VAR file was not created: {file_name}")

    file_size = os.path.getsize(file_path)

    if file_size == 0:
        raise IOError(f"BSE VAR file is empty: {file_name}")
    logger.info(f"Downloaded     : {file_name}")
    logger.info(f"Downloaded size: {file_size:,} bytes")

    zip_path = os.path.join(download_dir, file_name)

    # Extract folder = ZIP filename without extension
    extract_folder = os.path.join(download_dir, os.path.splitext(file_name)[0])

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_folder)

    logger.info(f"Extracted to: {extract_folder}")

    # SELECT XLS FILE
    selection_rule = task_details.get("zip_file", "same_as_zip")
    zip_base_name = os.path.splitext(file_name)[0]
    if selection_rule == "same_as_zip":
        selected_file = f"{zip_base_name}.xls"
    elif selection_rule == "current_date":
        # current_date = datetime.now().strftime("%d%m%y")
        # selected_file = f"VAR{current_date}.xls"
        target_date = datetime.now()
        selected_file = (
            f"VAR{datetime.strptime(target_date, '%Y%m%d').strftime('%d%m%y')}.xls"
        )

    elif selection_rule == "all":
        selected_file = "all"
    else:
        selected_file = selection_rule

    logger.info(f"VAR ZIP file      : {file_name}")
    logger.info(f"VAR selection rule: {selection_rule}")
    logger.info(f"VAR selected file : {selected_file}")

    # POST PROCESS
    result = post_process(
        file_path=file_path,
        final_files_dir=final_files_dir,
        logger=logger,
        selected_file=selected_file,
        table_name=task_details["table_name"],
        config=config,
    )

    if result is None:
        raise RuntimeError(f"BSE VAR post-processing failed: {file_name}")

    return {"result": result, "table_name": task_details["table_name"]}


# =========================================================
# DOWNLOAD ALL BSE FILES
# =========================================================
def scrape_bse(task, config, logger=None, connection=None):
    if logger is None:
        logger = Logger

    download_dir = config.get_download_directory()
    final_files_dir = config.get_final_files_directory()

    logger.info("=" * 70)
    logger.info("STARTING BSE SCRAPING")
    logger.info("=" * 70)

    # ---------------------------------------------------------
    # Get task configuration from tasktypedetails JSON
    # ---------------------------------------------------------
    task_details = get_task_details(task)

    logger.info("=" * 70)
    logger.info("BSE TASK CONFIGURATION")
    logger.info("=" * 70)

    for key, value in task_details.items():
        logger.info(f"{key} = {value}")

    logger.info("=" * 70)

    file_type = task_details.get("file_type")
    segment = task_details.get("segment")
    data_type = task_details.get("data_type")
    protocol = task_details.get("protocol")

    logger.info(
        f"BSE TASK | "
        f"FileType={file_type} | "
        f"Segment={segment} | "
        f"DataType={data_type} | "
        f"Protocol={protocol}"
    )

    results = []

    try:

        # =====================================================
        # 1. DIRECT URL DOWNLOAD
        # =====================================================
        if task_details.get("url") and task_details.get("file_name"):

            logger.info(
                f"BSE DIRECT DOWNLOAD | "
                f"FileType={file_type} | "
                f"URL={task_details.get('url')}"
            )

            result = download_bse_file(
                task_details=task_details,
                api_data=None,
                logger=logger,
                download_dir=download_dir,
                final_files_dir=final_files_dir,
                config=config,
            )

            results.append(result)

            logger.info(
                f"BSE DOWNLOAD SUCCESS | "
                f"FileType={file_type} | "
                f"Segment={segment}"
            )

            return {
                "success": True,
                "files": results,
            }

        # =====================================================
        # 2. SFTP
        #
        # Do not fall through to the BSE API.
        # The actual SFTP implementation should be connected
        # here once we use the existing SFTP code.
        # =====================================================
        if protocol and protocol.upper() == "SFTP":

            logger.info(
                f"BSE SFTP TASK | "
                f"FileType={file_type} | "
                f"Segment={segment} | "
                f"DataType={data_type}"
            )

            logger.error(
                "BSE SFTP task received, but SFTP handling "
                "is not implemented in the current BSE scraper."
            )

            return {
                "success": False,
                "files": results,
            }

        # =====================================================
        # 3. BSE SLBM BHAVCOPY
        # =====================================================
        if segment == "SLBM" and data_type == "Bhavcopy":

            logger.info("Fetching BSE UDiFF API for SLBM")

            session = requests.Session()
            session.headers.update(BSE_HEADERS)

            response = session.get(
                config.get_bse_api_url(),
                timeout=(30, 60),
            )

            response.raise_for_status()

            api_data = response.json()

            if not isinstance(api_data, dict):
                raise RuntimeError("Unexpected BSE UDiFF API response.")

            result = download_bse_slbm(
                api_data=api_data,
                task_details=task_details,
                logger=logger,
                download_dir=download_dir,
                final_files_dir=final_files_dir,
                config=config,
            )

            results.append(result)

            logger.info(f"BSE SLBM DOWNLOAD SUCCESS | " f"Segment={segment}")

            return {
                "success": True,
                "files": results,
            }

        # =====================================================
        # 4. MARGIN / VAR
        # =====================================================
        if data_type == "Margin" or file_type == "VAR":

            var_api_url = task_details.get("api_url")

            if not var_api_url:
                raise ValueError("BSE Margin/VAR task is missing api_url.")

            logger.info(f"Fetching BSE VAR API | " f"URL={var_api_url}")

            session = requests.Session()
            session.headers.update(BSE_HEADERS)

            response = session.get(
                var_api_url,
                timeout=(30, 60),
            )

            response.raise_for_status()

            api_data = response.json()

            if not isinstance(api_data, dict):
                raise RuntimeError("Unexpected BSE VAR API response.")

            result = download_bse_var(
                api_data=api_data,
                task_details=task_details,
                logger=logger,
                download_dir=download_dir,
                final_files_dir=final_files_dir,
                config=config,
            )

            results.append(result)

            logger.info(
                f"BSE VAR DOWNLOAD SUCCESS | "
                f"FileType={file_type} | "
                f"Segment={segment}"
            )

            return {
                "success": True,
                "files": results,
            }

        # =====================================================
        # 5. NORMAL BSE DOWNLOAD
        # =====================================================
        logger.info(f"Fetching BSE UDiFF API | " f"FileType={file_type}")

        session = requests.Session()
        session.headers.update(BSE_HEADERS)

        response = session.get(
            config.get_bse_api_url(),
            timeout=(30, 60),
        )

        response.raise_for_status()

        api_data = response.json()

        if not isinstance(api_data, dict):
            raise RuntimeError("Unexpected BSE UDiFF API response.")

        if "dsUdiff" not in api_data:
            raise RuntimeError("BSE API response does not contain dsUdiff.")

        logger.info(f"BSE API records found: " f"{len(api_data['dsUdiff'])}")

        for index, item in enumerate(api_data["dsUdiff"], start=1):
            logger.info(
                f"API Record {index} | "
                f"FileType={item.get('Filetype')} | "
                f"Filename={item.get('filename')}"
            )

        result = download_bse_file(
            task_details=task_details,
            api_data=api_data,
            logger=logger,
            download_dir=download_dir,
            final_files_dir=final_files_dir,
            config=config,
        )

        if result:
            update_task_status(
                connection=connection,
                task_id=task["taskid"],
                status="COMPLETED",
            )
            logger.info(f"Task {task['taskid']} completed successfully.")

        results.append(result)

        logger.info(
            f"BSE DOWNLOAD SUCCESS | " f"FileType={file_type} | " f"Segment={segment}"
        )

        return {
            "success": True,
            "files": results,
        }

    except Exception as error:

        logger.error(
            f"BSE DOWNLOAD FAILED | "
            f"FileType={file_type} | "
            f"Segment={segment} | "
            f"DataType={data_type} | "
            f"Protocol={protocol} | "
            f"Error={error}"
        )

        return {
            "success": False,
            "files": results,
        }
