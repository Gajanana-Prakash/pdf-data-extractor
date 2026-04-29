from extractor import extract_text, extract_tables
from ocr import extract_text_with_ocr
from parser import extract_data, extract_items_from_tables
from layout_parser import extract_layout_data
from smart_parser import smart_extract_data
from db import save_to_db, create_table, is_duplicate
from logger import setup_logger
from utils import generate_file_hash

from config import CONFIDENCE_THRESHOLD, PDF_FOLDER, OUTPUT_FOLDER

import logging
import json
import os
import uuid
import time

from multiprocessing import Pool


def process_wrapper(file):
    pdf_path = os.path.join(PDF_FOLDER, file)
    process_pdf(pdf_path)


def process_pdf(pdf_path):
    try:
        start = time.time()

        logging.info(f"Processing file: {pdf_path}")
        print(f"\n🔄 Processing: {pdf_path}")

        # 🔐 STEP 0 — Generate Hash
        file_hash = generate_file_hash(pdf_path)

        if not file_hash:
            print("❌ Hash generation failed")
            return

        print(f"🔐 File Hash: {file_hash}")

        # 🔁 Duplicate Check
        if is_duplicate(file_hash):
            print("⚠️ Duplicate file detected → Skipping")
            logging.warning(f"Duplicate skipped: {pdf_path}")
            return

        # STEP 1 — Extract text
        text = extract_text(pdf_path)

        # STEP 2 — OCR fallback
        if not text.strip():
            print("⚠️ No text found → Using OCR")
            text = extract_text_with_ocr(pdf_path)

        if not text.strip():
            print("❌ Failed to extract text")
            return

        print(f"✅ Text length: {len(text)}")

        # STEP 3 — Layout
        layout_output = extract_layout_data(pdf_path) or {
            "invoice_details": {},
            "items": []
        }

        # STEP 4 — Smart extraction
        invoice_data, confidence = smart_extract_data(text)
        print(f"🧠 Confidence: {confidence}")

        if confidence < CONFIDENCE_THRESHOLD:
            print("⚠️ Using regex fallback")
            invoice_data = extract_data(text)

        layout_output["invoice_details"] = invoice_data

        # STEP 5 — Items fallback
        if not layout_output["items"]:
            tables = extract_tables(pdf_path)
            layout_output["items"] = extract_items_from_tables(tables)

        # STEP 6 — Add IDs
        final_output = layout_output
        final_output["document_id"] = str(uuid.uuid4())
        final_output["file_hash"] = file_hash

        print(f"🆔 Document ID: {final_output['document_id']}")

        # STEP 7 — Save JSON
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        output_path = os.path.join(
            OUTPUT_FOLDER,
            os.path.basename(pdf_path).replace(".pdf", ".json")
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        print(f"💾 JSON saved: {output_path}")

        # STEP 8 — Save DB
        save_to_db(final_output, file_hash)
        print("💾 Saved to DB")

        end = time.time()
        print(f"⏱️ Time: {round(end - start, 2)} sec")

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        print(f"❌ Error: {e}")


def main():
    setup_logger()
    print("🚀 Application Started")

    create_table()

    os.makedirs(PDF_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith(".pdf")]

    print(f"📂 PDFs: {pdf_files}")

    if not pdf_files:
        print("❌ No PDFs found")
        return

    try:
        with Pool(4) as p:
            p.map(process_wrapper, pdf_files)

    except Exception as e:
        print("⚠️ Multiprocessing failed → fallback")

        for file in pdf_files:
            process_pdf(os.path.join(PDF_FOLDER, file))

    print("\n🎉 All files processed!")


if __name__ == "__main__":
    main()