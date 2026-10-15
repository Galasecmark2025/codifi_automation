import psycopg


def get_connection(config):
    connection = psycopg.connect(
        host=config.get_database_host(),
        port=config.get_database_port(),
        dbname=config.get_database_name(),
        user=config.get_database_user(),
        password=config.get_database_password(),
    )

    return connection


def test_connection(config):
    try:
        connection = get_connection(config)
        print("PostgreSQL connected successfully.")
        connection.close()

    except Exception as error:
        print("PostgreSQL connection failed.")
        print("Error:", error)


if __name__ == "__main__":
    test_connection()
