# config.py

from pathlib import Path


class Config:
    def __init__(self):
        self._logging_destination = ""
        self._logging_level = ""
        self._store_to_file = False
        self._logging_directory = ""
        self._logging_file_name = ""

        self._server_host = ""
        self._server_port = 0

        # Database
        self._database_host = ""
        self._database_port = 0
        self._database_name = ""
        self._database_user = ""
        self._database_password = ""

        # Scraper
        self._scraper_exchange = ""
        self._scraper_segment = ""
        self._scraper_file_type = ""

        # APIs/URLs
        self._nse_page_url = ""
        self._nse_reports_url = ""
        self._nse_derivatives_url = ""
        self._bse_api_url = ""

    def load(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as config_file:
                current_section = ""

                for line in config_file:
                    line = line.strip()

                    if not line:
                        continue

                    if line.startswith("#") or line.startswith(";"):
                        continue

                    if line.startswith("[") and line.endswith("]"):
                        current_section = line[1:-1]
                        continue

                    separator_position = line.find("=")

                    if separator_position == -1:
                        continue

                    key = line[:separator_position].strip()
                    value = line[separator_position + 1 :].strip()

                    if current_section == "Logging":
                        if key == "Destination":
                            self._logging_destination = value

                        elif key == "Level":
                            self._logging_level = value

                        elif key == "StoreToFile":
                            self._store_to_file = value.lower() == "true"

                        elif key == "Directory":
                            self._logging_directory = value

                        elif key == "FileName":
                            self._logging_file_name = value

                    elif current_section == "Server":
                        if key == "Host":
                            self._server_host = value

                        elif key == "Port":
                            self._server_port = int(value)

                    elif current_section == "Database":
                        if key == "Host":
                            self._database_host = value

                        elif key == "Port":
                            self._database_port = int(value)

                        elif key == "Name":
                            self._database_name = value

                        elif key == "User":
                            self._database_user = value

                        elif key == "Password":
                            self._database_password = value

                    elif current_section == "Scraper":
                        if key == "Exchange":
                            self._scraper_exchange = value

                        elif key == "Segment":
                            self._scraper_segment = value

                        elif key == "FileType":
                            self._scraper_file_type = value

                    elif current_section == "Exchange":
                        if key == "NSEPageUrl":
                            self._nse_page_url = value

                        elif key == "NSEReportsUrl":
                            self._nse_reports_url = value

                        elif key == "NSEDervativesUrl":
                            self._nse_derivatives_url = value

                        elif key == "BSEApiUrl":
                            self._bse_api_url = value

            return True

        except (OSError, ValueError):
            return False

    def get_logging_destination(self):
        return self._logging_destination

    def get_logging_level(self):
        return self._logging_level

    def get_store_to_file(self):
        return self._store_to_file

    def get_logging_directory(self):
        return self._logging_directory

    def get_logging_file_name(self):
        return self._logging_file_name

    def get_server_host(self):
        return self._server_host

    def get_server_port(self):
        return self._server_port

    def get_database_host(self):
        return self._database_host

    def get_database_port(self):
        return self._database_port

    def get_database_name(self):
        return self._database_name

    def get_database_user(self):
        return self._database_user

    def get_database_password(self):
        return self._database_password

    def get_scraper_exchange(self):
        return self._scraper_exchange

    def get_scraper_segment(self):
        return self._scraper_segment

    def get_scraper_file_type(self):
        return self._scraper_file_type

    # -------------------------
    # Base API/URLs
    def get_nse_page_url(self):
        return self._nse_page_url

    def get_nse_reports_url(self):
        return self._nse_reports_url

    def get_nse_derivatives_url(self):
        return self._nse_derivatives_url

    def get_bse_api_url(self):
        return self._bse_api_url
