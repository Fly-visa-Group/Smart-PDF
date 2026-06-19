"""
PDF → HTML Extractor (layout-preserving).

Converts each PDF page to clean HTML that preserves:
- Font sizes (PDF points → CSS pt)
- Bold / italic
- Text alignment (left / center / right)
- Vertical spacing between blocks (margin-top heuristic)
- Tables (converted to <table> elements)

Uses pymupdf_layout when available for improved block grouping.
Falls back to PyMuPDF dict extraction otherwise.
For image-only (scanned) PDFs, uses RapidOCR.

The resulting HTML is sent verbatim to Gemini for translation.
"""
import html as html_lib
import fitz  # PyMuPDF

# pymupdf-layout is installed — suppress the advisory log message.
# We use PyMuPDF's native dict extraction which is already accurate for legal docs.
try:
    from pymupdf.layout import DocumentLayoutAnalyzer  # noqa: F401 — suppress warning
    _HAS_LAYOUT = True
except ImportError:
    _HAS_LAYOUT = False

import logging as _logging
_logging.getLogger("pymupdf").setLevel(_logging.ERROR)


# ── helpers ───────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    return html_lib.escape(text, quote=False)


def _is_inside_table(bbox: list, table_bboxes: list) -> bool:
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for tx0, ty0, tx1, ty1 in table_bboxes:
        if tx0 - 5 <= cx <= tx1 + 5 and ty0 - 5 <= cy <= ty1 + 5:
            return True
    return False


def _alignment(x0: float, block_w: float, page_w: float, is_large: bool) -> str:
    margin_l = x0
    margin_r = page_w - (x0 + block_w)
    mid_block = x0 + block_w / 2
    mid_page = page_w / 2

    if x0 > mid_page * 1.1 and block_w < page_w * 0.5:
        return "right"
    if abs(margin_l - margin_r) < page_w * 0.07 and block_w < page_w * 0.75:
        return "center"
    if is_large and abs(mid_block - mid_page) < page_w * 0.08:
        return "center"
    return "left"


def _gap_to_margin(gap_pt: float) -> int:
    """Convert vertical gap (PDF points) to CSS margin-top in pixels."""
    if gap_pt < 2:
        return 0
    if gap_pt < 6:
        return 4
    if gap_pt < 12:
        return 8
    if gap_pt < 20:
        return 14
    if gap_pt < 35:
        return 20
    return 30


def _table_to_html(grid: list, font_size: float = 11.0) -> str:
    """Convert a 2-D grid of strings to an HTML <table>."""
    rows_html = []
    for row in grid:
        cells_html = []
        for cell in row:
            text = _escape((cell or "").strip())
            cells_html.append(
                f'<td style="border:1px solid #999;padding:5px 8px;'
                f'font-size:{font_size:.0f}pt;vertical-align:top;'
                f'white-space:pre-wrap;">{text}</td>'
            )
        rows_html.append("<tr>" + "".join(cells_html) + "</tr>")
    return (
        '<table style="width:100%;border-collapse:collapse;'
        'border:1px solid #999;margin:6px 0;">'
        "<tbody>" + "".join(rows_html) + "</tbody></table>"
    )


# ── main entry point ──────────────────────────────────────────────────────────

