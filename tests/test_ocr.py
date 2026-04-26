import pytesseract
from PIL import Image
import os

# 🔴 REQUIRED for Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

try:
    print("Starting OCR test...")

    base_dir = os.path.dirname(__file__)
    img_path = os.path.join(base_dir, "test.png")

    if not os.path.exists(img_path):
        raise FileNotFoundError("❌ test.png not found")

    print("Loading image...")
    img = Image.open(img_path).convert("L")  # 🔥 improved

    print("Running OCR...")
    text = pytesseract.image_to_string(img)

    print("\n----- OCR OUTPUT -----\n")
    print(text.strip())

    if not text.strip():
        print("⚠️ Warning: OCR returned empty text. Try a clearer image.")

except Exception as e:
    print(f"⚠️ Error occurred: {e}")