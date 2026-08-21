import logging
import os


LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "automation.log")


def get_logger(name="codifi_automation"):

    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --------------------------------------------------------
    # File Handler
    # --------------------------------------------------------

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )

    file_handler.setLevel(logging.DEBUG)

    # --------------------------------------------------------
    # Console Handler
    # --------------------------------------------------------

    console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)

    # --------------------------------------------------------
    # Common Format
    # --------------------------------------------------------

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger