import re
import logging


# ==============================
# 🔹 CLEAN TEXT FUNCTION
# ==============================
def clean_text(text):
    return text.replace("₹", "").replace("Rs", "").replace(",", "").strip()


# ==============================
# 🔹 DETECT DATES (MULTI FORMAT)
# ==============================
def detect_dates(text):
    patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]

    dates = []
    for p in patterns:
        dates.extend(re.findall(p, text))

    return dates


# ==============================
# 🔹 DETECT AMOUNTS (ROBUST)
# ==============================
def detect_amounts(text):
    matches = re.findall(r"[₹Rs$]?\s?\d+(?:,\d{3})*(?:\.\d+)?", text)

    values = []
    for m in matches:
        try:
            values.append(float(clean_text(m)))
        except:
            continue

    return values


# ==============================
# 🔹 DETECT INVOICE NUMBER
# ==============================
def detect_invoice_number(text):
    matches = re.findall(r"\b[A-Z0-9\-]{5,}\b", text)
    return matches[0] if matches else None


# ==============================
# 🔹 SECTION DETECTION (🔥 NEW)
# ==============================
def detect_sections(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    sections = {
        "header": [],
        "company": [],
        "customer": [],
    }

    # heuristic rules
    for i, line in enumerate(lines[:15]):  # only top section
        if "invoice" in line.lower():
            sections["header"].append(line)
        elif "to" in line.lower():
            sections["customer"].append(line)
        elif "from" in line.lower() or "ltd" in line.lower():
            sections["company"].append(line)

    return sections


# ==============================
# 🔹 ENTITY DETECTION (IMPROVED)
# ==============================
def detect_entities(sections):
    company = " ".join(sections["company"]) if sections["company"] else None
    customer = " ".join(sections["customer"]) if sections["customer"] else None
    return company, customer


# ==============================
# 🔹 CONFIDENCE SCORING (🔥 NEW)
# ==============================
def calculate_confidence(data):
    score = 0
    total = 5

    if data.get("invoice_number"):
        score += 1
    if data.get("invoice_date"):
        score += 1
    if data.get("total_amount"):
        score += 1
    if data.get("company"):
        score += 1
    if data.get("customer"):
        score += 1

    return score / total


# ==============================
# 🔥 MAIN FUNCTION
# ==============================
def smart_extract_data(text):
    try:
        data = {}

        # 🔹 Sections
        sections = detect_sections(text)

        # 🔹 Dates
        dates = detect_dates(text)
        data["invoice_date"] = dates[0] if dates else None
        data["due_date"] = dates[1] if len(dates) > 1 else None

        # 🔹 Amounts
        amounts = detect_amounts(text)
        data["total_amount"] = max(amounts) if amounts else None

        # 🔹 Invoice Number
        data["invoice_number"] = detect_invoice_number(text)

        # 🔹 Entities
        company, customer = detect_entities(sections)
        data["company"] = company
        data["customer"] = customer

        # 🔥 Confidence
        confidence = calculate_confidence(data)

        return data, confidence

    except Exception as e:
        logging.error(f"Smart parsing error: {str(e)}")
        return {}, 0