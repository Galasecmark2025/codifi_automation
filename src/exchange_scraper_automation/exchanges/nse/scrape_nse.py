import json
import os
from urllib.parse import unquote, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from exchange_scraper_automation.file_management.file_operations import \
    post_process
from exchange_scraper_automation.file_management.filename_patterns import \
    validate_filenamepath
from exchange_scraper_automation.models.nse_report_config import \
    NSEReportConfig
from exchange_scraper_automation.models.task import Task
from exchange_scraper_automation.models.task_paths import TaskPaths
from exchange_scraper_automation.observability.logger import Logger

# CONSTANTS

# USER_AGENT = (
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#     "AppleWebKit/537.36 (KHTML, like Gecko) "
#     "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
# )


# SELENIUM
def create_driver(user_agent: str):
    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={user_agent}")
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
def validate_report_url(download_url, report_label, segment, url_contains, logger):
    """Validate the report URL using the minimal task configuration.

    The full expected filename (including its extension) is validated against
    the database ``filenamepath`` separately by ``validate_filenamepath``.
    """
    if url_contains and url_contains not in download_url:
        Logger.error(
            "REPORT URL SAFETY CHECK FAILED\n"
            f"Report      : {report_label}\n"
            f"Segment     : {segment}\n"
            f"Expected URL part: {url_contains}\n"
            f"Actual URL  : {download_url}"
        )

    logger.info(
        f"Report URL safety check passed | Report={report_label} | "
        f"Segment={segment} | URL part={url_contains!r}"
    )


# FILE NAME
def get_file_name(download_url):
    path = urlparse(download_url).path
    file_name = os.path.basename(path)
    file_name = unquote(file_name)

    if not file_name:
        Logger.error("Could not determine filename " f"from URL: {download_url}")

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
        logger.info(
            f"Content-Type       : {content_type}\n"
            f"Content-Length     : {content_length}\n"
            f"Content-Encoding   : {content_encoding}\n"
            f"Content-Disposition: {content_disposition}"
        )

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

            Logger.error(
                "Incomplete download. "
                f"Expected {expected_size:,} bytes, "
                f"received {downloaded_size:,} bytes."
            )

    # VERIFY FILE EXISTS
    if not os.path.exists(temp_path):
        Logger.error("Download finished but temporary " "file does not exist.")

    actual_size = os.path.getsize(temp_path)

    # VERIFY FILE IS NOT EMPTY
    if actual_size == 0:
        os.remove(temp_path)
        Logger.error("Downloaded file is empty.")

    # FINALIZE DOWNLOAD
    os.replace(temp_path, file_path)

    logger.info(
        f"Download completed : "
        f"{os.path.basename(file_path)}\n"
        f"Downloaded size    : "
        f"{actual_size:,} bytes"
    )

    return file_path


def get_task_details(task):
    task_details = task.details

    if not task_details:
        Logger.error(f"Task {task.task_id} has empty tasktypedetails.")

    if isinstance(task_details, str):
        try:
            task_details = json.loads(task_details)
        except json.JSONDecodeError as error:
            Logger.error(
                f"Invalid tasktypedetails JSON for TaskID={task.task_id}: {error}"
            )

    if not isinstance(task_details, dict):
        Logger.error(
            f"tasktypedetails for TaskID={task.task_id} must be a JSON object."
        )

    return task_details


def get_nse_market_url(config, market):
    if market == "capital_market":
        return config.get_nse_reports_url()

    if market == "derivatives":
        return config.get_nse_derivatives_url()

    Logger.error(f"Invalid NSE market: {market}")


# MAIN NSE DOWNLOAD
# def download_nse_files(task, config, logger=None,):
def download_nse_files(task: Task, paths: TaskPaths, config, logger=None):
    if logger is None:
        logger = Logger

    # Load and validate the report configuration once.
    report = NSEReportConfig.from_mapping(task.details)

    market = report.market
    report_label = report.report_label
    tab = report.tab
    section = report.section
    segment = report.segment
    headers = report.headers
    url_contains = report.url_contains

    # Paths are supplied as a separate object.
    download_dir = os.fspath(paths.download_dir)

    try:
        os.makedirs(download_dir, exist_ok=True)
        logger.info(f"NSE download and extraction directory: {download_dir}")

    except OSError as error:
        Logger.error(
            f"Unable to create NSE download/output directories "
            f"| TaskID={task.task_id} | DownloadDir={download_dir}"
        )

    # CONFIG VALIDATION
    if not tab:
        Logger.error(f"NSE tab is not configured for: " f"{report_label}")

    if not section:
        Logger.error(f"NSE section is not configured for: " f"{report_label}")

    user_agent = config.get_nse_user_agent()
    if not user_agent:
        Logger.error("NSE user agent is missing from the configuration service.")

    # CREATE DRIVER
    driver = create_driver(user_agent)

    try:
        url = get_nse_market_url(
            config=config,
            market=market,
        )

        # OPEN NSE
        logger.info(f"Opening NSE market : {market}\n" f"Opening NSE page   : {url}")
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

        # The database filenamepath is the source of truth for both the
        # expected filename and its extension (for example, *.csv.zip).
        filenamepath = str(task.filename_path).strip()

        if not filenamepath:
            Logger.error(
                f"Missing filenamepath database column | TaskID={task.task_id}"
            )

        file_name = get_file_name(download_url)

        validate_filenamepath(
            filenamepath=filenamepath,
            actual_filename=file_name,
        )

        # Validate the source URL using url_contains. The expected filename,
        # including its extension, was validated above against filenamepath.
        validate_report_url(
            download_url=download_url,
            report_label=report_label,
            segment=segment,
            url_contains=url_contains,
            logger=logger,
        )

        # GET FILENAME
        file_name = get_file_name(download_url)
        logger.info(
            f"Report Name : {report_label}\n"
            f"File Name   : {file_name}\n"
            f"URL         : {download_url}"
        )

        # REQUEST SESSION
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": user_agent,
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
            logger=logger,
            headers=headers,
            filenamepath=filenamepath,
        )

        # VERIFY POST PROCESS RESULT
        if result is None:
            Logger.error(f"Post-processing failed for: {file_name}")

        return result

    finally:
        driver.quit()


# NSE SCRAPER
def scrape_nse(task, config, paths: TaskPaths, connection=None):
    Logger.info(f"{'=' * 70}\n" "STARTING NSE SCRAPING\n" f"{'=' * 70}")

    try:
        result = download_nse_files(
            task=task,
            paths=paths,
            config=config,
            logger=Logger,
        )

        if isinstance(result, dict) and result.get("success") is False:
            return result

        Logger.info(f"NSE task completed: " f"{task.alias_name}")

        return {
            "success": True,
            "files": result,
        }

    except Exception as error:
        Logger.error(f"Failed to process NSE task " f"TaskID={task.task_id}: {error}")

        return {
            "success": False,
            "files": [],
        }
