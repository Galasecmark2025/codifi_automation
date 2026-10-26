# config.py

import configparser
import json
import logging
from copy import deepcopy
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "Config" / "configservice.ini"
)


class Config:
    CONFIG_SERVICE_ENDPOINT = "/ExchangeAdaptor"
    DEFAULT_SERVICE_ID = 81
    REQUEST_TIMEOUT = (5, 20)

    def __init__(self):
        # Config-service connection
        self._config_service_ip = ""
        self._config_service_port = 0
        self._config_service_token = ""

        # Service metadata
        self._service_id = 0
        self._service_name = ""
        self._service_type = ""

        # Logging
        self._logging_destination = ""
        self._logging_level = ""
        self._store_to_file = False
        self._logging_directory = ""
        self._logging_file_name = ""

        # Server
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

        # Exchange API URLs
        self._nse_page_url = ""
        self._nse_reports_url = ""
        self._nse_derivatives_url = ""
        self._bse_api_url = ""

        # Complete configuration returned by the service
        self._service_config = {}

        self._loaded = False

        # Security
        self._sftp_encryption_key = ""

    def load(self, file_path=DEFAULT_CONFIG_PATH, service_id=DEFAULT_SERVICE_ID):
        """
        Read config-service connection details from config.ini,
        call the configuration service using service_id, and load
        the configuration returned by the service.
        """
        self._loaded = False

        try:
            # ---------------------------------------------
            # 1. Read config-service connection details
            # ---------------------------------------------
            ini_path = Path(file_path)

            if not ini_path.is_file():
                logger.error("Configuration file not found: %s", ini_path)
                return False

            parser = configparser.ConfigParser()
            parser.read(ini_path, encoding="utf-8")

            if not parser.has_section("ConfigService"):
                logger.error(
                    "Missing [ConfigService] section in %s",
                    ini_path,
                )
                return False

            section = parser["ConfigService"]

            self._config_service_ip = section.get("IP", "").strip()
            self._config_service_token = section.get("Token", "").strip()

            try:
                self._config_service_port = section.getint("PORT", fallback=0)
            except ValueError:
                logger.error("Config-service PORT must be an integer")
                return False

            if (
                not self._config_service_ip
                or not self._config_service_token
                or not 1 <= self._config_service_port <= 65535
            ):
                logger.error(
                    "config.ini must contain valid IP, PORT, and Token "
                    "under [ConfigService]"
                )
                return False

            # ---------------------------------------------
            # 2. Prepare the config-service request
            # ---------------------------------------------
            ip = self._config_service_ip

            if ip.startswith(("http://", "https://")):
                base_url = ip.rstrip("/")
            else:
                base_url = f"http://{ip}:{self._config_service_port}"

            url = f"{base_url}{self.CONFIG_SERVICE_ENDPOINT}"

            request_body = {
                "serviceType": service_id,
            }

            # Assumes the service accepts a Bearer token.
            # Match this header to the authentication header used
            # by CHttpClient::post() in your C++ implementation.
            headers = {
                "Authorization": f"Bearer {self._config_service_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            logger.info(
                "Fetching configuration for ServiceId %s from %s",
                service_id,
                url,
            )

            # ---------------------------------------------
            # 3. Call the config service
            # ---------------------------------------------
            response = requests.post(
                url,
                json=request_body,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                logger.error(
                    "Config service returned HTTP %s: %s",
                    response.status_code,
                    response.text[:1000],
                )
                return False

            # ---------------------------------------------
            # 4. Parse the JSON response
            # ---------------------------------------------
            try:
                response_json = response.json()
            except ValueError as error:
                logger.error(
                    "Config service returned invalid JSON: %s",
                    error,
                )
                return False

            common_config = self._extract_common_config(response_json)
            service_config = self._extract_service_config(response_json)

            if not isinstance(service_config, dict):
                logger.error(
                    "Config service response does not contain a JSON "
                    "configuration object"
                )
                return False

            # ---------------------------------------------
            # 5. Populate the application's configuration
            # ---------------------------------------------
            self._apply_service_config(
                service_config, service_id, common_config=common_config
            )

            self._loaded = True

            logger.info(
                "Configuration loaded successfully for ServiceId %s",
                self._service_id,
            )

            return True

        except requests.RequestException as error:
            logger.error(
                "Request to config service failed: %s",
                error,
            )
            return False

        except (OSError, ValueError, TypeError) as error:
            logger.error(
                "Failed to load service configuration: %s",
                error,
            )
            return False

    @staticmethod
    def _extract_common_config(response_json):
        """Find the common configuration object containing logSetting."""
        pending = [response_json]

        while pending:
            current = pending.pop()

            if isinstance(current, dict):
                if isinstance(current.get("logSetting"), dict):
                    return current

                pending.extend(
                    value
                    for value in current.values()
                    if isinstance(value, (dict, list))
                )

            elif isinstance(current, list):
                pending.extend(current)

        return {}

    @staticmethod
    def _extract_service_config(response_json):
        """
        Accept either a flattened configuration response or a response
        that wraps the configuration in result, data, config, or
        jserviceconfig.
        """
        current = response_json

        for _ in range(5):
            if not isinstance(current, dict):
                return current

            # The flattened response is the expected format.
            if any(key in current for key in ("database", "server", "exchangeBaseAPI")):
                return current

            nested = None

            for key in ("jserviceconfig", "result", "data", "config"):
                if key in current:
                    nested = current[key]
                    break

            if nested is None:
                return current

            if isinstance(nested, str):
                nested = json.loads(nested)

            current = nested

        return current

    def _apply_service_config(self, config, requested_service_id, common_config):
        """Map the service JSON into the application's attributes."""

        database = config.get("database", {})
        server = config.get("server", {})
        exchange_api = config.get("exchangeBaseAPI", {})

        bse_common = config.get("bseCommonConfig", {})
        nse_common = config.get("nseCommonConfig", {})

        if not isinstance(bse_common, dict):
            raise ValueError("'bseCommonConfig' must be a JSON object")

        if not isinstance(nse_common, dict):
            raise ValueError("'nseCommonConfig' must be a JSON object")

        common_config = common_config or {}

        common_log = common_config.get("logSetting", {})
        service_logging = config.get("logging", {})

        if not isinstance(common_log, dict):
            logger.error("'logSetting' must be a JSON object")

        if not isinstance(service_logging, dict):
            logger.error("'logging' must be a JSON object")

        # Convert the common sink into settings understood by the application.
        sink = str(common_log.get("appLogSink", "PRINT")).strip().upper()

        sink_defaults = {
            "PRINT": ("PRINT", False),
            "FILE": ("FILE", True),
            "BOTH": ("BOTH", True),
        }

        destination, store_to_file = sink_defaults.get(
            sink,
            ("PRINT", False),
        )

        service_label = (
            str(config.get("serviceType") or config.get("serviceName") or "application")
            .strip()
            .replace(" ", "_")
        )

        # Common configuration supplies defaults.
        logging_config = {
            "level": common_log.get("logLevel", "INFO"),
            "destination": destination,
            "directory": common_log.get("appLogFolder", "Logs"),
            "storeToFile": store_to_file,
            "logFileName": f"{service_label}.log",
        }

        # Non-empty service-specific values override common defaults.
        for key, value in service_logging.items():
            if value is not None and value != "":
                logging_config[key] = value

        # Populate the existing Config attributes.
        self._logging_destination = str(logging_config["destination"])
        self._logging_level = str(logging_config["level"])
        self._store_to_file = logging_config["storeToFile"] is True
        self._logging_directory = str(logging_config["directory"])
        self._logging_file_name = str(logging_config["logFileName"])

        scraper_config = config.get("scraper", {})

        if not isinstance(database, dict):
            logger.error("'database' must be a JSON object")

        if not isinstance(server, dict):
            logger.error("'server' must be a JSON object")

        if not isinstance(exchange_api, dict):
            logger.error("'exchangeBaseAPI' must be a JSON object")

        # Validate required database settings.
        required_database_keys = (
            "host",
            "port",
            "user",
            "dbName",
            "password",
        )

        missing_database_keys = [
            key
            for key in required_database_keys
            if key not in database or database[key] is None
        ]

        if missing_database_keys:
            logger.error(
                "Missing database configuration keys: "
                + ", ".join(missing_database_keys)
            )

        # Validate required server settings.
        for key in ("host", "port"):
            if key not in server or server[key] is None:
                logger.error(f"Missing server configuration key: {key}")

        # Service metadata.
        self._service_id = int(config.get("serviceId", requested_service_id))
        self._service_name = str(config.get("serviceName", ""))
        self._service_type = str(config.get("serviceType", ""))

        # Database.
        self._database_host = str(database["host"])
        self._database_port = int(database["port"])
        self._database_name = str(database["dbName"])
        self._database_user = str(database["user"])
        self._database_password = str(database["password"])

        # Server.
        self._server_host = str(server["host"])
        self._server_port = int(server["port"])

        if not 1 <= self._database_port <= 65535:
            logger.error("Database port must be between 1 and 65535")

        if not 1 <= self._server_port <= 65535:
            logger.error("Server port must be between 1 and 65535")

        # Exchange API URLs
        self._nse_page_url = str(
            nse_common.get("pageUrl") or exchange_api.get("nsePageUrl", "")
        ).strip()

        self._nse_reports_url = str(
            nse_common.get("capitalMarketUrl")
            or exchange_api.get("nseReportsUrl", "")
        ).strip()

        self._nse_derivatives_url = str(
            nse_common.get("derivativesUrl") or exchange_api.get("nseDerivativesUrl", "")
        ).strip()

        self._bse_api_url = str(
            bse_common.get("apiUrl") or exchange_api.get("bseApiUrl", "")
        ).strip()

        # Optional logging configuration.
        # These remain at their defaults if the JSON doesn't include
        # a "logging" object.
        self._logging_destination = str(logging_config.get("destination", ""))
        self._logging_level = str(logging_config.get("level", ""))
        self._store_to_file = logging_config.get("storeToFile", False) is True
        self._logging_directory = str(logging_config.get("directory", ""))
        self._logging_file_name = str(logging_config.get("logFileName", ""))

        # Optional scraper configuration.
        self._scraper_exchange = str(scraper_config.get("exchange", ""))
        self._scraper_segment = str(scraper_config.get("segment", ""))
        self._scraper_file_type = str(scraper_config.get("fileType", ""))

        # Security configuration
        security_config = config.get("security", {})

        if not isinstance(security_config, dict):
            logger.error("'security' must be a JSON object")

        self._sftp_encryption_key = str(
            security_config.get("sftpEncryptionKey", "")
        ).strip()

        # Retain the complete response configuration for fields
        # that may be added in the future.
        self._service_config = config.copy()

    # ---------------------------------------------
    # Status and service metadata
    # ---------------------------------------------
    def is_loaded(self):
        return self._loaded

    def get_service_id(self):
        return self._service_id

    def get_service_name(self):
        return self._service_name

    def get_service_type(self):
        return self._service_type

    def get_service_config(self):
        return self._service_config.copy()

    # ---------------------------------------------
    # Config-service connection
    # ---------------------------------------------
    def get_config_service_ip(self):
        return self._config_service_ip

    def get_config_service_port(self):
        return self._config_service_port

    # Avoid exposing the token unnecessarily.

    # ---------------------------------------------
    # Logging
    # ---------------------------------------------
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

    # ---------------------------------------------
    # Server
    # ---------------------------------------------
    def get_server_host(self):
        return self._server_host

    def get_server_port(self):
        return self._server_port

    # ---------------------------------------------
    # Database
    # ---------------------------------------------
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

    # ---------------------------------------------
    # Scraper
    # ---------------------------------------------
    def get_scraper_exchange(self):
        return self._scraper_exchange

    def get_scraper_segment(self):
        return self._scraper_segment

    def get_scraper_file_type(self):
        return self._scraper_file_type

    # ---------------------------------------------
    # Exchange API URLs
    # ---------------------------------------------
    def get_nse_page_url(self):
        return self._nse_page_url

    def get_nse_reports_url(self):
        return self._nse_reports_url

    def get_nse_derivatives_url(self):
        return self._nse_derivatives_url

    def get_bse_base_api(self) -> str:
        return str(
            self._service_config.get("bseCommonConfig", {}).get("baseApi", "")
        ).strip()

    def get_bse_scraper_headers(self) -> dict:
        return deepcopy(
            self._service_config.get("bseCommonConfig", {}).get("scraperHeaders", {})
        )

    def get_bse_download_headers(self) -> dict:
        return deepcopy(
            self._service_config.get("bseCommonConfig", {}).get("downloadHeaders", {})
        )

    def get_nse_user_agent(self) -> str:
        return str(
            self._service_config.get("nseCommonConfig", {}).get("userAgent", "")
        ).strip()

    # ---------------------------------------------
    # SFTP password encryption
    # ---------------------------------------------
    def get_sftp_encryption_key(self) -> str:
        """Return the SFTP encryption key from the configuration service."""

        if not self._sftp_encryption_key:
            logger.error(
                "SFTP encryption key is missing from the configuration service."
            )

        return self._sftp_encryption_key


def redact_sensitive_values(value):
    """Redact secrets in nested configuration dictionaries and lists."""

    sensitive_keys = (
        "password",
        "passwd",
        "token",
        "secret",
        "apikey",
        "accesskey",
        "authorization",
        "encryptionkey",
        "privatekey",
        "credential",
    )

    if isinstance(value, dict):
        safe_config = {}

        for key, item in value.items():
            normalized_key = str(key).lower().replace("_", "").replace("-", "")

            if any(secret in normalized_key for secret in sensitive_keys):
                safe_config[key] = "[REDACTED]"
            else:
                safe_config[key] = redact_sensitive_values(item)

        return safe_config

    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]

    return value


