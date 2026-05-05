import re
import logging


def clean_text(text):
    return text.replace("₹", "").replace("Rs", "").replace(",", "").strip()


def detect_dates(text):
    """
    Detect dates in multiple formats.
    Returns list in document order (first = invoice date, second = due date).

    FIX: Added "05 Avg 2024" OCR corruption guard — OCR sometimes reads
    "Aug" as "Avg". We normalise common OCR month mis-reads before matching.
    """
    # Normalise common OCR month corruptions
    ocr_fixes = {
        "Avg": "Aug", "Avy": "Aug", "Avq": "Aug",
        "Jao": "Jan", "Jum": "Jun", "Jui": "Jul",
        "Nar": "Mar", "Wlay": "May",
    }
    for wrong, right in ocr_fixes.items():
        text = text.replace(wrong, right)

    patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}",
    ]
    dates = []
    for p in patterns:
        dates.extend(re.findall(p, text, re.IGNORECASE))

    seen, unique = set(), []
    for d in dates:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def detect_amounts(text):
    matches = re.findall(r"[₹Rs$]?\s?\d+(?:,\d{3})*(?:\.\d+)?", text)
    values = []
    for m in matches:
        try:
            values.append(float(clean_text(m)))
        except Exception:
            continue
    return values


def detect_invoice_number(text):
    """
    FIX: Original broad regex matched everything including dates and phone
    numbers. New two-strategy approach with labeled + alphanumeric fallback.

    FIX 2: OCR sometimes produces 'O' (letter) instead of '0' (zero) in
    invoice numbers like 'INV-O00001'. We normalise the O→0 in candidates
    after extraction (but only in the digit section, not the letter prefix).
    """
    # Strategy 1: Explicit label
    labeled = re.search(
        r"(?:Invoice|Bill|Inv|Receipt)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/O]{2,})",
        text, re.IGNORECASE,
    )
    if labeled:
        raw = labeled.group(1).strip()
        # Normalise OCR O→0 in numeric sections only
        fixed = re.sub(r"(?<=[A-Z\-])O(?=\d)", "0", raw)
        fixed = re.sub(r"(?<=\d)O(?=\d)", "0", fixed)
        return fixed

    # Strategy 2: Mixed alphanumeric pattern
    candidates = re.findall(r"\b([A-Z]{1,4}[-/]?[O0-9]{3,})\b", text)
    if candidates:
        raw = candidates[0]
        fixed = re.sub(r"O", "0", raw[1:])  # fix O in numeric part only
        return raw[0] + fixed

    return None


