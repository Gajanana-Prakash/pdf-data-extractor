import pdfplumber
import re
import logging


def _parse_number(cell_text):
    """Strip currency symbols, commas, spaces; return float or 0.0."""
    if not cell_text:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", str(cell_text).replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _parse_pipe_table(text):
    """
    NEW — Parse pipe-delimited ( | ) text tables.

    WHY: Some PDF generators (especially Indian billing software) produce
    invoices where the item table is rendered as plain text with | column
    separators and ─ / ┼ separator lines, NOT as a real PDF table object.
    pdfplumber.extract_tables() returns [] for these — so they were
    completely skipped, producing items: [] in the output.

    This function detects those text-based tables and parses them.
    """
    lines = text.split("\n")
    pipe_lines = [l for l in lines if l.count("|") >= 3]
    if not pipe_lines:
        return []

    # First pipe line = header row
    headers = [h.strip().lower() for h in pipe_lines[0].split("|")]

    items = []
    for line in pipe_lines[1:]:
        # Skip box-drawing separator lines (─ ┼ ━ etc.)
        if re.search(r"[─┼━┤├┘└┐┌]", line):
            continue

        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2:
            continue

        item = {}
        for i, header in enumerate(headers):
            if i >= len(cells):
                break
            val = cells[i].strip()
            if not val:
                continue

            if any(k in header for k in ("desc", "item", "product", "particular", "service", "name")):
                if val and not val.isdigit():
                    item["description"] = val

            elif any(k in header for k in ("qty", "quantity", "units", "nos")):
                num = re.sub(r"[^\d.]", "", val)
                try:
                    item["quantity"] = int(float(num)) if num else 0
                except ValueError:
                    item["quantity"] = 0

            elif any(k in header for k in ("unit price", "price", "rate", "mrp")):
                item["unit_price"] = _parse_number(val)

            elif any(k in header for k in ("amount", "total")) and "sub" not in header:
                item["amount"] = _parse_number(val)

        if item.get("description"):
            items.append(item)

    # Auto-compute missing amounts
    for item in items:
        if not item.get("amount") and item.get("quantity") and item.get("unit_price"):
            item["amount"] = round(item["quantity"] * item["unit_price"], 2)

    return items


def extract_layout_data(pdf_path):
    """
    Extract data using layout + table analysis.

    BUGS FIXED vs original:
    1. Word-loop stored the KEYWORD itself (e.g. word "Invoice") as invoice_number.
       FIX: Only trigger look-ahead when word is a label token (paired with "No"/"#"),
       not a standalone title word. Also added "once set, skip" guards.

    2. Key name was 'total' — clashes with smart_parser's 'total_amount'.
       FIX: renamed key to 'total_amount' so merge in main.py is clean.

    3. float(cell.replace(",","")) crashed on currency cells like "₹1,200" or "n500".
       FIX: _parse_number() strips all non-digit/dot chars safely.

    4. items[] was [] for pipe-delimited text tables.
       FIX: added _parse_pipe_table() fallback.

    5. Column matching too narrow — only 'desc','qty','price','amount'.
       FIX: expanded with 'particular','service','rate','mrp','units', etc.

    6. Empty-row guard was too loose (any non-empty field passed).
       FIX: guard now requires 'description' to be present.
    """

    result = {
        "invoice_details": {
            "invoice_number": None,
            "invoice_date": None,
            "total_amount": None,     # FIXED: was "total" — caused duplicate key after merge
        },
        "items": [],
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""

            for page in pdf.pages:
                # ==============================
                # STEP 1 — Extract words with look-ahead
                # ==============================
                words = page.extract_words()
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

                # Track which fields are already set to avoid overwriting with bad data
                inv_no_set = result["invoice_details"]["invoice_number"] is not None
                inv_date_set = result["invoice_details"]["invoice_date"] is not None

                for idx, word in enumerate(words):
                    text_lower = word["text"].lower()

                    # ==============================
                    # Invoice Number
                    # FIXED: only trigger on "No", "No.", "Number", "#"
                    # NOT on standalone "INVOICE" title word.
                    # The original regex matched bare "invoice" (the page title)
                    # and then look-ahead grabbed "Invoice" (next word) as the number.
                    # ==============================
                    if not inv_no_set and re.search(r"^(no\.?|number|#)$", text_lower):
                        prev = words[idx - 1]["text"].lower() if idx > 0 else ""
                        if "invoice" in prev or "inv" in prev or "bill" in prev:
                            # Next non-colon token is the value
                            for lookahead in words[idx + 1: idx + 4]:
                                candidate = lookahead["text"].strip(":- ")
                                if candidate and candidate not in (":", "-", ""):
                                    result["invoice_details"]["invoice_number"] = candidate
                                    inv_no_set = True
                                    break

                    # ==============================
                    # Invoice Date
                    # FIXED: was triggering on bare "Date" word from "Account Name",
                    # "Due Date" etc. Now only triggers when previous word is "Invoice".
                    # ==============================
                    elif not inv_date_set and text_lower == "date":
                        prev = words[idx - 1]["text"].lower() if idx > 0 else ""
                        if "invoice" in prev:
                            for lookahead in words[idx + 1: idx + 4]:
                                candidate = lookahead["text"].strip(":- ")
                                if re.search(r"\d{1,4}[-/]\d{1,2}|^\d{1,2}$", candidate):
                                    result["invoice_details"]["invoice_date"] = candidate
                                    inv_date_set = True
                                    break

                    # ==============================
                    # Total Amount
                    # ==============================
                    elif text_lower in ("total", "amount") or re.search(r"grand\s*total|total\s*amount|balance\s*due|amount\s*due", text_lower):
                        for lookahead in words[idx + 1: idx + 4]:
                            candidate = re.sub(r"[^\d.]", "", lookahead["text"].replace(",", ""))
                            if candidate:
                                try:
                                    val = float(candidate)
                                    # Keep largest total seen (Grand Total > Sub Total)
                                    existing = result["invoice_details"]["total_amount"] or 0
                                    if val > existing:
                                        result["invoice_details"]["total_amount"] = val
                                except ValueError:
                                    pass
                                break

                # ==============================
                # STEP 2 — Real PDF Tables
                # ==============================
                tables = page.extract_tables()

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    raw_headers = table[0]
                    if not raw_headers:
                        continue
                    headers = [str(h).lower().strip() if h else "" for h in raw_headers]

                    for row in table[1:]:
                        item = {}

                        for i, cell in enumerate(row):
                            if i >= len(headers) or not cell:
                                continue

                            col = headers[i]
                            cell_str = str(cell).strip()

                            if any(k in col for k in ("desc", "item", "product", "particular", "name", "service")):
                                item["description"] = cell_str

                            elif any(k in col for k in ("qty", "quantity", "units", "nos", "no.")):
                                num = re.sub(r"[^\d.]", "", cell_str)
                                try:
                                    item["quantity"] = int(float(num)) if num else 0
                                except (ValueError, TypeError):
                                    item["quantity"] = 0

                            elif any(k in col for k in ("unit price", "price", "rate", "mrp")):
                                item["unit_price"] = _parse_number(cell_str)

                            elif any(k in col for k in ("amount", "total", "net")) and "sub" not in col:
                                item["amount"] = _parse_number(cell_str)

                            elif any(k in col for k in ("tax", "gst", "vat", "igst", "cgst", "sgst")):
                                item["tax"] = _parse_number(cell_str)

                        if item.get("description"):
                            # Auto-compute amount if missing
                            if not item.get("amount") and item.get("quantity") and item.get("unit_price"):
                                item["amount"] = round(item["quantity"] * item["unit_price"], 2)
                            result["items"].append(item)

            # ==============================
            # STEP 3 — Pipe-table fallback
            # If no real tables were found but the text has pipe-delimited rows,
            # parse those. This handles Indian invoice formats.
            # ==============================
            if not result["items"] and full_text:
                pipe_items = _parse_pipe_table(full_text)
                if pipe_items:
                    result["items"] = pipe_items

        logging.info(f"Layout extraction successful: {pdf_path}")
        return result

    except Exception as e:
        logging.error(f"Layout extraction failed: {str(e)}")
        return result