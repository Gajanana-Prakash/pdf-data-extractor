import psycopg2
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )


def create_table():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                file_hash TEXT UNIQUE,   -- 🔥 NEW (IMPORTANT)
                data JSONB NOT NULL,
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


def is_duplicate(file_hash):
    """
    Check if file already exists in DB
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM invoices WHERE file_hash = %s", (file_hash,))
        result = cursor.fetchone()

        return result is not None

    except Exception as e:
        logging.error(f"Duplicate check error: {str(e)}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_to_db(data, file_hash):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = "INSERT INTO invoices (file_hash, data) VALUES (%s, %s);"
        cursor.execute(query, (file_hash, json.dumps(data)))

        conn.commit()
        logging.info("Data inserted into DB successfully.")

    except Exception as e:
        logging.error(f"DB Error: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()