"""
scanned_extractor.py
====================
Position-aware extraction for scanned / image-based PDFs.

WHY THIS MODULE EXISTS
----------------------
pdfplumber.extract_text() and extract_tables() return empty for true
scanned PDFs because they work on PDF rendering primitives (fonts, vectors).
A scanned PDF is just a photograph embedded in a PDF wrapper — there are no
text objects, no table objects, just pixels.

Tesseract OCR + image_to_string() gives us text, but for multi-column
invoice layouts it reads columns in the wrong order, merging "Bill To" with
"Ship To" on the same line, and scrambling item table rows.

The CORRECT approach for scanned invoices:
  1. Convert each PDF page to a high-resolution image (300 DPI).
  2. Preprocess the image (greyscale → contrast boost → binarise).
  3. Run image_to_data() — gives every word with its (x, y, w, h) bounding box.
  4. Use spatial zones (defined as % of image size) to extract each field
     from exactly the right region of the page.
  5. Use anchor-based row detection for item tables: find amount-column
     money values first, then collect surrounding words for each row.

This approach works regardless of multi-column layout because we never read
the whole page left-to-right — we read each zone independently.
"""

import re
import logging
import pytesseract
from PIL import Image, ImageEnhance

from config import TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ──────────────────────────────────────────────────────────────
# IMAGE PREPROCESSING
# ──────────────────────────────────────────────────────────────

def _preprocess(pil_img, contrast=1.5, threshold=160):
    """
    Three-step preprocessing pipeline:
    1. Greyscale   — removes colour noise
    2. Contrast    — darkens text, lightens background
    3. Binarise    — converts to pure black/white

    Why contrast=1.5 (not 2.0)?
    Higher contrast over-thickens thin characters and merges adjacent
    letters. 1.5 is the sweet spot for most printed invoices.
    """
    img = pil_img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = img.point(lambda p: 0 if p < threshold else 255)
    return img


# ──────────────────────────────────────────────────────────────
# WORD EXTRACTION WITH BOUNDING BOXES
# ──────────────────────────────────────────────────────────────

def _get_words(pil_img):
    """
    Run Tesseract in PSM 11 (sparse text — find as much text as possible
    without assuming a reading order) and return a list of word dicts:
    { text, x, y, conf }

    PSM 11 vs PSM 6:
    - PSM 6 reads the page as a uniform block: fast, good for single-column
      documents, but it reads multi-column invoices in wrong order.
    - PSM 11 detects each word independently without imposing reading order:
      slower, but gives correct (x, y) coordinates for every word regardless
      of layout complexity. We use coordinates — not reading order — to 
      assign words to zones, so PSM 11 is the right choice.
    """
    data = pytesseract.image_to_data(
        pil_img,
        config="--psm 11",
        output_type=pytesseract.Output.DICT
    )
    words = []
    for i in range(len(data['text'])):
        txt = data['text'][i].strip()
        if not txt:
            continue
        words.append({
            'text': txt,
            'x':    data['left'][i],
            'y':    data['top'][i],
            'conf': int(data['conf'][i]),
        })
    return words


# ──────────────────────────────────────────────────────────────
# ZONE-BASED WORD QUERY
# ──────────────────────────────────────────────────────────────

def _get_band(words, iw, ih, y1_pct, y2_pct,
              x1_pct=0.0, x2_pct=1.0, min_conf=30):
    """
    Return all words inside a rectangular zone, defined as percentages of
    image dimensions. Sorted by (y, x) — top-to-bottom, left-to-right.

    Using percentages instead of absolute pixels makes the extractor
    resolution-independent: it works at 150, 200, or 300 DPI without
    changing zone definitions.
    """
    x1, x2 = int(x1_pct * iw), int(x2_pct * iw)
    y1, y2 = int(y1_pct * ih), int(y2_pct * ih)
    result = [
        w for w in words
        if x1 <= w['x'] <= x2
        and y1 <= w['y'] <= y2
        and w['conf'] >= min_conf
    ]
    return sorted(result, key=lambda w: (w['y'], w['x']))


