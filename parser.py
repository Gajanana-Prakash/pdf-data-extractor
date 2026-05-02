import re


def clean_number(value):
    """
    Converts messy values like '₹1,200.50', 'n500.00', 'Rs 300', None → float.
    """
    if value is None:
        return 0.0
    value = str(value)
    value = re.sub(r"[^\d.]", "", value)
    if value == "" or value == ".":
        return 0.0
    # Guard against multiple dots (e.g. "1.2.3")
    parts = value.split(".")
    if len(parts) > 2:
        value = parts[0] + "." + "".join(parts[1:])
    return float(value)


def extract_data(text):
    """
    Regex fallback parser.

    FIX 1: invoice_date regex used .* which greedily consumed
    everything to end of line including trailing spaces/junk.
    Changed to capture only up to end of meaningful content.

    FIX 2: company/customer regex used re.DOTALL crossing
    multiple lines — easily grabbed half the document.
    Replaced with line-by-line approach looking for the line
    immediately after the "From:" / "To:" label.

    FIX 3: total regex stopped at first match which could be
    a subtotal. Now searches for Grand Total / Amount Due first.
    """
    data = {}

    # Invoice number
    inv_no = re.search(r"Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*(\S+)", text, re.IGNORECASE)
    data["invoice_number"] = inv_no.group(1).strip() if inv_no else None

    # Dates — capture up to 20 chars to avoid overrun
    inv_date = re.search(r"Invoice\s+Date\s*[:\-]?\s*(.{5,20})", text, re.IGNORECASE)
    due_date = re.search(r"Due\s+Date\s*[:\-]?\s*(.{5,20})", text, re.IGNORECASE)
    data["invoice_date"] = inv_date.group(1).strip() if inv_date else None
    data["due_date"] = due_date.group(1).strip() if due_date else None

    # Company: line immediately after "From:" label
    lines = text.split("\n")
    data["company"] = None
    data["customer"] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^From\s*[:\-]?\s*$", stripped, re.IGNORECASE) and i + 1 < len(lines):
            data["company"] = lines[i + 1].strip()
        elif re.match(r"^From\s*[:\-]\s*\S", stripped, re.IGNORECASE):
            data["company"] = re.sub(r"^From\s*[:\-]\s*", "", stripped, flags=re.IGNORECASE).strip()
        if re.match(r"^(?:Bill\s+)?To\s*[:\-]?\s*$", stripped, re.IGNORECASE) and i + 1 < len(lines):
            data["customer"] = lines[i + 1].strip()
        elif re.match(r"^(?:Bill\s+)?To\s*[:\-]\s*\S", stripped, re.IGNORECASE):
            data["customer"] = re.sub(r"^(?:Bill\s+)?To\s*[:\-]\s*", "", stripped, flags=re.IGNORECASE).strip()

    # Total — prefer Grand Total / Amount Due over bare Total
    grand = re.search(
        r"(?:Grand\s+Total|Total\s+Amount|Amount\s+Due|Balance\s+Due)\s*[:\-]?\s*[₹Rs$]?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE,
    )
    if grand:
        data["total_amount"] = clean_number(grand.group(1))
    else:
        total = re.search(r"Total\s*[:\-]?\s*[^\d]*([\d,\.]+)", text, re.IGNORECASE)
        data["total_amount"] = clean_number(total.group(1)) if total else None

    return data


def extract_items_from_tables(tables):
    """
    Dynamic table parser.

    FIX 1: quantity conversion used int(value) which crashes on
    "2.0" (float string). Now uses int(float(...)).

    FIX 2: Empty-row guard `any(v != "" ...)` passed even for rows
    where only amount was filled — those are subtotal/total rows,
    not items. Guard now requires "description" to be present.

    FIX 3: Added tax/GST column support.
    """
    items = []

    try:
        for df in tables:
            # Normalize column names, handle None
            df.columns = [str(col).lower().strip() if col is not None else "" for col in df.columns]

            for _, row in df.iterrows():
                item = {}

                for col in df.columns:
                    value = row[col]
                    if value is None or str(value).strip() == "":
                        continue

                    col_name = col.lower()

                    if any(k in col_name for k in ("desc", "item", "product", "particular", "name", "service")):
                        item["description"] = str(value).strip()

                    elif any(k in col_name for k in ("qty", "quantity", "units", "nos")):
                        try:
                            item["quantity"] = int(float(re.sub(r"[^\d.]", "", str(value)) or 0))
                        except (ValueError, TypeError):
                            item["quantity"] = 0

                    elif any(k in col_name for k in ("price", "rate", "unit price", "mrp")):
                        item["unit_price"] = clean_number(value)

                    elif any(k in col_name for k in ("amount", "total", "line total")):
                        item["amount"] = clean_number(value)

                    elif any(k in col_name for k in ("tax", "gst", "vat", "igst", "cgst", "sgst")):
                        item["tax"] = clean_number(value)

                # Only add rows that have a description — skip subtotal/total rows
                if item.get("description"):
                    items.append(item)

        return items

    except Exception as e:
        print("Error extracting table items:", e)
        return []