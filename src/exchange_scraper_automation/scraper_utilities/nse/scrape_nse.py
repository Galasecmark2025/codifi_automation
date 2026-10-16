import json
import os
from urllib.parse import unquote, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from exchange_scraper_automation.scraper_utilities.file_operations import post_process
from exchange_scraper_automation.scraper_utilities.logger import Logger

# CONSTANTS

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)


# SELENIUM
def create_driver():
    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={USER_AGENT}")
    return webdriver.Chrome(options=options)


def wait_for_page(driver):

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def select_nse_tab(driver, tab, logger):
    logger.info(f"Selecting NSE tab : {tab}")

    tab_xpath = f"//a[normalize-space(@aria-controls)='{tab}']"

    # Wait for tab to exist
    tab_element = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, tab_xpath))
    )

    # Scroll to tab
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", tab_element
    )

    # Wait until clickable
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, tab_xpath)))

    # Click
    driver.execute_script("arguments[0].click();", tab_element)

    # Confirm selected
    WebDriverWait(driver, 30).until(
        lambda d: (
            d.find_element(By.XPATH, tab_xpath).get_attribute("aria-selected") == "true"
        )
    )

    logger.info(f"NSE tab selected : {tab}")


# REPORT IDENTIFICATION
def build_report_xpath(report_label, section):
    return (
        "//div[contains("
        "concat(' ', normalize-space(@class), ' '), "
        "' reportsDownload ')]"
        f"[@data-section='{section}']"
        f"[.//label[contains("
        f"normalize-space(), '{report_label}'"
        f")]]"
    )


def find_nse_report(driver, report_label, section):
    report_xpath = build_report_xpath(report_label=report_label, section=section)
    return WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, report_xpath))
    )


def get_download_url(driver, report_label, section, logger=None):
    report_xpath = build_report_xpath(report_label=report_label, section=section)

    if logger:
        logger.info(f"Waiting for download URL : " f"{report_label}")

    def find_url(driver):
        reports = driver.find_elements(By.XPATH, report_xpath)
        for report in reports:
            url = report.get_attribute("data-link")

            if url and url.startswith("http"):
                return url

        return False

    download_url = WebDriverWait(driver, 30, poll_frequency=0.5).until(find_url)

    if logger:
        logger.info(f"Download URL ready : " f"{download_url}")

    return download_url


# SAFETY VALIDATION
def validate_report_url(download_url, report, logger):
    segment = report.get("segment")

    report_label = report.get("report_label")

    expected_extension = report.get("file_extension")

    expected_url_part = report.get("url_contains")

    expected_prefix = report.get("filename_prefix")

    # URL validation

    if expected_url_part:

        if expected_url_part not in download_url:

            raise RuntimeError(
                "REPORT SAFETY CHECK FAILED\n"
                f"Report      : {report_label}\n"
                f"Segment     : {segment}\n"
                f"Expected URL: {expected_url_part}\n"
                f"Actual URL  : {download_url}"
            )

    # Filename validation
    file_name = get_file_name(download_url)

    if expected_extension:

        if not file_name.lower().endswith(expected_extension.lower()):

            raise RuntimeError(
                "FILE EXTENSION SAFETY CHECK FAILED\n"
                f"Report           : {report_label}\n"
                f"Expected         : {expected_extension}\n"
                f"Actual filename  : {file_name}"
            )

    if expected_prefix:
        if not file_name.startswith(expected_prefix):
            raise RuntimeError(
                "FILENAME SAFETY CHECK FAILED\n"
                f"Report           : {report_label}\n"
                f"Expected prefix  : {expected_prefix}\n"
                f"Actual filename  : {file_name}\n"
                f"URL              : {download_url}"
            )

    logger.info(f"URL safety check passed : {file_name}")


# FILE NAME
def get_file_name(download_url):
    path = urlparse(download_url).path
    file_name = os.path.basename(path)
    file_name = unquote(file_name)

    if not file_name:
        raise ValueError("Could not determine filename " f"from URL: {download_url}")

    return file_name


