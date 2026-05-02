import re
import logging


def clean_text(text):
    return text.replace("₹", "").replace("Rs", "").replace(",", "").strip()


def detect_dates(text):
    """
    FIX: Added common invoice date formats — "15 Jan 2024", "January 15, 2024".
    Original only had numeric formats.
    """
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
    # Deduplicate preserving order
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
        except:
            continue
    return values


def detect_invoice_number(text):
    """
    FIX: Original r"\b[A-Z0-9\-]{5,}\b" was too broad —
    it matched dates (2024-01-15), phone numbers, PAN cards etc.
    New approach: first look for labeled invoice number, then
    fallback to alphanumeric codes that mix letters + digits.
    """
    # Strategy 1: Explicit label
    labeled = re.search(
        r"(?:Invoice|Bill|Inv|Receipt)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,})",
        text, re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1).strip()

    # Strategy 2: Mixed alphanumeric (letters + numbers, avoids pure date strings)
    candidates = re.findall(r"\b([A-Z]{1,4}[-/]?[0-9]{3,})\b", text)
    if candidates:
        return candidates[0]

    return None


def detect_sections(text):
    """
    FIX 1: Original scanned only first 15 lines — many invoices have
    headers deeper. Expanded to 30 lines.
    FIX 2: Bare "to" matched too many false positives. Added specific
    labels like "Bill To", "Billed To", "Ship To".
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    sections = {"header": [], "company": [], "customer": []}

    for i, line in enumerate(lines[:30]):
        lower = line.lower()
        if "invoice" in lower or "bill" in lower or "receipt" in lower:
            sections["header"].append(line)
        elif re.search(r"\b(bill\s+to|billed\s+to|ship\s+to|sold\s+to|customer)\b", lower):
            sections["customer"].append(line)
        elif re.search(r"\bto\b", lower) and i > 2:
            sections["customer"].append(line)
        elif re.search(r"\b(from|seller|vendor|supplier|ltd|pvt|inc|llp|corp)\b", lower):
            sections["company"].append(line)

    return sections


def detect_entities(sections):
    """
    FIX: Original returned raw joined text including label words
    like "Bill To" or "From:" in the entity name itself.
    Now strips those label words from the start of the string.
    """
    def clean_label(lines):
        text = " ".join(lines) if lines else None
        if not text:
            return None
        text = re.sub(
            r"^(Bill\s+To|Billed\s+To|Ship\s+To|From|To)\s*[:\-]?\s*",
            "", text, flags=re.IGNORECASE,
        ).strip()
        return text if text else None

    return clean_label(sections["company"]), clean_label(sections["customer"])


def calculate_confidence(data):
    score = sum([
        bool(data.get("invoice_number")),
        bool(data.get("invoice_date")),
        bool(data.get("total_amount")),
        bool(data.get("company")),
        bool(data.get("customer")),
    ])
    return score / 5


def smart_extract_data(text):
    """
    FIX: total_amount previously used max() over ALL numbers in
    the document — this picked up phone numbers, zip codes, and
    quantities instead of the actual invoice total.
    Now uses a context-aware regex that looks for the number
    adjacent to Total / Grand Total / Amount Due labels first,
    and only falls back to max() if nothing is found.
    """
    try:
        data = {}
        sections = detect_sections(text)
        dates = detect_dates(text)
        data["invoice_date"] = dates[0] if dates else None
        data["due_date"] = dates[1] if len(dates) > 1 else None

        # Context-aware total extraction
        total_match = re.search(
            r"(?:Grand\s+Total|Total\s+Amount|Amount\s+Due|Balance\s+Due|Net\s+Total|Total)"
            r"\s*[:\-]?\s*[₹Rs$]?\s*([\d,]+(?:\.\d{1,2})?)",
            text, re.IGNORECASE,
        )
        if total_match:
            try:
                data["total_amount"] = float(total_match.group(1).replace(",", ""))
            except ValueError:
                data["total_amount"] = None
        else:
            amounts = detect_amounts(text)
            data["total_amount"] = max(amounts) if amounts else None

        data["invoice_number"] = detect_invoice_number(text)
        company, customer = detect_entities(sections)
        data["company"] = company
        data["customer"] = customer

        confidence = calculate_confidence(data)
        return data, confidence

    except Exception as e:
        logging.error(f"Smart parsing error: {str(e)}")
        return {}, 0