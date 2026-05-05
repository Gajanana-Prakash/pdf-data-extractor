import os
import platform

# ==============================
# 🔧 OCR Configuration
#
# FIX: Original had hard-coded Windows path r"C:\Program Files\..."
# which crashes on Linux/Mac/Docker (any production server).
#
# New logic:
# 1. Check environment variable TESSERACT_PATH first (set in .env)
# 2. If not set, use platform-appropriate default
#
# Windows users: create a .env file and add:
#   TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
# Linux/Mac:     installed via  apt install tesseract-ocr  or  brew install tesseract
# ==============================

_env_path = os.getenv("TESSERACT_PATH")

if _env_path:
    TESSERACT_PATH = _env_path
elif platform.system() == "Windows":
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    TESSERACT_PATH = "/usr/bin/tesseract"

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
# 📝 Logging
# ==============================
LOG_FILE = os.getenv("LOG_FILE", "app.log")