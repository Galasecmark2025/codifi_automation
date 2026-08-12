import psycopg


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "learning_db",
    "user": "postgres",
    "password": "PgDev@2026#Strong",
}


def get_connection():

    connection = psycopg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )

    return connection


def test_connection():

    try:

        connection = get_connection()

        print("PostgreSQL connected successfully.")

        connection.close()

    except Exception as error:

        print("PostgreSQL connection failed.")
        print("Error:", error)


if __name__ == "__main__":
    test_connection()