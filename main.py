import csv, time, requests, os, zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# from headers import *
from db_operations import upload_all_csv_files
from logger import get_logger

logger = get_logger("main")

DOWNLOAD_DIR = "downloads"
FINAL_FILES_DIR = "final_files"

NSE_PAGE_URL = "https://www.nseindia.com/all-reports"
BSE_API_URL = ("https://api.bseindia.com/BseIndiaAPI/api/GetBhavcopydata/w?flag=0")

VAR_HEADERS = [
    "record_type",
    "symbol",
    "series",
    "isin",
    "elm_margin",
    "additional_margin",
    "var_margin",
    "extreme_loss_margin",
    "special_margin",
    "total_margin",
]

BSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
    ),
}

DERIVATIVE_TABS = {
    "equity": "cr_derv_equities",
    "commodity": "cr_derv_commodity",
    "currency": "cr_derv_currency",
    "irf": "cr_derv_irf",
}

BSE_UDIFF_FILES = [
    {
        "file_type": "EQ",
        "download_path": "https://www.bseindia.com/download/BhavCopy/Equity/",
    },
    {
        "file_type": "COM",
        "download_path": "https://www.bseindia.com/download/BhavCopy/Commodity/Csv/",
    },
    {
        "file_type": "CUR",
        "download_path": "https://www.bseindia.com/bsedata/CIML_bhavcopy/",
    },
    {
        "file_type": "EQD",
        "download_path": "https://www.bseindia.com/download/BhavCopy/Derivative/",
    },
]

NSE_REPORTS = [

    {
        "url": "https://www.nseindia.com/all-reports",
        "report_label": "VaR Begin Day File",
        "file_extension": ".dat",
    },

    {
        "url": "https://www.nseindia.com/all-reports",
        "report_label": "CM-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
    },

    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["equity"],
        "report_label": "F&O-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
    },

    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["commodity"],
        "report_label": "COM-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
    },

    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["currency"],
        "report_label": "CD-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
    },
]

import shutil


def post_process(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    os.makedirs(
        FINAL_FILES_DIR,
        exist_ok=True
    )

    # =====================================================
    # DAT
    # =====================================================

    if extension == ".dat":

        file_name = os.path.basename(file_path)

        csv_name = (
            os.path.splitext(file_name)[0]
            + ".csv"
        )

        final_csv = os.path.join(
            FINAL_FILES_DIR,
            csv_name
        )

        # VaR file uses actual headers
        if file_name.upper().startswith("C_VAR1_"):

            convert_dat_to_csv(
                input_file=file_path,
                output_file=final_csv,
                headers=VAR_HEADERS
            )

        # Other DAT files use temporary headers
        else:

            convert_dat_to_csv(
                input_file=file_path,
                output_file=final_csv
            )

        return final_csv

    # =====================================================
    # ZIP
    # =====================================================

    elif extension == ".zip":

        extracted_folder = extract_zip(
            file_path
        )

        final_files = []

        # Search extracted folder for CSV files
        for root, directories, files in os.walk(
            extracted_folder
        ):

            for file_name in files:

                if not file_name.lower().endswith(".csv"):
                    continue

                source_csv = os.path.join(
                    root,
                    file_name
                )

                final_csv = os.path.join(
                    FINAL_FILES_DIR,
                    file_name
                )

                shutil.copy2(
                    source_csv,
                    final_csv
                )

                logger.info(
                    f"CSV Copied : {final_csv}"
                )

                final_files.append(
                    final_csv
                )

        if not final_files:

            logger.info(
                f"No CSV files found inside: "
                f"{extracted_folder}"
            )

        return final_files

    # =====================================================
    # CSV
    # =====================================================

    elif extension == ".csv":

        file_name = os.path.basename(
            file_path
        )

        final_csv = os.path.join(
            FINAL_FILES_DIR,
            file_name
        )

        shutil.copy2(
            file_path,
            final_csv
        )

        logger.info(
            f"CSV Copied : {final_csv}"
        )

        return final_csv

    # =====================================================
    # Other
    # =====================================================

    else:

        logger.info(
            f"No post-processing required: "
            f"{file_path}"
        )

        return file_path

def download_bse_udiff(file_type, download_path):

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )

    session = requests.Session()
    session.headers.update(BSE_HEADERS)

    response = session.get(
        BSE_API_URL,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    file_name = None

    for file_data in data.get("dsUdiff", []):

        if file_data.get("Filetype") == file_type:

            file_name = file_data.get("filename")

            break

    if not file_name:

        raise ValueError(
            f"No UDiFF file found for file type: {file_type}"
        )

    download_url = (
        f"{download_path}{file_name}"
    )

    logger.info("\n--------------------------------")
    logger.info("BSE File Type :", file_type)
    logger.info("File Name     :", file_name)
    logger.info("URL           :", download_url)
    logger.info("--------------------------------")

    response = session.get(
        download_url,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,"
                "image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "Referer": (
                "https://www.bseindia.com/"
                "markets/marketinfo/bhavcopy"
            ),
        },
        timeout=60
    )

    response.raise_for_status()

    # ---------------------------------------------
    # Save raw BSE file
    # ---------------------------------------------

    file_path = os.path.join(
        DOWNLOAD_DIR,
        file_name
    )

    with open(
        file_path,
        "wb"
    ) as file:

        file.write(
            response.content
        )

    logger.info(
        f"Downloaded    : {file_name}"
    )

    # ---------------------------------------------
    # SAME POST-PROCESSING AS NSE
    # ---------------------------------------------

    final_file = post_process(
        file_path
    )

    return final_file    