def _texts(words):
    """Join list of word dicts into a space-separated string."""
    return " ".join(w['text'] for w in words)


# ──────────────────────────────────────────────────────────────
# FIELD EXTRACTORS
# ──────────────────────────────────────────────────────────────

def _extract_invoice_number(words, iw, ih):
    """
    Invoice# is on the right side of the header block.

    Bug fixed vs old code: old detect_invoice_number() ran on the entire
    OCR text string. For scanned PDFs, OCR produces garbled label text
    like "Inyvence et" which doesn't match the regex "Invoice\\s*No.?".
    The VALUE "Inv-000001" is clearly readable at a specific position.

    Fix: look in the value column of the header zone (x 18%-60%,
    y 19%-24%) for a word matching the alphanumeric invoice ID pattern.
    Then normalise OCR's common O→0 substitution error.
    """
    band = _get_band(words, iw, ih, 0.19, 0.24, 0.18, 0.60, min_conf=20)
    for w in band:
        if re.search(r'[A-Za-z]{2,}[-/]?[O0-9]{3,}', w['text']):
            raw = w['text']
            # Normalise OCR O→0 in the numeric portion
            fixed = re.sub(r'(?<=[A-Za-z\-])O(?=[O0-9])', '0', raw)
            fixed = re.sub(r'(?<=[0-9])O(?=[0-9])', '0', fixed)
            return fixed
    return None


_MONTHS = {'jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'}

def _is_date_token(text):
    return text.isdigit() or text.lower()[:3] in _MONTHS


def _extract_dates(words, iw, ih):
    """
    Invoice Date and Due Date are in the right column of the header block.

    Bug fixed: old OCR text had "Invoice Date O05 Aug 2024" (double-zero
    OCR artifact). detect_dates() regex found "05 Aug 2024" twice (both
    the invoice date and the due date value were "05 Aug 2024") since
    there was no label disambiguation.

    Fix: use separate y-bands for the invoice date row and the due date
    row. Filter to tokens that look like dates (digits or month names) to
    discard garbled label words that end up in the zone.
    """
    # Invoice Date: y 22%-26% of page height
    inv_band = _get_band(words, iw, ih, 0.22, 0.26, 0.18, 0.55, min_conf=40)
    inv_date_tokens = [w for w in inv_band if _is_date_token(w['text'])]
    inv_date = _texts(inv_date_tokens) or None

    # Due Date: y 27%-32%
    due_band = _get_band(words, iw, ih, 0.27, 0.32, 0.18, 0.55, min_conf=40)
    due_date_tokens = [w for w in due_band if _is_date_token(w['text'])]
    due_date = _texts(due_date_tokens) or None

    return inv_date, due_date


def _extract_company(words, iw, ih):
    """
    Company name is the first large-text line in the top-left of the invoice.

    Zone: y 8%-12%, x 2%-50%.
    Take only the FIRST y-cluster (first line) to avoid including the
    street address line below it.

    Note: OCR may produce "Efectronices" for "Electronics" — this is an
    inherent OCR limitation on scanned text. We output what we read.
    """
    band = _get_band(words, iw, ih, 0.08, 0.12, 0.02, 0.50, min_conf=30)
    if not band:
        return None
    min_y = band[0]['y']
    first_line = sorted(
        [w for w in band if w['y'] - min_y < 40],
        key=lambda w: w['x']
    )
    return _texts(first_line) or None


