import pytesseract
from PIL import Image
import pdfplumber
import logging

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_with_ocr(pdf_path):
    text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    # Convert to grayscale
                    image = page.to_image().original.convert("L")

                    # OCR
                    ocr_text = pytesseract.image_to_string(image)

                except Exception as e:
                    logging.warning(f"OCR failed on page: {str(e)}")
                    ocr_text = ""

                text += ocr_text + "\n"

        logging.info(f"OCR extraction completed for {pdf_path}")
        return text

    except Exception as e:
        logging.error(f"OCR error: {str(e)}")
        return ""