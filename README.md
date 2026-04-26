# PDF Data Extractor

A Python tool that reads invoice PDF files, extracts structured data (invoice number, dates, company, items, totals) using regex, saves the output as JSON files, and stores the data in a PostgreSQL database.

---

## Project Structure

```
pdf-data-extractor/
├── pdfs/               # Place your input PDF files here
├── output/             # Extracted JSON files are saved here (auto-created)
├── main.py             # Entry point — runs the full pipeline
├── extractor.py        # Extracts raw text from PDF using pdfplumber
├── parser.py           # Parses invoice fields from text using regex
├── db.py               # Saves data to PostgreSQL database
├── logger.py           # Configures logging to app.log
├── .env                # Your database credentials (never commit this)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/your-username/pdf-data-extractor.git
cd pdf-data-extractor
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL

Make sure PostgreSQL is installed and running on your machine. Then create a database:

```sql
CREATE DATABASE pdf_data;
```

> The `invoices` table is created automatically when you run the project — you do not need to create it manually.

### 5. Configure environment variables

Create a `.env` file in the project root (copy the example below):

```
DB_NAME=pdf_data
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432
```

> **Important:** Never commit your `.env` file to GitHub. It is already listed in `.gitignore`.

### 6. Add your PDF files

Place your invoice PDF files inside the `pdfs/` folder:

```
pdfs/
├── invoice1.pdf
├── invoice2.pdf
└── ...
```

---

## Running the Project

```bash
python main.py
```

**What happens when you run it:**

1. The `invoices` table is created in PostgreSQL (if it doesn't exist yet)
2. Every `.pdf` file in the `pdfs/` folder is processed
3. Extracted data is saved as a `.json` file in the `output/` folder
4. The same data is inserted into the PostgreSQL `invoices` table
5. All activity is logged to `app.log`

---

## Output Example

For `pdfs/sample.pdf`, the tool creates `output/sample.json`:

```json
{
    "invoice_details": {
        "invoice_number": "INV-20260408-001",
        "invoice_date": "08 April 2026",
        "due_date": "08 May 2026",
        "company": "Acme Technologies Pvt Ltd",
        "customer": "Global Retail Solutions Ltd",
        "total_amount": 277170.20
    },
    "items": [
        {
            "description": "Wireless Bluetooth Headphones",
            "quantity": 15,
            "unit_price": 2499.0,
            "amount": 37485.0
        }
    ]
}
```

---

## Database Schema

The `invoices` table is created automatically with this structure:

```sql
CREATE TABLE IF NOT EXISTS invoices (
    id         SERIAL PRIMARY KEY,
    data       JSONB     NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `psycopg2.OperationalError` | Check your `.env` credentials and that PostgreSQL is running |
| `No PDF files found` | Place PDF files inside the `pdfs/` folder |
| Items not extracted | Your PDF may use a different table format — check `parser.py` regex patterns |

---

## Tech Stack

- **Python 3.8+**
- **pdfplumber** — PDF text extraction
- **psycopg2** — PostgreSQL database connector
- **python-dotenv** — Loads `.env` environment variables