def detect_sections(text):
    """
    State-machine parser for company/customer blocks.
    Reads the name from the line AFTER the label, not by keyword-matching.

    FIX: Added 'Bill To' / 'Ship To' style labels common in US invoices.
    FIX 2: For scanned PDFs without From: label, try to detect company
    from the very first non-header line (heuristic: first substantial line
    that looks like a company name).
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    sections = {"header": [], "company": [], "customer": []}
    i = 0
    while i < len(lines):
        line = lines[i]
        lower = line.lower()

        if re.search(r"\b(invoice|receipt|bill)\b", lower):
            sections["header"].append(line)

        # From: alone on its line
        elif re.match(r"^from\s*:\s*$", lower):
            if i + 1 < len(lines):
                sections["company"].append(lines[i + 1])
                i += 2
                continue
        # From: value inline
        elif re.match(r"^from\s*:\s*\S", lower):
            val = re.sub(r"^from\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            if val:
                sections["company"].append(val)

        # "Bill To:" alone / "To:" alone
        elif re.match(r"^(bill\s+to|ship\s+to|billed\s+to|sold\s+to)\s*:?\s*$", lower):
            if i + 1 < len(lines):
                sections["customer"].append(lines[i + 1])
                i += 2
                continue
        elif re.match(r"^to\s*:\s*$", lower):
            if i + 1 < len(lines):
                sections["customer"].append(lines[i + 1])
                i += 2
                continue
        # Inline "To: value" or "Bill To: value"
        elif re.match(r"^(bill\s+to|to)\s*:\s*\S", lower):
            val = re.sub(r"^(bill\s+to|to)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            if val:
                sections["customer"].append(val)

        i += 1

    # Heuristic for scanned PDFs: if company not found via From: label,
    # check if the first non-invoice-header line looks like a company name
    # (contains capitalised words, not a date/number/address)
    if not sections["company"]:
        for line in lines[:8]:
            lower = line.lower()
            # Skip lines that are clearly headers/dates/addresses
            if re.search(r"\b(invoice|date|no\.|due|bill|to|from|gstin|email|phone)\b", lower):
                continue
            if re.search(r"\d{2}[-/]\d{2}|\d{4}", line):
                continue
            # Looks like a company name: multiple capitalised words
            if re.search(r"[A-Z][a-z]+\s+[A-Z]", line) and len(line) > 5:
                sections["company"].append(line)
                break

    return sections


def detect_entities(sections):
    company = sections["company"][0] if sections["company"] else None
    customer = sections["customer"][0] if sections["customer"] else None
    return company, customer


def calculate_confidence(data):
    score = sum([
        bool(data.get("invoice_number")),
        bool(data.get("invoice_date")),
        bool(data.get("total_amount")),
        bool(data.get("company")),
        bool(data.get("customer")),
    ])
    return score / 5


def extract_total_amount(text):
    """
    Context-aware total extraction.

    Priority order: Grand Total > Total Amount > Amount Due > Balance Due >
                    Net Payable > Net Total > bare Total (excluding Sub Total).

    FIX: 'Sub Total' line was matching before 'Total Amount' because the
    fallback bare-'total' scan ran first. Now tries labeled patterns in
    priority order, and the bare-total scan explicitly excludes lines
    containing 'sub'.

    FIX 2: Indian number format '2,77,170.20' (non-standard comma grouping).
    Handled by stripping ALL commas before float conversion.

    FIX 3: Corrupted currency prefix (OCR produces 'n' for '₹', or '$' for
    US invoices). Currency prefix is now optional and broadly matched.
    """
    priority_patterns = [
        r"Grand\s+Total",
        r"Total\s+Amount",
        r"Amount\s+Due",
        r"Balance\s+Due",
        r"Net\s+Payable",
        r"Net\s+Total",
    ]

    for label in priority_patterns:
        m = re.search(
            label + r"\s*[:\-]?\s*[₹Rs$nNrR]?\s*([\d,]+(?:\.\d{1,2})?)",
            text, re.IGNORECASE,
        )
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue

    # Bare 'Total' fallback — skip lines with 'sub', 'tax', 'rate'
    for line in text.split("\n"):
        if re.search(r"\btotal\b", line, re.IGNORECASE):
            if re.search(r"\b(sub|tax\s+rate|rate)\b", line, re.IGNORECASE):
                continue
            nums = re.findall(r"[\d,]+(?:\.\d{1,2})?", line)
            for n in nums:
                try:
                    val = float(n.replace(",", ""))
                    if val > 0:
                        return val
                except ValueError:
                    pass

    # Last resort
    amounts = detect_amounts(text)
    return max(amounts) if amounts else None


def smart_extract_data(text):
    try:
        data = {}
        sections = detect_sections(text)
        dates = detect_dates(text)
        data["invoice_date"] = dates[0] if dates else None
        data["due_date"] = dates[1] if len(dates) > 1 else None
        data["total_amount"] = extract_total_amount(text)
        data["invoice_number"] = detect_invoice_number(text)
        company, customer = detect_entities(sections)
        data["company"] = company
        data["customer"] = customer
        confidence = calculate_confidence(data)
        return data, confidence
    except Exception as e:
        logging.error(f"Smart parsing error: {str(e)}")
        return {}, 0