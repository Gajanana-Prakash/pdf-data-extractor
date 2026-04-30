from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import logging

# 🔥 Import your pipeline
from main import process_pdf
from config import PDF_FOLDER
from logger import setup_logger   # ✅ NEW

# ============================================
# 🚀 INIT APP
# ============================================
app = FastAPI()

# ============================================
# 🔥 SETUP LOGGER (VERY IMPORTANT)
# ============================================
setup_logger()
logging.info("API Server Started")

# ============================================
# 🔥 CORS (ALLOW FRONTEND TO CALL API)
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 👈 allow all (dev mode)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# 🏠 HOME ROUTE
# ============================================
@app.get("/")
def home():
    return {"message": "PDF Processing API is running"}

# ============================================
# 📤 UPLOAD ROUTE
# ============================================
@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        # Ensure folder exists
        os.makedirs(PDF_FOLDER, exist_ok=True)

        # Save file
        file_path = os.path.join(PDF_FOLDER, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logging.info(f"File uploaded: {file.filename}")
        print(f"📂 File saved: {file_path}")

        # 🔥 Process PDF
        result = process_pdf(file_path)

        # ============================================
        # ⚠️ HANDLE DUPLICATE
        # ============================================
        if result and isinstance(result, dict) and result.get("status") == "duplicate":
            logging.warning(f"Duplicate skipped: {file.filename}")

            return {
                "status": "duplicate",
                "message": "File already processed",
                "filename": file.filename
            }

        # ============================================
        # ❌ HANDLE FAILURE
        # ============================================
        if result is None:
            logging.error(f"Processing failed: {file.filename}")

            return {
                "status": "error",
                "message": "Failed to process PDF",
                "filename": file.filename
            }

        # ============================================
        # ✅ SUCCESS RESPONSE
        # ============================================
        logging.info(f"Processing completed: {file.filename}")

        return {
            "status": "success",
            "filename": file.filename,
            "data": result
        }

    except Exception as e:
        logging.error(f"Upload error: {str(e)}")

        return {
            "status": "error",
            "message": str(e)
        }