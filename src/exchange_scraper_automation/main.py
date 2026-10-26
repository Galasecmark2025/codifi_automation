"""Application entry point for exchange scraper automation."""

from __future__ import annotations

from exchange_scraper_automation.application.task_application import \
    TaskApplication
from exchange_scraper_automation.config import Config, log_loaded_configuration
from exchange_scraper_automation.data_paths import DATA_ROOT
from exchange_scraper_automation.observability.logger import Logger


def main() -> None:
    """Load configuration, initialize logging, and start the HTTP listener."""
    config = Config()
    if not config.load():
        Logger.error("Failed to load configuration. Application startup cancelled.")
        return

    Logger.configure(config)

    # Log configuration once during startup.
    log_loaded_configuration(config, Logger)

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    Logger.info(
        f"Data root ready: {DATA_ROOT}\n\n"
        f"{'=' * 70}\n"
        "EXCHANGE SCRAPER AUTOMATION STARTING\n"
        f"{'=' * 70}"
    )

    application = TaskApplication(config)
    application.start_listener()


if __name__ == "__main__":
    main()
