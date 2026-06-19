import io
import re
from html.parser import HTMLParser
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _pt_from_style(style_str: str, default: float = 9.0) -> float:
    """Extract font-size in pt from inline style string."""
    m = re.search(r"font-size\s*:\s*([\d.]+)pt", style_str or "")
    return float(m.group(1)) if m else default


def _is_bold(style_str: str, tag: str = "") -> bool:
    if tag in ("b", "strong"):
        return True
    if "font-weight:bold" in (style_str or "").replace(" ", ""):
        return True
    return False


def _align_from_style(style_str: str) -> WD_ALIGN_PARAGRAPH:
    if "text-align:center" in (style_str or "").replace(" ", ""):
        return WD_ALIGN_PARAGRAPH.CENTER
    if "text-align:right" in (style_str or "").replace(" ", ""):
        return WD_ALIGN_PARAGRAPH.RIGHT
    return WD_ALIGN_PARAGRAPH.LEFT


# ── Paragraph-level HTML → docx converter ────────────────────────────────────

class _Span:
    __slots__ = ("text", "bold", "size", "italic")
    def __init__(self, text, bold=False, size=9.0, italic=False):
        self.text = text
        self.bold = bold
        self.size = size
        self.italic = italic


class _Para:
    __slots__ = ("spans", "align", "space_before")
    def __init__(self, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0):
        self.spans: list[_Span] = []
        self.align = align
        self.space_before = space_before  # pt before this paragraph


class _HtmlDocxParser(HTMLParser):
    """Parse Gemini HTML fragment → list of _Para objects for python-docx."""

    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "tr", "li", "br"}

    def __init__(self):
        super().__init__()
        self.paras: list[_Para] = []
        self._cur: _Para = _Para()
        self._bold_stack: list[bool] = [False]
        self._size_stack: list[float] = [9.0]
        self._italic_stack: list[bool] = [False]
        self._style_stack: list[str] = [""]

    def _flush(self):
        if any(s.text.strip() for s in self._cur.spans):
            self.paras.append(self._cur)
        self._cur = _Para()

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        style = attrs_d.get("style", "")

        if tag in self.BLOCK_TAGS:
            self._flush()
            align = _align_from_style(style)
            # small top-margin for section breaks
            space_before = 2.0 if "margin-top:4" in style.replace(" ", "") or "margin:4" in style.replace(" ", "") else 0.0
            self._cur = _Para(align=align, space_before=space_before)

        # span / b / strong / i / em
        bold = _is_bold(style, tag) or self._bold_stack[-1]
        size = _pt_from_style(style, self._size_stack[-1])
        italic = (tag in ("i", "em")) or self._italic_stack[-1]

        self._bold_stack.append(bold)
        self._size_stack.append(size)
        self._italic_stack.append(italic)
        self._style_stack.append(style)

    def handle_endtag(self, tag):
        if self._bold_stack:
            self._bold_stack.pop()
            self._size_stack.pop()
            self._italic_stack.pop()
            self._style_stack.pop()
        if tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        text = data  # keep whitespace for inline joins
        if not text.strip():
            return
        self._cur.spans.append(_Span(
            text=text,
            bold=self._bold_stack[-1] if self._bold_stack else False,
            size=self._size_stack[-1] if self._size_stack else 9.0,
            italic=self._italic_stack[-1] if self._italic_stack else False,
        ))

    def get_paras(self) -> list[_Para]:
        self._flush()
        return self.paras


def _html_to_docx_paras(html: str) -> list[_Para]:
    # Remove spacer divs (<div style="height:Xpx"...>) — pure visual whitespace
    html = re.sub(r'<div[^>]*aria-hidden[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div[^>]*height\s*:\s*\d+px[^>]*>\s*</div>', '', html)
    parser = _HtmlDocxParser()
    parser.feed(html)
    return parser.get_paras()


def _add_html_page_to_doc(doc: Document, html: str):
    """Convert one page's translated_html into python-docx paragraphs."""
    paras = _html_to_docx_paras(html)
    for para in paras:
        p = doc.add_paragraph()
        p.alignment = para.align
        fmt = p.paragraph_format
        fmt.space_before = Pt(para.space_before)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0
        for span in para.spans:
            run = p.add_run(span.text)
            run.bold = span.bold
            run.italic = span.italic
            run.font.name = "Times New Roman"
            run.font.size = Pt(span.size)


def build_docx_from_translation(translation_result: dict) -> bytes:
    """
    Generate a beautifully formatted DOCX from structured translation blocks.
    Enforces consular standards: Times New Roman, 13pt body text, 14pt bold headings,
    preserves tables and alignment formatting.
    """
    is_html_mode = translation_result.get("mode") == "html"

    doc = Document()

    # Page setup: narrow margins for HTML mode to fit more content
    margin = Inches(0.8) if is_html_mode else Inches(1)
    for section in doc.sections:
        section.top_margin = margin
        section.bottom_margin = margin
        section.left_margin = margin
        section.right_margin = margin

    # Configure default style
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(9 if is_html_mode else 13)
    p_format = style.paragraph_format
    p_format.line_spacing = 1.0 if is_html_mode else 1.25
    p_format.space_after = Pt(0) if is_html_mode else Pt(4)
    p_format.space_before = Pt(0)

    # Process page by page
    for p_idx, page in enumerate(translation_result.get("pages", [])):
        if p_idx > 0:
            doc.add_page_break()

        # ── HTML mode: convert HTML → docx paragraphs preserving formatting ──
        if is_html_mode:
            _add_html_page_to_doc(doc, page.get("translated_html", ""))
            continue

        for block in page.get("blocks", []):
            block_type = block.get("type", "paragraph")
            
            if block_type == "table":
                cells = block.get("translated_cells", [])
                if not cells:
                    continue
                rows_count = len(cells)
                cols_count = len(cells[0]) if rows_count > 0 else 0
                if cols_count == 0:
                    continue
                
                table = doc.add_table(rows=rows_count, cols=cols_count)
                if not block.get("borderless", False):
                    table.style = 'Table Grid'
                
                for r_idx, row_data in enumerate(cells):
                    for c_idx, cell_value in enumerate(row_data):
                        val = cell_value or ""
                        cell = table.cell(r_idx, c_idx)
                        cell.text = str(val)
                        
                        # Set cell fonts
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.name = 'Times New Roman'
                                run.font.size = Pt(13)
            
            else: # paragraph
                text = block.get("translated", "")
                if not text.strip():
                    continue
                
                is_heading = block.get("is_heading", False)
                align_str = block.get("align", "left")
                is_bold = block.get("is_bold", False)
                
                p = doc.add_paragraph()
                
                # Apply alignments
                if align_str == "center":
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif align_str == "right":
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    # Preserve left indent from bbox x0 if present
                    bbox = block.get("bbox")
                    if bbox and len(bbox) >= 4:
                        x0 = bbox[0]
                        if x0 > 90:
                            indent_inches = (x0 - 72) / 72.0
                            p.paragraph_format.left_indent = Inches(min(3.5, max(0.0, indent_inches)))
                    
                # Split paragraph by original newlines to preserve spacing
                lines = text.split("\n")
                for l_idx, line in enumerate(lines):
                    if l_idx > 0:
                        p.add_run("\n")
                    run = p.add_run(line)
                    run.font.name = 'Times New Roman'
                    
                    if is_heading:
                        run.font.size = Pt(14)
                        run.bold = True
                    else:
                        run.font.size = Pt(13)
                        if is_bold:
                            run.bold = True
                            
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.read()