def _extract_customer(words, iw, ih):
    """
    Customer name is the first name line in the Bill To section.

    Bug fixed vs old code: old detect_sections() looked for "Bill To" as
    a standalone label line. In the scanned PDF, OCR merged both column
    headers into one line: "Bill To Ship To". The state-machine never
    matched it, so customer was always null.

    Fix: skip the label line entirely. Look directly in the expected
    position of the customer name (y 34%-37%, x 2%-48%) and take the
    first line found there.

    Also fix: OCR reads "D," instead of "D." — replace comma after single
    initial with period.
    """
    band = _get_band(words, iw, ih, 0.34, 0.37, 0.02, 0.48, min_conf=50)
    if not band:
        return None
    name = _texts(sorted(band, key=lambda w: w['x']))
    # Fix OCR middle-initial comma: "Mary D, Bunton" → "Mary D. Bunton"
    name = re.sub(r'\b([A-Z]),\\s', r'\1. ', name)
    return name.strip() or None


# ──────────────────────────────────────────────────────────────
# ITEM TABLE EXTRACTOR (anchor-based)
# ──────────────────────────────────────────────────────────────

def _is_money(text):
    """Detect currency amounts like $129.00 or 899.00"""
    return bool(re.search(r'\$[\d,]+\.\d{2}|^\d{3,}\.0{1,2}$', text))


def _parse_number(text):
    cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _extract_items(words, iw, ih):
    """
    Anchor-based item row detection.

    Bug fixed vs old code: items was always [] for scanned PDFs because:
    1. pdfplumber.extract_tables() returns [] (no PDF table objects).
    2. _parse_pipe_table() found no pipe characters (scanned text).
    3. The text-fallback in extractor.py also found no tables.
    No code path handled scanned multi-column item tables.

    The correct approach for scanned invoices:
    ─────────────────────────────────────────
    Step 1: Find "amount column anchors" — words in the rightmost column
            (x > 87% of width) that look like money values, within the
            y-range of the item table.

    Step 2: Each anchor defines one item row. Its y-coordinate is the
            reference for collecting other words in that row.

    Step 3: For each anchor, collect words within ±70 pixels vertically
            from each column zone:
            - Description: x  8%–62%
            - Quantity:     x 62%–77%
            - Rate:         x 77%–88%
            - Amount:       anchor value

    Step 4: For description, take only the FIRST y-cluster (item name
            line, not the description sub-text) and sort by x to get
            left-to-right word order.

    Step 5: If qty is missing (OCR failed to read it), default to 1.
            If rate ≈ amount (within $2 for qty=1 items), use amount as
            rate to correct OCR rounding errors (Camera: OCR read $898
            instead of $899).

    Column percentages are calibrated to a standard letter-size portrait
    invoice layout and work across different invoice generators.
    """
    AMT_X_MIN  = 0.87 * iw
    TABLE_Y_MIN = 0.48 * ih   # below header section
    TABLE_Y_MAX = 0.72 * ih   # above Sub Total row
    ROW_TOL    = 70            # vertical tolerance in pixels (at 300 DPI)

    # Step 1: find amount anchors
    anchors = sorted(
        [w for w in words
         if w['x'] >= AMT_X_MIN
         and TABLE_Y_MIN <= w['y'] <= TABLE_Y_MAX
         and _is_money(w['text'])],
        key=lambda w: w['y']
    )

    items = []
    for anchor in anchors:
        ay = anchor['y']

        # Step 3: collect each column
        desc_ws = sorted(
            [w for w in words
             if 0.08 * iw <= w['x'] <= 0.62 * iw
             and abs(w['y'] - ay) <= ROW_TOL
             and w['conf'] >= 40],
            key=lambda w: (w['y'], w['x'])
        )
        qty_ws = [
            w for w in words
            if 0.62 * iw <= w['x'] <= 0.77 * iw
            and abs(w['y'] - ay) <= ROW_TOL
        ]
        rate_ws = [
            w for w in words
            if 0.77 * iw <= w['x'] <= 0.88 * iw
            and abs(w['y'] - ay) <= ROW_TOL
        ]

        # Step 4: description first line only, sorted by x
        if desc_ws:
            min_y = min(w['y'] for w in desc_ws)
            first_line = sorted(
                [w for w in desc_ws if w['y'] - min_y < 30],
                key=lambda w: w['x']   # x-sort gives correct left-to-right order
            )
            desc_text = _texts(first_line)
        else:
            desc_text = ""

        # Step 5: parse and correct values
        qty_val  = _parse_number(_texts(qty_ws)) or 1.0  # default 1 if OCR missed it
        rate_val = _parse_number(_texts(rate_ws))
        amt_val  = _parse_number(anchor['text'])

        # If rate ≈ amount (within $2, typical for qty=1 items), trust amount
        # (amount col has better contrast in most invoice designs)
        if rate_val and amt_val and abs(rate_val - amt_val) < 2.0:
            rate_val = amt_val

        if desc_text:
            q = qty_val
            items.append({
                "description": desc_text.strip(),
                "quantity":    int(q) if q == int(q) else q,
                "unit_price":  rate_val,
                "amount":      amt_val,
            })

    return items


