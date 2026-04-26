import psycopg2
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Creates and returns a new database connection using .env credentials."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )


def create_table():
    """
    Creates the invoices table if it does not already exist.
    Call this once at startup inside main().

    FIX (Missing Item 2): The original project had no CREATE TABLE code at all.
    Without this, every INSERT would fail with 'relation does not exist'.
    """
    # FIX (Bug 1): conn and cursor initialized to None BEFORE try block.
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id         SERIAL PRIMARY KEY,
                data       JSONB     NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        logging.info("Table 'invoices' is ready.")

    except Exception as e:
        logging.error(f"Table creation error: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_to_db(data):
    """
    Inserts extracted invoice data as JSON into the invoices table.

    FIX (Bug 1): conn and cursor are now initialized to None BEFORE the try block.
    In the original code they were only assigned inside try, so if
    psycopg2.connect() raised an exception (e.g. wrong password, Postgres not
    running), the finally block would crash with:
        NameError: name 'cursor' is not defined
    Now the finally block safely checks 'if cursor' and 'if conn' without error.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = "INSERT INTO invoices (data) VALUES (%s);"
        cursor.execute(query, [json.dumps(data)])

        conn.commit()
        logging.info("Data inserted into DB successfully.")

    except Exception as e:
        logging.error(f"DB Error: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()