def log_loaded_configuration(config: Config, Logger) -> None:
    """Log configuration details once after successful configuration."""

    safe_config = redact_sensitive_values(config.get_service_config())

    effective_logging = {
        "destination": config.get_logging_destination(),
        "level": config.get_logging_level(),
        "store_to_file": config.get_store_to_file(),
        "directory": config.get_logging_directory(),
        "file_name": config.get_logging_file_name(),
    }

    Logger.info(
        f"{'=' * 70}\n"
        "LOADED CONFIGURATION\n"
        f"{'=' * 70}\n\n"
        f"Config service IP: {config.get_config_service_ip()}\n"
        f"Config service port: {config.get_config_service_port()}\n\n"
        "Effective logging configuration:\n"
        f"{json.dumps(effective_logging, indent=2)}\n\n"
        "Service configuration (sensitive values redacted):\n"
        f"{json.dumps(safe_config, indent=2, ensure_ascii=False)}\n\n"
        f"{'=' * 70}\n"
        "CONFIGURATION LOGGING COMPLETED\n"
        f"{'=' * 70}"
    )


def test_config_service_connection():
    """Test config-service connectivity and effective configuration."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config_path = DEFAULT_CONFIG_PATH
    service_id = 81

    print("\n========== CONFIG SERVICE TEST ==========")
    print(f"Config file : {config_path}")
    print(f"Requested Service ID: {service_id}")

    config = Config()

    if not config.load(
        file_path=config_path,
        service_id=service_id,
    ):
        print("\n[FAILED] Could not fetch configuration.")
        print("Check the service IP, port, token, API endpoint, and logs.")
        return False

    print("\n[SUCCESS] Configuration fetched successfully!")

    # Effective logging settings after merging common and service config.
    print("\n---------- Effective Logging Configuration ----------")
    print(f"Destination   : {config.get_logging_destination()}")
    print(f"Level         : {config.get_logging_level()}")
    print(f"Store To File : {config.get_store_to_file()}")
    print(f"Directory     : {config.get_logging_directory()}")
    print(f"Base Filename : {config.get_logging_file_name()}")

    print("\n---------- Service Details ----------")
    print(f"Service ID   : {config.get_service_id()}")
    print(f"Service Name : {config.get_service_name()}")
    print(f"Service Type : {config.get_service_type()}")

    print("\n---------- Database Configuration ----------")
    print(f"Host     : {config.get_database_host()}")
    print(f"Port     : {config.get_database_port()}")
    print(f"Database : {config.get_database_name()}")
    print(f"User     : {config.get_database_user()}")
    print("Password : [HIDDEN]")

    print("\n---------- Server Configuration ----------")
    print(f"Host : {config.get_server_host()}")
    print(f"Port : {config.get_server_port()}")

    print("\n---------- Exchange APIs ----------")
    print(f"NSE Page URL        : {config.get_nse_page_url()}")
    print(f"NSE Reports URL     : {config.get_nse_reports_url()}")
    print(f"NSE Derivatives URL : {config.get_nse_derivatives_url()}")
    print(f"NSE User Agents     : {config.get_nse_user_agent}")
    print(f"BSE Base API URL    : {config.get_bse_base_api()}")
    print(f"BSE Download Headers: {config.get_bse_download_headers}")
    print(f"BSE Scraper Headers : {config.get_bse_scraper_headers}")

    print("\n---------- Service-Specific JSON ----------")

    # Deep copy prevents password masking from modifying stored config.
    safe_config = deepcopy(config.get_service_config())

    database_config = safe_config.get("database")
    if isinstance(database_config, dict) and "password" in database_config:
        database_config["password"] = "[HIDDEN]"

    print(json.dumps(safe_config, indent=4))

    print("\n========== TEST COMPLETED ==========")
    return True


if __name__ == "__main__":
    test_config_service_connection()
