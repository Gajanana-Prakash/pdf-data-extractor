from extractor import extract_text, extract_tables
from ocr import extract_text_with_ocr
from parser import extract_data, extract_items_from_tables
from layout_parser import extract_layout_data
from smart_parser import smart_extract_data
from db import save_to_db, create_table
from logger import setup_logger

from config import CONFIDENCE_THRESHOLD, PDF_FOLDER, OUTPUT_FOLDER

import logging
import json
import os
import uuid
import time

# 🔥 NEW — multiprocessing
from multiprocessing import Pool


# ============================================
# 🔁 WRAPPER FOR MULTIPROCESSING
# ============================================
def process_wrapper(file):
    pdf_path = os.path.join(PDF_FOLDER, file)
    process_pdf(pdf_path)


def process_pdf(pdf_path):
    try:
        start = time.time()   # ⏱️ START TIMER

        logging.info(f"Processing file: {pdf_path}")
        print(f"\n🔄 Processing: {pdf_path}")

        # STEP 1 — Extract text
        text = extract_text(pdf_path)

        # STEP 2 — OCR fallback
        if not text.strip():
            logging.warning(f"No text found in {pdf_path}. Using OCR...")
            print("⚠️ No text found → Using OCR")
            text = extract_text_with_ocr(pdf_path)

        if not text.strip():
            logging.error(f"Text extraction failed: {pdf_path}")
            print("❌ Failed to extract text even after OCR")
            return

        print(f"✅ Text extracted (length: {len(text)})")

        # STEP 3 — Layout extraction
        layout_output = extract_layout_data(pdf_path)

        if not layout_output:
            layout_output = {
                "invoice_details": {},
                "items": []
            }

        # STEP 4 — Smart extraction
        invoice_data, confidence = smart_extract_data(text)

        logging.info(f"Smart confidence: {confidence}")
        print(f"🧠 Smart Confidence: {confidence}")

        # Intelligent fallback
        if confidence < CONFIDENCE_THRESHOLD:
            logging.warning("Low confidence. Switching to regex fallback")
            print("⚠️ Low confidence → Using regex fallback")
            invoice_data = extract_data(text)

        layout_output["invoice_details"] = invoice_data

        # STEP 5 — Items fallback
        if not layout_output["items"]:
            logging.warning("Layout items failed. Using table extraction fallback")
            print("⚠️ Layout items failed → Using table fallback")

            tables = extract_tables(pdf_path)
            items = extract_items_from_tables(tables)

            layout_output["items"] = items

        # STEP 6 — Unique ID
        final_output = layout_output
        final_output["document_id"] = str(uuid.uuid4())

        print(f"🆔 Document ID: {final_output['document_id']}")

        # STEP 7 — Save JSON
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        file_name = os.path.basename(pdf_path).replace(".pdf", ".json")
        output_path = os.path.join(OUTPUT_FOLDER, file_name)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        logging.info(f"JSON saved: {output_path}")
        print(f"💾 JSON saved: {output_path}")

        # STEP 8 — Save DB
        save_to_db(final_output)
        logging.info(f"Saved to database: {pdf_path}")
        print("💾 Saved to database")

        end = time.time()   # ⏱️ END TIMER
        print(f"⏱️ Time taken: {round(end - start, 2)} sec")

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        print(f"❌ Error in file: {os.path.basename(pdf_path)}")


def main():
    setup_logger()
    logging.info("Application started.")
    print("🚀 Application Started")

    create_table()

    os.makedirs(PDF_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith(".pdf")]

    print(f"📂 Found PDFs: {pdf_files}")

    if not pdf_files:
        logging.warning("No PDF files found.")
        print("❌ No PDF files found in 'pdfs/' folder.")
        return

    # ============================================
    # 🚀 MULTIPROCESSING (PARALLEL EXECUTION)
    # ============================================
    try:
        with Pool(4) as p:   # 👈 4 workers (you can change)
            p.map(process_wrapper, pdf_files)

    except Exception as e:
        logging.error(f"Multiprocessing failed: {str(e)}")
        print("⚠️ Falling back to sequential processing...")

        # fallback safe loop
        for file in pdf_files:
            pdf_path = os.path.join(PDF_FOLDER, file)
            process_pdf(pdf_path)

    logging.info("All files processed successfully.")
    print("\n🎉 All files processed successfully!")


if __name__ == "__main__":
    main()