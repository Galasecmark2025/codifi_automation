# logger.py

from datetime import datetime
from enum import IntEnum
from pathlib import Path


class LogLevel(IntEnum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class LogDestination(IntEnum):
    PRINT = 0
    FILE = 1
    BOTH = 2


class Logger:
    _log_level = LogLevel.INFO
    _destination = LogDestination.BOTH
    _store_to_file = True
    _log_directory = "logs"
    _log_file_name = "scheduler"
    # size_t      max_file_bytes { 2097152 };

    @classmethod
    def configure(cls, config):
        cls._destination = cls._get_destination(config.get_logging_destination())
        cls._log_level = cls._get_log_level(config.get_logging_level())
        cls._store_to_file = config.get_store_to_file()

        directory = config.get_logging_directory().strip()
        file_name = config.get_logging_file_name().strip()

        cls._log_directory = Path(directory) if directory else "logs"
        cls._log_file_name = file_name

        if cls._store_to_file:
            if cls._log_directory is None:
                Logger.error(
                    "Logging directory is required when StoreToFile is enabled"
                )

            if not cls._log_file_name:
                Logger.error("Log filename is required when StoreToFile is enabled")

            try:
                cls._log_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                # log_file = cls._log_directory / cls._log_file_name
                log_file = cls._get_log_file_path(datetime.now())

                # Check that the log file can be opened for appending.
                with log_file.open("a", encoding="utf-8"):
                    pass

            except OSError as error:
                Logger.error(f"Unable to initialize file logging: {error}")

    @classmethod
    def set_store_to_file(cls, store_to_file: bool):
        cls._store_to_file = store_to_file

    @classmethod
    def set_log_level(cls, log_level: LogLevel):
        cls._log_level = log_level

    @classmethod
    def set_log_destination(cls, destination: LogDestination):
        cls._destination = destination

    @classmethod
    def debug(cls, message: str):
        cls.log(LogLevel.DEBUG, message)

    @classmethod
    def info(cls, message: str):
        cls.log(LogLevel.INFO, message)

    @classmethod
    def warning(cls, message: str):
        cls.log(LogLevel.WARNING, message)

    @classmethod
    def error(cls, message: str):
        cls.log(LogLevel.ERROR, message)

    @classmethod
    def log(cls, log_level: LogLevel, message: str):

        if log_level < cls._log_level:
            return

        # current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()

        log_message = (
            f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"[{cls.get_log_level_string(log_level)}] "
            f"{message}"
        )

        if cls._destination in (LogDestination.PRINT, LogDestination.BOTH, ):
            print(log_message)

        if cls._store_to_file:
            log_file = cls._get_log_file_path(current_time)

            with log_file.open("a", encoding="utf-8") as file:
                file.write(log_message + "\n")

    @staticmethod
    def _get_log_level(level: str) -> LogLevel:
        levels = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
        }

        return levels.get(level.upper(), LogLevel.DEBUG)

    @staticmethod
    def _get_destination(destination: str) -> LogDestination:
        destinations = {
            "PRINT": LogDestination.PRINT,
            "FILE": LogDestination.FILE,
            "BOTH": LogDestination.BOTH,
        }

        return destinations.get(destination.upper(), LogDestination.PRINT, )

    @staticmethod
    def get_log_level_string(log_level: LogLevel) -> str:
        return {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.WARNING: "WARNING",
            LogLevel.ERROR: "ERROR",
        }.get(log_level, "UNKNOWN")

    @classmethod
    def _get_log_file_path(cls, current_time: datetime) -> Path:
        """Return the log file path for the current date."""
        if cls._log_directory is None:
            Logger.error("Logging directory has not been configured")

        if not cls._log_file_name:
            Logger.error("Log filename has not been configured")

        configured_file = Path(cls._log_file_name)
        dated_file_name = (
            f"{configured_file.stem}_{current_time:%Y-%m-%d}"
            f"{configured_file.suffix}"
        )

        return cls._log_directory / dated_file_name
