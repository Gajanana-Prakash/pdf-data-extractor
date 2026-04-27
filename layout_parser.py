import pdfplumber
import logging


def extract_layout_data(pdf_path):
    """
    Extract data using layout (position-based understanding)
    instead of fixed regex patterns.
    """

    result = {
        "invoice_details": {
            "invoice_number": None,
            "invoice_date": None,
            "total": None
        },
        "items": []
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:

                # ==============================
                # 🔹 STEP 1 — Extract words
                # ==============================
                words = page.extract_words()

                for word in words:
                    text = word["text"].lower()

                    # 📍 Invoice Number Detection
                    if "invoice" in text and not result["invoice_details"]["invoice_number"]:
                        result["invoice_details"]["invoice_number"] = word["text"]

                    # 📍 Date Detection
                    elif "date" in text and not result["invoice_details"]["invoice_date"]:
                        result["invoice_details"]["invoice_date"] = word["text"]

                    # 📍 Total Detection
                    elif "total" in text:
                        result["invoice_details"]["total"] = word["text"]

                # ==============================
                # 🔹 STEP 2 — Extract Tables
                # ==============================
                tables = page.extract_tables()

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    headers = table[0]

                    for row in table[1:]:
                        item = {}

                        for i, cell in enumerate(row):
                            if not cell:
                                continue

                            column_name = headers[i].lower()

                            # 📦 Description
                            if "desc" in column_name or "item" in column_name:
                                item["description"] = cell

                            # 🔢 Quantity
                            elif "qty" in column_name:
                                try:
                                    item["quantity"] = int(cell)
                                except:
                                    item["quantity"] = 0

                            # 💰 Unit Price
                            elif "price" in column_name:
                                try:
                                    item["unit_price"] = float(cell.replace(",", ""))
                                except:
                                    item["unit_price"] = 0.0

                            # 💵 Amount
                            elif "amount" in column_name or "total" in column_name:
                                try:
                                    item["amount"] = float(cell.replace(",", ""))
                                except:
                                    item["amount"] = 0.0

                        if item:
                            result["items"].append(item)

        logging.info(f"Layout extraction successful: {pdf_path}")
        return result

    except Exception as e:
        logging.error(f"Layout extraction failed: {str(e)}")
        return result