# DOWNLOAD
def download_file(session, download_url, file_path, logger):
    temp_path = file_path + ".part"

    # Remove stale partial file
    if os.path.exists(temp_path):
        os.remove(temp_path)

    logger.info(f"Starting download: " f"{os.path.basename(file_path)}")

    expected_size = None
    content_encoding = None
    downloaded_size = 0

    with session.get(download_url, stream=True, timeout=(30, 120)) as response:
        response.raise_for_status()

        content_type = response.headers.get("Content-Type")
        content_encoding = response.headers.get("Content-Encoding")
        content_length = response.headers.get("Content-Length")
        content_disposition = response.headers.get("Content-Disposition")
        logger.info(f"Content-Type       : {content_type}")
        logger.info(f"Content-Length     : {content_length}")
        logger.info(f"Content-Encoding   : {content_encoding}")
        logger.info(f"Content-Disposition: " f"{content_disposition}")

        if content_length:
            expected_size = int(content_length)

            logger.info(f"Expected size : " f"{expected_size:,} bytes")

        else:
            logger.info("Expected size : Unknown")

        # WRITE DOWNLOAD
        with open(temp_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                file.write(chunk)
                downloaded_size += len(chunk)

    # VERIFY DOWNLOAD SIZE
    if content_encoding:
        logger.info(
            "Skipping Content-Length validation "
            f"because response uses "
            f"Content-Encoding: {content_encoding}"
        )

    elif expected_size is not None:
        if downloaded_size != expected_size:
            if os.path.exists(temp_path):
                os.remove(temp_path)

            raise IOError(
                "Incomplete download. "
                f"Expected {expected_size:,} bytes, "
                f"received {downloaded_size:,} bytes."
            )

    # VERIFY FILE EXISTS
    if not os.path.exists(temp_path):
        raise IOError("Download finished but temporary " "file does not exist.")

    actual_size = os.path.getsize(temp_path)

    # VERIFY FILE IS NOT EMPTY
    if actual_size == 0:
        os.remove(temp_path)
        raise IOError("Downloaded file is empty.")

    # FINALIZE DOWNLOAD
    os.replace(temp_path, file_path)

    logger.info(f"Download completed : " f"{os.path.basename(file_path)}")

    logger.info(f"Downloaded size    : " f"{actual_size:,} bytes")

    return file_path


def get_task_details(task):
    task_details = task.get("tasktypedetails")

    if not task_details:
        raise ValueError(f"Task {task.get('taskid')} has empty tasktypedetails.")

    if isinstance(task_details, str):
        try:
            task_details = json.loads(task_details)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid tasktypedetails JSON for TaskID={task.get('taskid')}: {error}"
            ) from error

    if not isinstance(task_details, dict):
        raise ValueError(
            f"tasktypedetails for TaskID={task.get('taskid')} must be a JSON object."
        )

    return task_details


def get_nse_market_url(config, market):
    if market == "capital_market":
        return config.get_nse_reports_url()

    if market == "derivatives":
        return config.get_nse_derivatives_url()

    raise ValueError(f"Invalid NSE market: {market}")


