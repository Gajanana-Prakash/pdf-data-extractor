from extractor import extract_text, extract_tables
from ocr import extract_text_with_ocr
from parser import extract_data, extract_items_from_tables  # 🔁 fallback
from layout_parser import extract_layout_data  # 🔥 NEW
from db import save_to_db, create_table
from logger import setup_logger

import logging
import json
import os


def process_pdf(pdf_path):
    try:
        logging.info(f"Processing file: {pdf_path}")

        # ============================================
        # STEP 1 — Extract text (for fallback use)
        # ============================================
        text = extract_text(pdf_path)

        # ============================================
        # STEP 2 — OCR fallback
        # ============================================
        if not text.strip():
            logging.warning(f"No text found in {pdf_path}. Using OCR...")
            text = extract_text_with_ocr(pdf_path)

        if not text.strip():
            logging.error(f"Text extraction failed: {pdf_path}")
            return

        # ============================================
        # 🔥 STEP 3 — Layout-Based Extraction (NEW)
        # ============================================
        layout_output = extract_layout_data(pdf_path)

        # ============================================
        # 🔁 STEP 4 — Fallback to Regex if needed
        # ============================================
        if not layout_output["items"]:
            logging.warning("Layout extraction failed. Using regex fallback...")

            invoice_data = extract_data(text)

            tables = extract_tables(pdf_path)
            items = extract_items_from_tables(tables)

            layout_output = {
                "invoice_details": invoice_data,
                "items": items
            }

        final_output = layout_output

        # ============================================
        # STEP 5 — Save JSON Output
        # ============================================
        os.makedirs("output", exist_ok=True)

        file_name = os.path.basename(pdf_path).replace(".pdf", ".json")
        output_path = os.path.join("output", file_name)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        logging.info(f"JSON saved: {output_path}")

        # ============================================
        # STEP 6 — Save to Database
        # ============================================
        save_to_db(final_output)
        logging.info(f"Saved to database: {pdf_path}")

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        print(f"Error in {pdf_path}: {e}")


def main():
    setup_logger()
    logging.info("Application started.")

    # Create DB table if not exists
    create_table()

    # Ensure folders exist
    os.makedirs("pdfs", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    pdf_folder = "pdfs"
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]

    if not pdf_files:
        logging.warning("No PDF files found.")
        print("No PDF files found in 'pdfs/' folder.")
        return

    # Process each PDF
    for file in pdf_files:
        pdf_path = os.path.join(pdf_folder, file)
        process_pdf(pdf_path)

    logging.info("All files processed successfully.")
    print("✅ Done. Check 'output/' folder.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}")
        print("Application crashed:", e)