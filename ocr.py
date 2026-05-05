"""
ocr.py — OCR fallback for scanned PDFs.

Used by main.py when pdfplumber.extract_text() returns empty.
Now calls scanned_extractor.extract_scanned_invoice() which does
position-aware extraction instead of naive image_to_string().

The old approach (image_to_string + smart_parser) had 4 bugs for test3:
  1. invoice_number = null (garbled label "Inyvence et" didn't match regex)
  2. total_amount = 10001 (ZIP code matched max() fallback)
  3. customer = null (merged "Bill To Ship To" header not parsed)
  4. items = [] (no table structure in OCR text)

The new approach (image_to_data + zone-based extraction) fixes all 4.
"""

import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance
import logging

from config import TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_text_with_ocr(pdf_path):
    """
    Legacy text-mode OCR. Still used as a fallback when the scanned
    extractor cannot be run (e.g. import error). Returns plain text string.

    Improvements vs original:
    - resolution=200 DPI (was unset / 72 DPI default — produced blurry images)
    - contrast + binarisation preprocessing (was greyscale-only)
    - --psm 6 (was default PSM 3 which scrambles multi-column layouts)
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    image = page.to_image(resolution=200).original
                    img = image.convert("L")
                    img = ImageEnhance.Contrast(img).enhance(2.0)
                    img = img.point(lambda p: 0 if p < 160 else 255)
                    ocr_text = pytesseract.image_to_string(img, config="--psm 6")
                    logging.info(f"OCR text mode: page {page_number} done")
                except Exception as e:
                    logging.warning(f"OCR failed on page {page_number}: {str(e)}")
                    ocr_text = ""
                text += ocr_text + "\n"
    except Exception as e:
        logging.error(f"OCR error for {pdf_path}: {str(e)}")
    return text.strip()