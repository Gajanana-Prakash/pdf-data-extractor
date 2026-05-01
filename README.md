# 🚀 PDF Data Extractor (AI-Powered Document Processing System)

A **production-ready, scalable PDF processing system** that extracts structured data from invoices/quotations using a **hybrid intelligent pipeline** combining:

- Text extraction
- OCR fallback (for scanned PDFs)
- Layout-aware parsing
- Smart extraction with confidence scoring
- Regex fallback (when needed)

The system provides:
✔ Batch processing pipeline  
✔ PostgreSQL storage  
✔ FastAPI-based backend API  
✔ Optional frontend UI  

---

## 🧠 Key Features

### 📄 Document Processing
- Supports multiple PDF formats
- Works with:
  - Text-based PDFs
  - Scanned/image-based PDFs (OCR)

### 🤖 Intelligent Extraction
- Smart parser with confidence scoring
- Automatic fallback to regex
- Multi-pattern extraction logic

### 🧩 Layout-Aware Parsing
- Extracts:
  - Invoice details
  - Line items
  - Totals

### 🔁 Fault Tolerance
- One file failure does NOT stop system

### ⚡ Performance
- Parallel processing using multiprocessing

### 🔐 Duplicate Detection
- SHA256 file hashing

### 🆔 Unique Tracking
- Each document has:
  - `document_id`
  - `file_hash`

### 🌐 API + UI
- FastAPI backend
- Upload & process PDFs
- Optional frontend interface

---

## 📁 Project Structure

```
pdf-data-extractor/
├── pdfs/                 # Input PDFs
├── output/               # JSON outputs
├── main.py               # Core pipeline
├── api.py                # FastAPI backend
├── extractor.py          # Text extraction
├── ocr.py                # OCR fallback
├── parser.py             # Regex parsing
├── smart_parser.py       # Smart extraction
├── layout_parser.py      # Layout parsing
├── db.py                 # Database logic
├── utils.py              # File hash generation
├── config.py             # Config settings
├── logger.py             # Logging
├── index.html            # Frontend UI (optional)
├── .env                  # Environment variables
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Clone Repository
```bash
git clone https://github.com/your-username/pdf-data-extractor.git
cd pdf-data-extractor
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🐘 PostgreSQL Setup

```sql
CREATE DATABASE pdf_data;
```

Table is created automatically.

---

## 🔐 Environment Variables

Create `.env` file:

```
DB_NAME=pdf_data
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

---

## ▶️ Run Batch Processing

```bash
python main.py
```

### What happens:
1. Reads PDFs from `pdfs/`
2. Generates file hash (duplicate detection)
3. Extracts text / OCR fallback
4. Smart + layout + regex extraction
5. Saves JSON → `output/`
6. Stores data in PostgreSQL
7. Logs activity → `app.log`

---

## 🌐 Run API (FastAPI)

```bash
uvicorn api:app --reload
```

Open:
👉 http://127.0.0.1:8000/docs

Upload PDF → Get JSON response

---

## 🖥️ Run Frontend UI (Optional)

```bash
python -m http.server 5500
```

Open:
👉 http://127.0.0.1:5500/index.html

---

## 📄 Output Example

```json
{
  "document_id": "uuid",
  "file_hash": "sha256_hash",
  "invoice_details": {
    "invoice_number": "INV-001",
    "date": "2026-04-01",
    "company": "ABC Pvt Ltd",
    "total_amount": 10000
  },
  "items": [
    {
      "description": "Product A",
      "quantity": 2,
      "price": 5000
    }
  ]
}
```

---

## 🧠 Architecture

```
PDF Input
   ↓
Text Extraction / OCR
   ↓
Layout Parsing
   ↓
Smart Extraction (Confidence Engine)
   ↓
Regex Fallback
   ↓
JSON Output
   ↓
PostgreSQL
   ↓
API Response
```

---

## 🏢 Industry-Level Capabilities

- Document AI systems
- Invoice automation tools
- OCR platforms
- ETL pipelines

---

## 🛠️ Tech Stack

- Python 3.8+
- pdfplumber
- pytesseract
- FastAPI
- PostgreSQL (psycopg2)
- multiprocessing
- python-dotenv

---

## 🧪 Troubleshooting

| Problem | Solution |
|--------|---------|
| No PDFs found | Add files to `pdfs/` |
| OCR not working | Install Tesseract |
| DB error | Check `.env` |
| Duplicate skipped | File already processed |
| API fetch error | Enable CORS |

---

## 🎯 Final Outcome

You built:

✅ Scalable ETL pipeline  
✅ AI-like document processor  
✅ API-based system  
✅ Full-stack mini product  

---

## 💬 Interview Line

> “I built a scalable document processing system with OCR, layout parsing, intelligent extraction, and a FastAPI interface.”

---

## 🚀 Future Improvements

- Cloud deployment (AWS/GCP)
- ML/NLP models
- React frontend
- Authentication system
- Dashboard analytics