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


# ============================================
# 🔁 MULTIPROCESS WRAPPER
# ============================================
def process_wrapper(file):
    pdf_path = os.path.join(PDF_FOLDER, file)
    process_pdf(pdf_path)


# ============================================
# 🚀 MAIN PROCESS FUNCTION (PRODUCTION SAFE)
# ============================================
def process_pdf(pdf_path):
    try:
        start = time.time()

        logging.info(f"Processing file: {pdf_path}")
        print(f"\n🔄 Processing: {pdf_path}")

        # ============================================
        # 🔐 STEP 0 — FILE HASH
        # ============================================
        file_hash = generate_file_hash(pdf_path)

        if not file_hash:
            logging.error("Hash generation failed")
            return {
                "status": "failed",
                "reason": "Hash generation failed"
            }

        print(f"🔐 File Hash: {file_hash}")

        # Duplicate check
        if is_duplicate(file_hash):
            logging.warning(f"Duplicate skipped: {pdf_path}")
            return {
                "status": "duplicate",
                "file": pdf_path
            }

        # ============================================
        # 📝 STEP 1 — TEXT EXTRACTION
        # ============================================
        text = extract_text(pdf_path)

        # OCR fallback
        if not text.strip():
            logging.warning("No text found → Using OCR")
            print("⚠️ No text found → Using OCR")
            text = extract_text_with_ocr(pdf_path)

        # ============================================
        # 🧠 STEP 2 — TEXT VALIDATION (FIXED)
        # ============================================
        clean_text = text.strip()

        if not clean_text:
            logging.error("❌ No text extracted even after OCR")
            return {
                "status": "failed",
                "reason": "No readable text found (OCR failed)",
                "file": pdf_path
            }

        print(f"✅ Text length: {len(clean_text)}")

        # Weak text handling
        weak_text = False
        if len(clean_text) < 50:
            weak_text = True
            logging.warning("⚠️ Weak text detected")
            print("⚠️ Weak text → extraction may be poor")

        # ============================================
        # 📐 STEP 3 — LAYOUT EXTRACTION
        # ============================================
        layout_output = extract_layout_data(pdf_path) or {
            "invoice_details": {},
            "items": []
        }

        # ============================================
        # 🤖 STEP 4 — SMART EXTRACTION
        # ============================================
        invoice_data, confidence = smart_extract_data(clean_text)

        print(f"🧠 Confidence: {confidence}")

        # Force fallback if weak text
        if weak_text:
            confidence = 0

        if confidence < CONFIDENCE_THRESHOLD:
            logging.warning("Using regex fallback")
            print("⚠️ Using regex fallback")
            invoice_data = extract_data(clean_text)

        layout_output["invoice_details"] = invoice_data

        # ============================================
        # 📦 STEP 5 — ITEMS FALLBACK
        # ============================================
        if not layout_output["items"]:
            logging.warning("Items fallback triggered")
            tables = extract_tables(pdf_path)
            layout_output["items"] = extract_items_from_tables(tables)

        # ============================================
        # 🆔 STEP 6 — ADD IDS
        # ============================================
        final_output = layout_output
        final_output["document_id"] = str(uuid.uuid4())
        final_output["file_hash"] = file_hash

        print(f"🆔 Document ID: {final_output['document_id']}")

        # ============================================
        # 💾 STEP 7 — SAVE JSON
        # ============================================
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        output_path = os.path.join(
            OUTPUT_FOLDER,
            os.path.basename(pdf_path).replace(".pdf", ".json")
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        print(f"💾 JSON saved: {output_path}")

        # ============================================
        # 🗄️ STEP 8 — SAVE TO DB
        # ============================================
        save_to_db(final_output, file_hash)
        print("💾 Saved to DB")

        # ============================================
        # ⏱️ STEP 9 — TIME TRACKING
        # ============================================
        end = time.time()
        print(f"⏱️ Time: {round(end - start, 2)} sec")

        return final_output

    except Exception as e:
        logging.exception(f"🔥 FULL ERROR in file: {pdf_path}")
        return {
            "status": "error",
            "message": str(e),
            "file": pdf_path
        }


# ============================================
# 🧠 MAIN FUNCTION
# ============================================
def main():
    setup_logger()
    logging.info("Application started.")
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
        logging.error(f"Multiprocessing failed: {str(e)}")
        print("⚠️ Multiprocessing failed → fallback")

        for file in pdf_files:
            process_pdf(os.path.join(PDF_FOLDER, file))

    print("\n🎉 All files processed!")


# ============================================
# 🚀 ENTRY POINT
# ============================================
if __name__ == "__main__":
    main()