import re


# 🔥 NEW — CLEANING FUNCTION (VERY IMPORTANT)
def clean_number(value):
    """
    Converts messy values like:
    '₹1,200.50', 'n500.00', 'Rs 300', None → 1200.50, 500.00, 300.0

    This makes your system robust for real-world PDFs.
    """
    if value is None:
        return 0.0

    # Convert to string
    value = str(value)

    # Remove everything except digits and dot
    value = re.sub(r"[^\d.]", "", value)

    # If empty after cleaning
    if value == "":
        return 0.0

    return float(value)


def extract_data(text):
    """
    Basic header extraction (still regex-based for now)
    Will be improved in Day 4 (layout-based)
    """
    data = {}

    invoice_no = re.search(r"Invoice No\.?\s*:?\s*(\S+)", text)
    invoice_date = re.search(r"Invoice Date\s*:?\s*(.*)", text)
    due_date = re.search(r"Due Date\s*:?\s*(.*)", text)

    company = re.search(r"From:\s*(.*?)\s*To:", text, re.DOTALL)
    customer = re.search(r"To:\s*(.*?)(?:Item|Description)", text, re.DOTALL)

    total = re.search(r"Total\s*:?\s*[^\d]?([\d,\.]+)", text)

    data["invoice_number"] = invoice_no.group(1) if invoice_no else None
    data["invoice_date"] = invoice_date.group(1).strip() if invoice_date else None
    data["due_date"] = due_date.group(1).strip() if due_date else None

    data["company"] = company.group(1).split("\n")[0].strip() if company else None
    data["customer"] = customer.group(1).split("\n")[0].strip() if customer else None

    # 🔥 FIXED — safe number conversion
    data["total_amount"] = clean_number(total.group(1)) if total else None

    return data


def extract_items_from_tables(tables):
    """
    Day 3 — Dynamic table parsing (NO HARD-CODED REGEX)

    Works for:
    ✔ Different column names
    ✔ Corrupted currency symbols
    ✔ Multiple table formats
    """
    items = []

    try:
        for df in tables:
            # Normalize column names
            df.columns = [str(col).lower() for col in df.columns]

            for _, row in df.iterrows():
                item = {}

                for col in df.columns:
                    value = row[col]

                    if value is None:
                        continue

                    col_name = col.lower()

                    # 🔍 Dynamic column detection
                    if "desc" in col_name or "item" in col_name or "product" in col_name:
                        item["description"] = str(value).strip()

                    elif "qty" in col_name or "quantity" in col_name:
                        item["quantity"] = int(value) if str(value).isdigit() else 0

                    elif "price" in col_name or "rate" in col_name:
                        item["unit_price"] = clean_number(value)

                    elif "amount" in col_name or "total" in col_name:
                        item["amount"] = clean_number(value)

                # Avoid adding empty rows
                if item and any(v != "" for v in item.values()):
                    items.append(item)

        return items

    except Exception as e:
        print("Error extracting table items:", e)
        return []