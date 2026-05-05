"""
main.py — PDF invoice extraction pipeline orchestrator.
"""

from extractor import extract_text, extract_tables
from ocr import extract_text_with_ocr
from parser import extract_data, extract_items_from_tables
from layout_parser import extract_layout_data
from smart_parser import smart_extract_data
from scanned_extractor import extract_scanned_invoice
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
    process_pdf(os.path.join(PDF_FOLDER, file))


def process_pdf(pdf_path):
    try:
        start = time.time()
        logging.info(f"Processing: {pdf_path}")
        print(f"\n🔄 Processing: {pdf_path}")

        # ── STEP 0: Deduplication ─────────────────────────────────────────
        file_hash = generate_file_hash(pdf_path)
        if not file_hash:
            return {"status": "failed", "reason": "Hash generation failed"}
        print(f"🔐 File Hash: {file_hash}")

        if is_duplicate(file_hash):
            logging.warning(f"Duplicate skipped: {pdf_path}")
            return {"status": "duplicate", "file": pdf_path}

        # ── STEP 1: Try direct text extraction ───────────────────────────
        text = extract_text(pdf_path)
        is_scanned = not text.strip()

        if is_scanned:
            logging.warning("No text found → scanned PDF detected")
            print("⚠️ No text → scanned PDF")
        else:
            print(f"✅ Text length: {len(text.strip())}")

        # ── STEP 2: ROUTE based on PDF type ──────────────────────────────
        #
        # FIX: Previously all PDFs — including scanned ones — went through
        # the same pipeline: text → smart_parser → regex fallback.
        # For scanned PDFs this always produced garbage because:
        #   a) OCR text had garbled labels (no "Invoice No." — just "Inyvence et")
        #   b) Multi-column layout was merged into wrong reading order
        #   c) Total fell back to max(all numbers) = ZIP code
        #
        # Fix: scanned PDFs now go through scanned_extractor which uses
        # position-aware bounding-box extraction instead of text parsing.

        if is_scanned:
            # ── SCANNED PDF PATH ─────────────────────────────────────────
            print("🔍 Using position-aware scanned extractor")
            scanned_details, scanned_items, confidence = extract_scanned_invoice(pdf_path)
            print(f"🧠 Scanned extractor confidence: {confidence}")

            if confidence < CONFIDENCE_THRESHOLD:
                # Fallback: try text OCR + smart_parser
                logging.warning("Scanned extractor low confidence → OCR text fallback")
                print("⚠️ Low confidence → OCR text fallback")
                ocr_text = extract_text_with_ocr(pdf_path)
                if ocr_text.strip():
                    fallback_data, fb_conf = smart_extract_data(ocr_text)
                    if fb_conf > confidence:
                        scanned_details = fallback_data
                        scanned_items   = []
                        confidence      = fb_conf

            final_output = {
                "invoice_details": scanned_details,
                "items": scanned_items,
            }

        else:
            # ── TEXT PDF PATH ─────────────────────────────────────────────
            clean_text = text.strip()
            weak_text = len(clean_text) < 50

            if weak_text:
                logging.warning("Weak text detected")
                print("⚠️ Weak text → may fallback")

            # Layout extraction (handles real PDF table objects)
            layout_output = extract_layout_data(pdf_path) or {"invoice_details": {}, "items": []}

            # Smart extraction (regex + heuristics)
            invoice_data, confidence = smart_extract_data(clean_text)
            print(f"🧠 Confidence: {confidence}")

            if weak_text:
                confidence = 0

            if confidence < CONFIDENCE_THRESHOLD:
                logging.warning("Using regex fallback")
                print("⚠️ Using regex fallback")
                invoice_data = extract_data(clean_text)

            # Merge layout + text parser results
            # layout values are base; smart_parser overrides when not None
            layout_details = layout_output.get("invoice_details", {})

            # Clean up legacy 'total' key from layout_parser
            if "total" in layout_details and "total_amount" not in layout_details:
                layout_details["total_amount"] = layout_details.pop("total")
            elif "total" in layout_details:
                layout_details.pop("total")

            merged = {
                **layout_details,
                **{k: v for k, v in invoice_data.items() if v is not None}
            }
            layout_output["invoice_details"] = merged

            # Items fallback
            if not layout_output["items"]:
                logging.warning("Items fallback triggered")
                tables = extract_tables(pdf_path)
                layout_output["items"] = extract_items_from_tables(tables)

            # Auto-compute missing line totals
            for item in layout_output["items"]:
                if not item.get("amount") and item.get("quantity") and item.get("unit_price"):
                    item["amount"] = round(item["quantity"] * item["unit_price"], 2)

            final_output = layout_output

        # ── STEP 3: Add metadata ──────────────────────────────────────────
        final_output["document_id"]  = str(uuid.uuid4())
        final_output["file_hash"]    = file_hash
        final_output["source_file"]  = os.path.basename(pdf_path)
        print(f"🆔 Document ID: {final_output['document_id']}")

        # ── STEP 4: Save JSON ─────────────────────────────────────────────
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        output_path = os.path.join(
            OUTPUT_FOLDER,
            os.path.basename(pdf_path).replace(".pdf", ".json")
        )
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
        print(f"💾 JSON saved: {output_path}")

        # ── STEP 5: Save to DB ────────────────────────────────────────────
        save_to_db(final_output, file_hash)
        print("💾 Saved to DB")

        elapsed = round(time.time() - start, 2)
        print(f"⏱️ Time: {elapsed} sec")
        return final_output

    except Exception as e:
        logging.exception(f"🔥 ERROR in: {pdf_path}")
        return {"status": "error", "message": str(e), "file": pdf_path}


def main():
    setup_logger()
    logging.info("Application started.")
    print("🚀 Application Started")

    create_table()
    os.makedirs(PDF_FOLDER,  exist_ok=True)
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
        logging.error(f"Multiprocessing failed: {e}")
        print("⚠️ Multiprocessing failed → sequential fallback")
        for file in pdf_files:
            process_pdf(os.path.join(PDF_FOLDER, file))

    print("\n🎉 All files processed!")


if __name__ == "__main__":
    main()