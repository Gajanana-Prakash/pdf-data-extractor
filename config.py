import os

# ==============================
# 🔧 OCR Configuration
# FIX: Tesseract path was hard-coded to Windows path.
# Now reads from environment variable with a sensible
# default for Linux (production). Windows users set
# TESSERACT_PATH in their .env file.
# ==============================
TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    "/usr/bin/tesseract"  # Linux/Mac default; override via .env on Windows
)

# ==============================
# 🧠 AI Confidence Threshold
# ==============================
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

# ==============================
# 📂 Folder Configuration
# ==============================
PDF_FOLDER = os.getenv("PDF_FOLDER", "pdfs")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "output")

# ==============================
# 📝 Logging Configuration
# ==============================
LOG_FILE = os.getenv("LOG_FILE", "app.log")