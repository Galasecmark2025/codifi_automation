import time

import psycopg

from exchange_scraper_automation.observability.logger import Logger

MAX_RETRIES = 3
RETRY_DELAY = 2


def get_connection(config):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            connection = psycopg.connect(
                host=config.get_database_host(),
                port=config.get_database_port(),
                dbname=config.get_database_name(),
                user=config.get_database_user(),
                password=config.get_database_password(),
            )

            Logger.info(
                f"PostgreSQL connection established | "
                f"Attempt={attempt}/{MAX_RETRIES} | "
                f"Host={config.get_database_host()} | "
                f"Port={config.get_database_port()} | "
                f"Database={config.get_database_name()}"
            )

            return connection

        except psycopg.OperationalError:
            Logger.error(
                f"PostgreSQL connection attempt failed | Attempt={attempt}/{MAX_RETRIES}",
            )

            if attempt == MAX_RETRIES:
                Logger.error("PostgreSQL connection failed after all retry attempts.")
                raise

            time.sleep(RETRY_DELAY)

        except Exception:
            Logger.error(
                f"Unexpected error while connecting to PostgreSQL | Attempt={attempt}/{MAX_RETRIES}"
            )
            raise


def test_connection(config):
    connection = None
    try:
        connection = get_connection(config)
        Logger.info("PostgreSQL connection test successful.")
        return True

    except Exception as error:
        Logger.error("PostgreSQL connection test failed.")
        return False

    finally:
        if connection is not None:
            connection.close()
            Logger.info("PostgreSQL test connection closed.")


if __name__ == "__main__":
    test_connection()
