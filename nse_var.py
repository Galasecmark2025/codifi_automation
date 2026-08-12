import csv, time, requests, os, zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from headers import *

DOWNLOAD_DIR = "downloads"
FINAL_FILES_DIR = "final_files"

NSE_PAGE_URL = "https://www.nseindia.com/all-reports"
BSE_API_URL = ("https://api.bseindia.com/BseIndiaAPI/api/GetBhavcopydata/w?flag=0")

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
        "headers": VAR_HEADERS
    },
    {
        "url": "https://www.nseindia.com/all-reports",
        "report_label": "CM-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
    },
    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["equity"],
        "report_label": "F&O-Bhavcopy File (DAT)",
        "file_extension": ".dat",
        "headers": FNO_HEADERS
    },
    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["commodity"],
        "report_label": "COM-Bhavcopy File (DAT)",
        "file_extension": ".dat",
        "headers": COMMODITY_HEADERS
    },
    {
        "url": "https://www.nseindia.com/all-reports-derivatives",
        "tab": DERIVATIVE_TABS["currency"],
        "report_label": "CD-Bhavcopy File (DAT)",
        "file_extension": ".dat",
        "headers": CD_HEADERS
    },
]

import shutil


def post_process(file_path):

    extension = os.path.splitext(file_path)[1].lower()
    file_name = os.path.basename(file_path)

    if extension == ".dat":

        os.makedirs(FINAL_FILES_DIR,exist_ok=True)

        csv_name = (os.path.splitext(file_name)[0]+ ".csv")

        csv_file = os.path.join(FINAL_FILES_DIR,csv_name)

        convert_dat_to_csv(input_file=file_path,output_file=csv_file)

        return csv_file

    elif extension == ".zip":

        return extract_zip(file_path)

    elif extension == ".csv":

        os.makedirs(FINAL_FILES_DIR,exist_ok=True)

        final_file = os.path.join(FINAL_FILES_DIR,file_name)

        shutil.copy2(file_path,final_file)

        print(f"CSV Copied : {final_file}")

        return final_file

    else:

        print(f"No post-processing required for {file_name}")

        return file_path

def download_bse_udiff(file_type, download_path):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update(BSE_HEADERS)

    response = session.get(BSE_API_URL,timeout=60)

    response.raise_for_status()

    data = response.json()

    file_name = None

    for file_data in data.get("dsUdiff", []):
        if file_data.get("Filetype") == file_type:
            file_name = file_data.get("filename")
            break

    if not file_name:
        raise ValueError(f"No UDiFF file found for file type: {file_type}")

    download_url = f"{download_path}{file_name}"

    print("\n--------------------------------")
    print("BSE File Type :", file_type)
    print("File Name     :", file_name)
    print("URL           :", download_url)
    print("--------------------------------")

    response = session.get(
        download_url,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;"
                "q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Referer": "https://www.bseindia.com/markets/marketinfo/bhavcopy",
        },
        timeout=60,
    )

    response.raise_for_status()

    file_path = os.path.join(DOWNLOAD_DIR,file_name)

    with open(file_path, "wb") as file:
        file.write(response.content)

    print(f"Downloaded    : {file_name}")

    return file_path

def convert_dat_to_csv(input_file, output_file):
    """
    Convert any comma-separated DAT file into CSV.
    """

    rows = []
    max_columns = 0

    with open(input_file, "r", encoding="utf-8", errors="replace") as dat_file:

        for line in dat_file:

            line = line.strip()

            if not line:continue

            columns = line.split(",")

            rows.append(columns)

            if len(columns) > max_columns:
                max_columns = len(columns)

    headers = [f"column{i}" for i in range(1, max_columns + 1)]

    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow(headers)

        for row in rows:

            # Make sure every row has same number of columns
            row = row + [""] * (max_columns - len(row))

            writer.writerow(row)

    print(f"CSV Created : {output_file}")

    print(f"Columns     : {max_columns}")

    print(f"Rows        : {len(rows)}")

    return output_file


def extract_zip(zip_file_path):
    extract_to = os.path.splitext(zip_file_path)[0]

    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    print(f"Extracted to: {extract_to}")

    return extract_to

def post_process(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    if extension != ".dat":
        return

    file_name = os.path.basename(file_path).upper()

    csv_file = os.path.splitext(file_path)[0] + ".csv"

    if file_name.startswith("C_VAR1_"):
        convert_dat_to_csv(input_file=file_path, output_file=csv_file)

    else:
        print(f"No converter available for {file_name}")



def download_nse_bhavcopy(url, report_label, file_extension=None, tab=None, headers=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
    )

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        time.sleep(3)
        if tab:
            driver.find_element(By.CSS_SELECTOR,f"a[aria-controls='{tab}']").click()

            time.sleep(3)

        report = driver.find_element(By.XPATH,f"//div[contains(@class,'reportsDownload')][.//label[contains(normalize-space(), '{report_label}')]]")

        file_name = report.find_element(By.CSS_SELECTOR,"span.reportCardSegment").text.strip()

        download_url = report.get_attribute("data-link")

        print(f"Report Name : {report_label}")
        print(f"File Name   : {file_name}")
        print(f"URL         : {download_url}")

        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
            ),
            "Referer": NSE_PAGE_URL,
        })

        response = session.get(download_url, timeout=60)
        response.raise_for_status()

        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        with open(file_path, "wb") as file:
            file.write(response.content)

        print(f"Downloaded: {file_name}")
        if file_extension == ".dat":
            csv_file = os.path.splitext(file_path)[0] + ".csv"
            convert_dat_to_csv(input_file=file_path, output_file=csv_file)
        elif file_extension == ".zip":
            extract_zip(file_path)

    finally:
        driver.quit()

if __name__ == "__main__":
    for report in NSE_REPORTS:
        try:
            download_nse_bhavcopy(
                url=report["url"],
                report_label=report["report_label"],
                file_extension=report["file_extension"],
                tab=report.get("tab"),
                headers=report["headers"]
            )

        except Exception as error:
            print(f"Failed to download NSE {report['report_label']}: {error}")

    for file in BSE_UDIFF_FILES:
        try:
            download_bse_udiff(file_type=file["file_type"], download_path=file["download_path"])
        except Exception as error:
            print(f"Failed to download BSE {file['file_type']} file: {error}")