def convert_dat_to_csv(input_file, output_file, headers=None):

    rows = []
    max_columns = 0

    with open(
        input_file,
        "r",
        encoding="utf-8",
        errors="replace"
    ) as dat_file:

        for line in dat_file:

            line = line.strip()

            if not line:
                continue

            columns = line.split(",")

            rows.append(columns)

            if len(columns) > max_columns:
                max_columns = len(columns)

    # --------------------------------------------------
    # Use actual headers if provided
    # Otherwise generate column1, column2, ...
    # --------------------------------------------------

    if headers:

        if len(headers) != max_columns:
            raise ValueError(
                f"Header count ({len(headers)}) "
                f"does not match data columns ({max_columns}) "
                f"for {input_file}"
            )

        csv_headers = headers

    else:

        csv_headers = [
            f"column{i}"
            for i in range(1, max_columns + 1)
        ]

    # --------------------------------------------------
    # Write CSV
    # --------------------------------------------------

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(csv_headers)

        for row in rows:

            row = row + [
                ""
            ] * (
                max_columns - len(row)
            )

            writer.writerow(row)

    logger.info(f"CSV Created : {output_file}")
    logger.info(f"Columns     : {max_columns}")
    logger.info(f"Rows        : {len(rows)}")

    return output_file

def extract_zip(zip_file_path):
    extract_to = os.path.splitext(zip_file_path)[0]

    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    logger.info(f"Extracted to: {extract_to}")

    return extract_to