def _ocr_page_to_elements(page: fitz.Page, page_w: float) -> list[tuple]:
    """
    Run RapidOCR on a scanned page and return (y0, html_str, y1) elements.
    Each OCR result is a text box; we map bounding box position to alignment.
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return []

    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")

    ocr = RapidOCR()
    result, _ = ocr(img_bytes)
    if not result:
        return []

    # Group OCR boxes into logical lines by proximity of y-centers
    # Sort by y0 then group into rows within 8px of each other
    boxes = []
    for box, text, conf in result:
        if not text.strip():
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x0 = min(xs) / zoom
        y0 = min(ys) / zoom
        x1 = max(xs) / zoom
        y1 = max(ys) / zoom
        h = y1 - y0
        font_size = round(h * 0.70, 1)  # heuristic: 70% of box height
        bold = font_size > 13.5
        boxes.append((y0, x0, x1, y1, font_size, bold, text.strip()))

    boxes.sort(key=lambda b: (b[0], b[1]))

    # Group into rows (same horizontal line)
    rows: list[list] = []
    current_row: list = []
    prev_y_mid = None
    for box in boxes:
        y0, x0, x1, y1, fs, bold, text = box
        y_mid = (y0 + y1) / 2
        if prev_y_mid is None or abs(y_mid - prev_y_mid) < (y1 - y0) * 0.6:
            current_row.append(box)
            prev_y_mid = y_mid
        else:
            if current_row:
                rows.append(current_row)
            current_row = [box]
            prev_y_mid = y_mid
    if current_row:
        rows.append(current_row)

    elements: list[tuple] = []
    for row in rows:
        row.sort(key=lambda b: b[1])  # sort by x0
        row_y0 = min(b[0] for b in row)
        row_y1 = max(b[3] for b in row)
        row_x0 = min(b[1] for b in row)
        row_x1 = max(b[2] for b in row)
        row_w = row_x1 - row_x0
        avg_fs = sum(b[4] for b in row) / len(row)
        is_large = avg_fs > 13.0

        align = _alignment(row_x0, row_w, page_w, is_large)

        parts = []
        for _, _, _, _, fs, bold, text in row:
            style = f"font-size:{fs:.1f}pt;"
            if bold:
                style += "font-weight:bold;"
            parts.append(f'<span style="{style}">{_escape(text)}</span>')

        p_style = f"text-align:{align};margin:0;line-height:1.55;"
        elements.append((row_y0, f'<p style="{p_style}">{"&nbsp;&nbsp;".join(parts)}</p>', row_y1))

    return elements


def pdf_page_to_html(page: fitz.Page) -> str:
    """
    Convert one fitz.Page to a self-contained HTML fragment.
    - For selectable-text PDFs: uses PyMuPDF dict extraction (preserves exact font sizes/bold).
    - For image-only (scanned) PDFs: falls back to RapidOCR with heuristic font sizing.
    The fragment is sent to Gemini for translation.
    """
    page_w = page.rect.width

    # ── 1. Detect tables ─────────────────────────────────────────────────────
    tables = page.find_tables()
    table_bboxes = [list(t.bbox) for t in tables]

    table_elements: list[tuple] = []  # (y0, html_str, y1)
    for t in tables:
        grid = t.extract()
        t_html = _table_to_html(grid)
        table_elements.append((t.bbox[1], t_html, t.bbox[3]))

    # ── 2. Check if page has extractable text via dict mode ───────────────────
    # NOTE: get_text("text") fails for custom-encoded Vietnamese fonts.
    # get_text("dict") is more reliable — it processes each span individually.
    raw_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
    has_native_text = any("lines" in b and any(
        sp["text"].strip() for ln in b["lines"] for sp in ln["spans"]
    ) for b in raw_dict["blocks"])

    block_elements: list[tuple] = []
    is_scanned = False    # True = no native text (pure image, OCR needed)
    scale = 1.0           # font-size normalisation factor

    if not has_native_text:
        # ── Pure image page: run RapidOCR ────────────────────────────────────
        block_elements = _ocr_page_to_elements(page, page_w)
        is_scanned = True
    else:
        raw = raw_dict  # reuse already-fetched dict

        all_sizes: list[float] = []
        for blk in raw["blocks"]:
            if "lines" not in blk:
                continue
            for ln in blk["lines"]:
                for sp in ln["spans"]:
                    if sp["text"].strip():
                        all_sizes.append(sp["size"])
        avg_size = (sum(all_sizes) / len(all_sizes)) if all_sizes else 11.0

        # Detect scan-embedded text layer: font sizes inflated > 20 pt on average
        # (scanners embed OCR text at high-res coordinates).
        # We normalise so body text ≈ 11 pt and headings scale proportionally.
        TARGET_BODY = 11.0
        if avg_size > 20.0:
            is_scanned = True
            scale = TARGET_BODY / avg_size   # e.g. avg=28pt → scale=0.39

        for blk in raw["blocks"]:
            if "lines" not in blk:
                continue
            bbox = blk["bbox"]
            if _is_inside_table(bbox, table_bboxes):
                continue

            lines_html: list[str] = []
            max_size = 0.0

            for ln in blk["lines"]:
                span_parts: list[str] = []
                for sp in ln["spans"]:
                    t = sp["text"]
                    if not t:
                        continue
                    raw_size = sp["size"]
                    # Apply normalisation and cap extremes
                    size = round(min(raw_size * scale, 28.0), 1)
                    # Floor to avoid sub-6pt invisible text (e.g. watermarks)
                    if size < 6.0:
                        size = 6.0
                    if size > max_size:
                        max_size = size
                    bold = bool(sp["flags"] & 16)
                    italic = bool(sp["flags"] & 2)

                    style = f"font-size:{size:.1f}pt;"
                    if bold:
                        style += "font-weight:bold;"
                    if italic:
                        style += "font-style:italic;"

                    span_parts.append(f'<span style="{style}">{_escape(t)}</span>')

                if span_parts:
                    lines_html.append("".join(span_parts))

            if not lines_html:
                continue

            x0, y0, x1, y1 = bbox
            block_w = x1 - x0
            is_large = max_size > TARGET_BODY * 1.2
            align = _alignment(x0, block_w, page_w, is_large)

            content = "<br/>".join(lines_html)
            p_style = f"text-align:{align};margin:0;line-height:1.6;"
            block_elements.append((y0, f'<p style="{p_style}">{content}</p>', y1))

    # ── 3. Merge tables + text, sort by y0 ───────────────────────────────────
    all_elems: list[tuple] = block_elements + table_elements
    all_elems.sort(key=lambda e: e[0])

    # ── 4. Assemble HTML with gap-based spacing ───────────────────────────────
    parts: list[str] = []
    prev_y1 = 0.0

    for y0, elem_html, y1 in all_elems:
        gap = max(0.0, y0 - prev_y1)
        margin = _gap_to_margin(gap)
        if margin > 0:
            parts.append(
                f'<div style="height:{margin}px;" aria-hidden="true"></div>'
            )
        parts.append(elem_html)
        prev_y1 = y1

    html_out = "\n".join(parts)
    return html_out, is_scanned


def pdf_to_html_pages(pdf_bytes: bytes) -> list[dict]:
    """
    Convert all pages of a PDF to HTML.
    Returns a list of dicts:
      { "page_num": int, "html": str, "width": float, "height": float,
        "is_scanned": bool }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        html_content, is_scanned = pdf_page_to_html(page)
        pages.append({
            "page_num": i + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "html": html_content,
            "is_scanned": is_scanned,
        })
    doc.close()
    return pages
