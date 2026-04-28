from extractor import extract_text, extract_tables
from ocr import extract_text_with_ocr
from parser import extract_data, extract_items_from_tables
from layout_parser import extract_layout_data
from smart_parser import smart_extract_data
from db import save_to_db, create_table
from logger import setup_logger

import logging
import json
import os


def process_pdf(pdf_path):
    try:
        logging.info(f"Processing file: {pdf_path}")
        print(f"\n🔄 Processing: {pdf_path}")

        # ============================================
        # STEP 1 — Extract text
        # ============================================
        text = extract_text(pdf_path)

        # ============================================
        # STEP 2 — OCR fallback
        # ============================================
        if not text.strip():
            logging.warning(f"No text found in {pdf_path}. Using OCR...")
            print("⚠️ No text found → Using OCR")
            text = extract_text_with_ocr(pdf_path)

        if not text.strip():
            logging.error(f"Text extraction failed: {pdf_path}")
            print("❌ Failed to extract text even after OCR")
            return

        print(f"✅ Text extracted (length: {len(text)})")

        # ============================================
        # STEP 3 — Layout extraction
        # ============================================
        layout_output = extract_layout_data(pdf_path)

        if not layout_output:
            layout_output = {
                "invoice_details": {},
                "items": []
            }

        # ============================================
        # 🧠 STEP 4 — SMART EXTRACTION (UPDATED)
        # ============================================
        invoice_data, confidence = smart_extract_data(text)

        logging.info(f"Smart confidence: {confidence}")
        print(f"🧠 Smart Confidence: {confidence}")

        # 🔁 Intelligent fallback
        if confidence < 0.6:
            logging.warning("Low confidence. Switching to regex fallback")
            print("⚠️ Low confidence → Using regex fallback")
            invoice_data = extract_data(text)

        layout_output["invoice_details"] = invoice_data

        # ============================================
        # 🔁 STEP 5 — Items fallback
        # ============================================
        if not layout_output["items"]:
            logging.warning("Layout items failed. Using table extraction fallback")
            print("⚠️ Layout items failed → Using table fallback")

            tables = extract_tables(pdf_path)
            items = extract_items_from_tables(tables)

            layout_output["items"] = items

        final_output = layout_output

        # ============================================
        # STEP 6 — Save JSON
        # ============================================
        os.makedirs("output", exist_ok=True)

        file_name = os.path.basename(pdf_path).replace(".pdf", ".json")
        output_path = os.path.join("output", file_name)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        logging.info(f"JSON saved: {output_path}")
        print(f"💾 JSON saved: {output_path}")

        # ============================================
        # STEP 7 — Save to DB
        # ============================================
        save_to_db(final_output)
        logging.info(f"Saved to database: {pdf_path}")
        print("💾 Saved to database")

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        print(f"❌ Error: {e}")


def main():
    setup_logger()
    logging.info("Application started.")
    print("🚀 Application Started")

    create_table()

    os.makedirs("pdfs", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    pdf_folder = "pdfs"
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]

    print(f"📂 Found PDFs: {pdf_files}")

    if not pdf_files:
        logging.warning("No PDF files found.")
        print("❌ No PDF files found in 'pdfs/' folder.")
        return

    for file in pdf_files:
        pdf_path = os.path.join(pdf_folder, file)
        process_pdf(pdf_path)

    logging.info("All files processed successfully.")
    print("\n🎉 All files processed successfully!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}")
        print("❌ Application crashed:", e)