def post_process(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    # ==================================================
    # DAT
    # ==================================================

    if extension == ".dat":

        os.makedirs(
            FINAL_FILES_DIR,
            exist_ok=True
        )

        file_name = os.path.basename(file_path)

        csv_name = (
            os.path.splitext(file_name)[0]
            + ".csv"
        )

        csv_file = os.path.join(
            FINAL_FILES_DIR,
            csv_name
        )

        # ----------------------------------------------
        # VaR file -> use actual headers
        # ----------------------------------------------

        if file_name.upper().startswith("C_VAR1_"):

            convert_dat_to_csv(
                input_file=file_path,
                output_file=csv_file,
                headers=VAR_HEADERS
            )

        # ----------------------------------------------
        # Other DAT files -> temporary column names
        # ----------------------------------------------

        else:

            convert_dat_to_csv(
                input_file=file_path,
                output_file=csv_file
            )

        return csv_file

    # ==================================================
    # ZIP
    # ==================================================

    elif extension == ".zip":

        extracted_folder = extract_zip(
            file_path
        )

        os.makedirs(
            FINAL_FILES_DIR,
            exist_ok=True
        )

        import shutil

        final_files = []

        for root, directories, files in os.walk(
            extracted_folder
        ):

            for file_name in files:

                if not file_name.lower().endswith(".csv"):
                    continue

                csv_file = os.path.join(
                    root,
                    file_name
                )

                final_file = os.path.join(
                    FINAL_FILES_DIR,
                    file_name
                )

                shutil.copy2(
                    csv_file,
                    final_file
                )

                logger.info(
                    f"CSV Copied : {final_file}"
                )

                final_files.append(
                    final_file
                )

        return final_files

    # ==================================================
    # CSV
    # ==================================================

    elif extension == ".csv":

        os.makedirs(
            FINAL_FILES_DIR,
            exist_ok=True
        )

        import shutil

        file_name = os.path.basename(
            file_path
        )

        final_file = os.path.join(
            FINAL_FILES_DIR,
            file_name
        )

        shutil.copy2(
            file_path,
            final_file
        )

        logger.info(
            f"CSV Copied : {final_file}"
        )

        return final_file

    else:

        logger.info(
            f"No post-processing required: "
            f"{file_path}"
        )

        return file_path

def download_nse_bhavcopy(
    url,
    report_label,
    file_extension=None,
    tab=None
):

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )

    options = Options()

    options.add_argument(
        "--headless=new"
    )

    options.add_argument(
        "--window-size=1920,1080"
    )

    options.add_argument(
        "--disable-gpu"
    )

    options.add_argument(
        "--no-sandbox"
    )

    options.add_argument(
        "--disable-dev-shm-usage"
    )

    options.add_argument(
        "--user-agent=Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36 Edg/151.0.0.0"
    )

    driver = webdriver.Chrome(
        options=options
    )

    try:

        driver.get(url)

        time.sleep(3)

        # -----------------------------------------
        # Open required derivative tab
        # -----------------------------------------

        if tab:

            driver.find_element(
                By.CSS_SELECTOR,
                f"a[aria-controls='{tab}']"
            ).click()

            time.sleep(3)

        # -----------------------------------------
        # Find report
        # -----------------------------------------

        report = driver.find_element(
            By.XPATH,
            f"//div[contains(@class,'reportsDownload')]"
            f"[.//label[contains("
            f"normalize-space(),"
            f"'{report_label}'"
            f")]]"
        )

        file_name = report.find_element(
            By.CSS_SELECTOR,
            "span.reportCardSegment"
        ).text.strip()

        download_url = report.get_attribute(
            "data-link"
        )

        logger.info(
            f"Report Name : {report_label}"
        )

        logger.info(
            f"File Name   : {file_name}"
        )

        logger.info(
            f"URL         : {download_url}"
        )

        # -----------------------------------------
        # Download
        # -----------------------------------------

        session = requests.Session()

        session.headers.update({

            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36 Edg/151.0.0.0"
            ),

            "Referer": url,
        })

        response = session.get(
            download_url,
            timeout=60
        )

        response.raise_for_status()

        file_path = os.path.join(
            DOWNLOAD_DIR,
            file_name
        )

        with open(
            file_path,
            "wb"
        ) as file:

            file.write(
                response.content
            )

        logger.info(
            f"Downloaded: {file_name}"
        )

        # -----------------------------------------
        # Post process
        # -----------------------------------------

        post_process(
            file_path
        )

        return file_path

    finally:

        driver.quit()

if __name__ == "__main__":

    # =====================================================
    # NSE
    # =====================================================

    for report in NSE_REPORTS:

        try:

            download_nse_bhavcopy(
                url=report["url"],
                report_label=report["report_label"],
                file_extension=report["file_extension"],
                tab=report.get("tab")
            )

        except Exception as error:

            logger.info(
                f"Failed to download NSE "
                f"{report['report_label']}: {error}"
            )

    # =====================================================
    # BSE
    # =====================================================

    for file in BSE_UDIFF_FILES:

        try:

            download_bse_udiff(
                file_type=file["file_type"],
                download_path=file["download_path"]
            )

        except Exception as error:

            logger.info(
                f"Failed to download BSE "
                f"{file['file_type']}: {error}"
            )

    # =====================================================
    # DATABASE
    # =====================================================

    logger.info("\n================================")
    logger.info("Uploading CSV files to database")
    logger.info("================================")

    try:

        upload_all_csv_files()

    except Exception as error:

        logger.info(
            f"Database upload failed: {error}"
        )