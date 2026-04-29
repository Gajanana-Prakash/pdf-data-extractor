import pytesseract
from PIL import Image
import pdfplumber
import logging

# 🔥 Import from config (NO HARDCODING)
from config import TESSERACT_PATH

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_text_with_ocr(pdf_path):
    """
    Extract text from scanned/image PDFs using OCR (Tesseract)

    Flow:
    PDF → Image → Preprocess → OCR → Text
    """

    text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    # ============================================
                    # STEP 1 — Convert PDF page to image
                    # ============================================
                    image = page.to_image().original

                    # ============================================
                    # STEP 2 — Preprocessing (VERY IMPORTANT)
                    # Improve OCR accuracy
                    # ============================================
                    image = image.convert("L")  # Grayscale

                    # Optional: increase contrast / threshold
                    # image = image.point(lambda x: 0 if x < 140 else 255)

                    # ============================================
                    # STEP 3 — OCR Extraction
                    # ============================================
                    ocr_text = pytesseract.image_to_string(image)

                    logging.info(f"OCR success on page {page_number}")

                except Exception as e:
                    logging.warning(f"OCR failed on page {page_number}: {str(e)}")
                    ocr_text = ""

                text += ocr_text + "\n"

        logging.info(f"OCR extraction completed for {pdf_path}")
        return text.strip()

    except Exception as e:
        logging.error(f"OCR error in file {pdf_path}: {str(e)}")
        return ""