# MAIN NSE DOWNLOAD
def download_nse_files(task, config, logger=None, ):
    if logger is None:
        logger = Logger

    task_details = get_task_details(task)

    protocol = task_details["protocol"].lower()
    if protocol != "url":
        logger.warning(
            f"NSE TaskID={task['taskid']} skipped: "
            f"protocol='{protocol}' is not supported by the NSE URL automation."
        )
        return {
            "success": False,
            "files": [],
        }

    market = task_details["market"]
    report_label = task_details["report_label"]
    file_extension = task_details.get("file_extension")
    tab = task_details.get("tab")
    section = task_details.get("section")
    segment = task_details.get("segment")
    headers = task_details.get("headers")
    url_contains = task_details.get("url_contains")
    filename_prefix = task_details.get("filename_prefix")
    table_name = task_details.get("table_name")

    # DIRECTORY CONFIGURATION

    configured_download_dir = task_details.get("local_path")

    if not configured_download_dir:
        raise ValueError(
            f"Missing local_path in NSE task configuration "
            f"| TaskID={task.get('taskid')}"
        )

    # configured_final_dir = task_details.get("final_files_dir")

    download_dir = os.fspath(configured_download_dir)
    final_files_dir = download_dir

    # os.makedirs(download_dir, exist_ok=True)

    try:
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(final_files_dir, exist_ok=True)
        logger.info(f"NSE download and extraction directory: {download_dir}")

    except OSError as error:
        raise RuntimeError(
            f"Unable to create NSE download/output directories "
            f"| TaskID={task.get('taskid')} "
            f"| DownloadDir={download_dir} "
            f"| FinalDir={final_files_dir}"
        ) from error

    logger.info(f"NSE download directory : {download_dir}")
    logger.info(f"NSE output directory   : {final_files_dir}")

    # CONFIG VALIDATION
    if not tab:
        raise ValueError(f"NSE tab is not configured for: " f"{report_label}")

    if not section:
        raise ValueError(f"NSE section is not configured for: " f"{report_label}")

    # CREATE DRIVER

    driver = create_driver()

    try:
        url = get_nse_market_url(
            config=config,
            market=market,
        )

        # OPEN NSE
        logger.info(f"Opening NSE market : {market}")
        logger.info(f"Opening NSE page   : {url}")
        driver.get(url)
        wait_for_page(driver)

        # SELECT TAB
        select_nse_tab(driver=driver, tab=tab, logger=logger)

        # WAIT FOR REPORT SECTION
        section_xpath = (
            "//div[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' reportsDownload ')]"
            f"[@data-section='{section}']"
        )

        WebDriverWait(driver, 30).until(
            lambda d: len(d.find_elements(By.XPATH, section_xpath)) > 0
        )

        # FIND REPORT
        report = find_nse_report(
            driver=driver, report_label=report_label, section=section
        )

        logger.info(f"Report found : {report_label}")

        # GET URL
        download_url = get_download_url(
            driver=driver, report_label=report_label, section=section, logger=logger
        )

        # BUILD REPORT CONFIG
        # FOR SAFETY VALIDATION
        report_config = {
            "report_label": report_label,
            "file_extension": file_extension,
            "segment": segment,
            "url_contains": url_contains,
            "filename_prefix": filename_prefix,
        }

        # SAFETY CHECK
        validate_report_url(
            download_url=download_url, report=report_config, logger=logger
        )

        # GET FILENAME
        file_name = get_file_name(download_url)
        logger.info(f"Report Name : {report_label}")
        logger.info(f"File Name   : {file_name}")
        logger.info(f"URL         : {download_url}")

        # REQUEST SESSION
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Referer": url,
                "Accept": "*/*",
            }
        )

        # FILE PATH
        file_path = os.path.join(download_dir, file_name)

        # DOWNLOAD
        download_file(
            session=session,
            download_url=download_url,
            file_path=file_path,
            logger=logger,
        )

        # POST PROCESS
        result = post_process(
            file_path=file_path,
            final_files_dir=final_files_dir,
            logger=logger,
            headers=headers,
            table_name=table_name,
        )

        # VERIFY POST PROCESS RESULT

        if result is None:
            raise RuntimeError(f"Post-processing failed for: {file_name}")

        return result

    finally:
        driver.quit()


# NSE SCRAPER
def scrape_nse(task, config, connection):
    Logger.info("=" * 70)
    Logger.info("STARTING NSE SCRAPING")
    Logger.info("=" * 70)

    try:
        result = download_nse_files(
            task=task,
            config=config,
            logger=Logger,
        )

        # download_nse_files() may return either:
        # 1. {"success": False, "files": []} for skipped protocol
        # 2. actual processed files for successful URL task

        if isinstance(result, dict) and result.get("success") is False:
            return result

        task_details = task.get("tasktypedetails")

        if isinstance(task_details, str):
            task_details = json.loads(task_details)

        table_name = (
            task_details.get("table_name") if isinstance(task_details, dict) else None
        )

        Logger.info(f"NSE task completed: " f"{task.get('aliasname')}")

        return {
            "success": True,
            "files": result,
        }

    except Exception as error:
        Logger.error(
            f"Failed to process NSE task " f"TaskID={task.get('taskid')}: {error}"
        )

        return {
            "success": False,
            "files": [],
        }
