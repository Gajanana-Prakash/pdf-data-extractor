import pdfplumber
import logging
import pandas as pd


def extract_text(pdf_path):
    """
    Extract text from PDF using pdfplumber
    """
    text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"

        logging.info(f"Text extracted using pdfplumber for {pdf_path}")
        return text

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")
        return ""


def extract_tables(pdf_path):
    """
    Extract tables using layout (Day 3 upgrade)
    """
    tables_data = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()

                for table in tables:
                    if table:
                        # Convert table into DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0])
                        tables_data.append(df)

        logging.info(f"Tables extracted from {pdf_path}")
        return tables_data

    except Exception as e:
        logging.error(f"Error extracting tables: {str(e)}")
        return []