import csv
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup

CURRENCY_MARGIN_URL = (
    "https://www.nseclearing.in/risk-management/currency-derivatives/margins"
)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)


EXPECTED_HEADERS = ["Product", "ELM: Futures", "ELM: Short Options"]


def scrape_currency_margin(final_files_dir="data/final_files", logger=None):
    """
    Scrape the Currency Derivatives margin table
    from NSE Clearing and save it as a CSV.

    The table is scraped fresh on every run so that
    changes published by NSE Clearing are captured.
    """

    os.makedirs(final_files_dir, exist_ok=True)

    if logger:
        logger.info("=" * 70)
        logger.info("STARTING NSE CURRENCY MARGIN SCRAPING")
        logger.info("=" * 70)

        logger.info(f"Opening NSE Clearing page: " f"{CURRENCY_MARGIN_URL}")

    # ---------------------------------------------------------
    # HTTP REQUEST
    # ---------------------------------------------------------

    response = requests.get(
        CURRENCY_MARGIN_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=(30, 60),
    )

    response.raise_for_status()

    # ---------------------------------------------------------
    # PARSE HTML
    # ---------------------------------------------------------

    soup = BeautifulSoup(response.text, "html.parser")

    target_table = None

    for table in soup.find_all("table"):
        header_row = table.find("thead")
        if not header_row:
            continue
        headers = [th.get_text(" ", strip=True) for th in header_row.find_all("th")]

        if headers == EXPECTED_HEADERS:
            target_table = table
            break

    # ---------------------------------------------------------
    # VALIDATE TABLE
    # ---------------------------------------------------------

    if target_table is None:
        Logger.error(
            "Currency margin table was not found " "or its structure has changed."
        )

    # ---------------------------------------------------------
    # READ DATA
    # ---------------------------------------------------------

    rows = []
    tbody = target_table.find("tbody")
    if tbody is None:
        Logger.error("Currency margin table has no tbody.")

    for tr in tbody.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        if len(cells) != len(EXPECTED_HEADERS):
            Logger.error(
                "Currency margin table structure changed. "
                f"Expected {len(EXPECTED_HEADERS)} columns, "
                f"found {len(cells)}: {cells}"
            )

        rows.append(cells)

    if not rows:
        Logger.error("Currency margin table was found " "but contains no data rows.")

    # ---------------------------------------------------------
    # OUTPUT FILE
    # ---------------------------------------------------------

    table_name = "temp"

    target_date = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(final_files_dir, f"{table_name}_{target_date}.csv")

    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(EXPECTED_HEADERS)
        writer.writerows(rows)

    # ---------------------------------------------------------
    # LOGGING
    # ---------------------------------------------------------

    if logger:
        logger.info(f"Currency Margin CSV Created : {output_file}")
        logger.info(f"Columns : {len(EXPECTED_HEADERS)}")
        logger.info(f"Rows    : {len(rows)}")

    return output_file