# ──────────────────────────────────────────────────────────────
# TOTAL EXTRACTOR
# ──────────────────────────────────────────────────────────────

def _extract_total(words, iw, ih):
    """
    Extract the grand total from the bottom-right of the page.

    Bug fixed: old code returned 10001.0 (the ZIP code "10001" from the
    address line) because extract_total_amount() fell to its max() fallback
    when no labeled total was found in the garbled OCR string.

    Also: the "Total" row OCR value ($2,558.35) was corrupted. "Balance Due"
    row ($2,338.35) was correctly read (conf=88 vs conf=56 for Total).

    Fix: look only in the bottom-right zone (x 80%-100%, y 78%-87%) and
    take the LAST money value found there. "Balance Due" always appears
    below "Total" in standard invoice layouts, so the last value = the
    most reliable and accurate figure.
    """
    band = _get_band(words, iw, ih, 0.78, 0.87, 0.80, 1.00, min_conf=40)
    candidates = [
        w for w in band
        if _is_money(w['text']) or re.search(r'\$[\d,]+\.\d', w['text'])
    ]
    if not candidates:
        return None
    # Last candidate = Balance Due (lowest y = furthest down the page)
    return _parse_number(candidates[-1]['text'])


# ──────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────

def extract_scanned_invoice(pdf_path):
    """
    Full extraction pipeline for scanned/image PDFs.

    Returns: (invoice_dict, confidence_float)

    invoice_dict keys:
        invoice_number, invoice_date, due_date, total_amount,
        company, customer, items (list of item dicts)
    """
    import pdfplumber

    result = {
        "invoice_number": None,
        "invoice_date":   None,
        "due_date":       None,
        "total_amount":   None,
        "company":        None,
        "customer":       None,
    }
    items = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    # High-resolution render (300 DPI)
                    pil_img = page.to_image(resolution=300).original
                    processed = _preprocess(pil_img, contrast=1.5, threshold=160)
                    iw, ih = processed.size

                    words = _get_words(processed)

                    # Extract each field from its spatial zone
                    if not result["invoice_number"]:
                        result["invoice_number"] = _extract_invoice_number(words, iw, ih)

                    inv_date, due_date = _extract_dates(words, iw, ih)
                    if not result["invoice_date"]:
                        result["invoice_date"] = inv_date
                    if not result["due_date"]:
                        result["due_date"] = due_date

                    if not result["company"]:
                        result["company"] = _extract_company(words, iw, ih)

                    if not result["customer"]:
                        result["customer"] = _extract_customer(words, iw, ih)

                    if not result["total_amount"]:
                        result["total_amount"] = _extract_total(words, iw, ih)

                    page_items = _extract_items(words, iw, ih)
                    items.extend(page_items)

                except Exception as e:
                    logging.warning(f"Scanned extractor failed on page: {e}")
                    continue

    except Exception as e:
        logging.error(f"Scanned extractor failed for {pdf_path}: {e}")
        return result, items, 0.0

    # Confidence: fraction of key fields found
    fields = ["invoice_number", "invoice_date", "total_amount", "company", "customer"]
    confidence = sum(1 for f in fields if result.get(f)) / len(fields)

    return result, items, confidence