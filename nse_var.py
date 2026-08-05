import csv, time, requests, os, zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

URL = "https://www.nseindia.com/all-reports"
DOWNLOAD_DIR = "downloads"

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
DERIVATIVE_TABS = {
    "equity": "cr_derv_equities",
    "commodity": "cr_derv_commodity",
    "currency": "cr_derv_currency",
    "irf": "cr_derv_irf",
}

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
        convert_var_dat_to_csv(input_file=file_path, output_file=csv_file, headers=VAR_HEADERS,)

    else:
        print(f"No converter available for {file_name}")


def convert_var_dat_to_csv(input_file, output_file, headers):
    with open(input_file, "r", encoding="utf-8") as dat_file, \
         open(output_file, "w", newline="", encoding="utf-8") as csv_file:

        writer = csv.writer(csv_file)
        writer.writerow(headers)

        for line in dat_file:
            line = line.strip()

            if not line: continue

            columns = line.split(",")

            # Ignore header record (10)
            if columns[0] == "10": continue

            # Only process security records (20)
            if columns[0] != "20": continue

            writer.writerow(columns)

    print(f"CSV created successfully: {output_file}")

def download_report(url, report_label, file_extension=None, tab=None):
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
        time.sleep(10)
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
            "Referer": URL,
        })

        response = session.get(download_url, timeout=60)
        response.raise_for_status()

        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        with open(file_path, "wb") as file:
            file.write(response.content)

        print(f"Downloaded: {file_name}")
        if file_extension == ".dat":
            csv_file = os.path.splitext(file_path)[0] + ".csv"
            convert_var_dat_to_csv(input_file=file_path, output_file=csv_file, headers=VAR_HEADERS)
        elif file_extension == ".zip":
            extract_zip(file_path)

    finally:
        driver.quit()


if __name__ == "__main__":
    download_report(
        url="https://www.nseindia.com/all-reports",
        report_label="VaR Begin Day File",
        file_extension=".dat",
    )

    download_report(
        url="https://www.nseindia.com/all-reports",
        report_label="CM-UDiFF Common Bhavcopy Final (zip)",
        file_extension=".zip",
    )

    download_report(
        url="https://www.nseindia.com/all-reports-derivatives",
        tab=DERIVATIVE_TABS["equity"],
        report_label="F&O-Bhavcopy File (DAT)",
        file_extension=".dat",
    )

    download_report(
        url="https://www.nseindia.com/all-reports-derivatives",
        tab=DERIVATIVE_TABS["commodity"],
        report_label="COM-Bhavcopy File (DAT)",
        file_extension=".dat",
    )

    download_report(
        url="https://www.nseindia.com/all-reports-derivatives",
        tab=DERIVATIVE_TABS["currency"],
        report_label="CD-Bhavcopy File (DAT)",
        file_extension=".dat",
    )