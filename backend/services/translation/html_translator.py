"""
HTML-based translator using Gemini.

Takes the structured HTML output of html_extractor and asks Gemini to:
  - Translate Vietnamese text content to English
  - Preserve every HTML tag and inline style exactly
  - Apply standard consular terminology

Falls back to Google Translate per-paragraph if Gemini fails.
"""
import json
import re
import logging
import urllib.request
import urllib.error
import os
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDrLO5Y4untHFecD6iCPoJv5GOzhiEVVZM")
# Model confirmed working with this API key (v1beta endpoint)
GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

SYSTEM_PROMPT = """\
You are an expert Vietnamese-to-English consular and legal document translator.
You will receive an HTML fragment from a Vietnamese legal document.

Your task:
1. Translate ONLY the visible Vietnamese text inside HTML elements to formal English.
2. Preserve ALL HTML tags, inline styles, class names, and data attributes EXACTLY as-is — do not change font-size, font-weight, text-align, or any other CSS value.
3. Do NOT add or remove any HTML elements or attributes.
4. Transliterate Vietnamese PERSONAL NAMES ONLY to UPPERCASE Latin without diacritics.
   Example: "Nguyễn Đỗ Thảo Trân" → "NGUYEN DO THAO TRAN"
   All other text (labels, places, institutions) → normal case, NOT uppercase.
5. Use standard English consular terminology:
   - "Giấy khai sinh" / "GIAY KHAI SINH" → "BIRTH CERTIFICATE"
   - "Bản chính" / "BAN CHINH" → "ORIGINAL"
   - "Bản sao" → "COPY"
   - "Cộng hòa xã hội chủ nghĩa Việt Nam" → "SOCIALIST REPUBLIC OF VIETNAM" (ALL CAPS, bold)
   - "Độc lập - Tự do - Hạnh phúc" → "Independence – Freedom – Happiness"
   - "Họ và tên" → "Full name", "Giới tính" → "Gender", "Nam" → "Male", "Nữ" → "Female"
   - "Ngày, tháng, năm sinh" → "Date of birth"
   - "Nơi sinh" → "Place of birth"
   - "Dân tộc" → "Ethnic group", "Quốc tịch" → "Nationality"
   - "Họ và tên cha" → "Father's full name", "Họ và tên mẹ" → "Mother's full name"
   - "Nơi thường trú" → "Permanent residence"
   - "Ngày đăng ký" → "Date of registration"
   - "Người đi khai sinh" → "Birth declarer"
   - "Quan hệ với người được khai sinh" → "Relationship to the registered person"
   - "Bà ngoại" → "Grandmother", "Ông nội" → "Grandfather", "Cha" → "Father", "Mẹ" → "Mother"
   - "Người thực hiện" → "REGISTRAR", "Người ký giấy khai sinh" → "SIGNER OF BIRTH CERTIFICATE"
   - "Chủ tịch" → "CHAIRMAN", "Phó chủ tịch" → "VICE CHAIRMAN"
   - "Giấy kết hôn" → "Marriage Certificate"
   - "Học bạ" → "School Report", "Bảng điểm" → "Transcript"
   - "Xác nhận thông tin cư trú" → "Confirmation of Residence Information"
   - "Giấy chứng nhận quyền sử dụng đất" → "Certificate of Land Use Rights"
   - "Quyền sở hữu nhà ở" → "Ownership of House"
   - "Thửa đất số" → "Land lot No.", "Tờ bản đồ số" → "Map sheet No."
   - "Diện tích" → "Area", "Mục đích sử dụng" → "Purpose of use"
   - "Đất ở tại đô thị" → "Urban residential land"
   - "Sử dụng riêng" → "Private use", "Lâu dài" → "Long-term"
   - "Ông" → "Mr.", "Bà" → "Mrs."
6. Keep numbers, sequences of dots (......), dashes (---), and parentheses unchanged.
7. Do NOT add extra bold (font-weight:bold) to spans that are not bold in the source HTML. Preserve bold only where it already exists in the original styles.
8. Do NOT wrap your response in markdown code fences.
9. Return ONLY the translated HTML fragment — no explanations, no preamble.
"""

SCANNED_EXTRA = """\

IMPORTANT — This HTML was extracted from a SCANNED document. The text layer may contain OCR errors:
- Missing Vietnamese diacritics: "NGUYEN THINH TRONG" means "NGUYỄN THỊNH TRỌNG"
- Merged words: "CONG HOAXA HOI" means "CỘNG HÒA XÃ HỘI"
- Garbled characters: "Ghi bang chie" means "Ghi bằng chữ", "NGHiAVIETNAM" means "NGHĨA VIỆT NAM"
- Wrong letters: "1ong" means "Tổng", "Dantoe" means "Dân tộc", "Namsinhf" means "Năm sinh"
- Mixed characters: "Namsinh:Al.07.3.1908" means "Năm sinh: 07.3.1968"
Please RECONSTRUCT the correct Vietnamese meaning from context, then translate to English.
The document structure (birth certificate, land certificate, etc.) should guide your interpretation.
"""


def _call_gemini(model: str, api_key: str, prompt_text: str) -> str:
    """Call a specific Gemini model and return the text response."""
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.05, "maxOutputTokens": 8192},
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _gemini_translate_html(html: str, api_key: str, is_scanned: bool = False) -> str:
    """Send HTML to Gemini (tries multiple models) and return translated HTML."""
    system = SYSTEM_PROMPT + (SCANNED_EXTRA if is_scanned else "")
    prompt_text = (
        system
        + "\n\n--- HTML to translate ---\n"
        + html
        + "\n--- end ---"
    )

    last_err = None
    for model in GEMINI_MODELS:
        try:
            text = _call_gemini(model, api_key, prompt_text)
            # Strip markdown fences if Gemini wraps the HTML anyway
            text = re.sub(r"^```[a-z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
            if text:
                logger.info(f"Gemini HTML translation succeeded with model: {model}")
                return text
        except urllib.error.HTTPError as e:
            logger.warning(f"Gemini model {model} returned HTTP {e.code}, trying next…")
            last_err = e
        except Exception as e:
            logger.warning(f"Gemini model {model} failed: {e}, trying next…")
            last_err = e

    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")


# ── Fallback: extract text nodes and translate with Google ────────────────────

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts: list[str] = []

    def handle_data(self, data: str):
        if data.strip():
            self.texts.append(data)


def _google_translate(text: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="vi", target="en").translate(text) or text
    except Exception as e:
        logger.warning(f"Google Translate fallback error: {e}")
        return text


def _fallback_translate_html(html: str) -> str:
    """
    Crude fallback: split on tags, translate text nodes with Google.
    Only used when Gemini is unavailable.
    """
    parts = re.split(r"(<[^>]+>)", html)
    translated: list[str] = []
    for part in parts:
        if part.startswith("<") or not part.strip():
            translated.append(part)
        else:
            translated.append(_google_translate(part))
    return "".join(translated)


# ── Public interface ──────────────────────────────────────────────────────────

RECONSTRUCT_PROMPT = """\
You are an expert Vietnamese-to-English consular document translator and HTML formatter.

Below is raw OCR text extracted from a scanned Vietnamese legal document.
The OCR text may contain errors: missing diacritics, merged words, wrong characters.

Your task:
1. Identify the document type (birth certificate, marriage certificate, land certificate, etc.)
2. Reconstruct the correct content from context, fixing OCR errors
3. Translate to formal English using standard consular terminology
4. Format as a SINGLE compact HTML fragment that MUST fit on one A4 page. Rules:
   - All text uses line-height:1; margin:0; padding:0 — no extra spacing anywhere
   - Document title: <p style="text-align:center;margin:3px 0 1px 0;line-height:1;"><span style="font-size:11pt;font-weight:bold;">TITLE</span></p>
   - Header lines (SOCIALIST REPUBLIC OF VIETNAM, Independence...): <p style="text-align:center;margin:0;line-height:1;"><span style="font-size:9pt;font-weight:bold;">text</span></p>
   - Subtitle (ORIGINAL/COPY): <p style="text-align:center;margin:0;line-height:1;"><span style="font-size:9pt;">(text)</span></p>
   - No./Book No.: <table style="width:100%;border:none;border-collapse:collapse;margin:1px 0;line-height:1;"><tr><td style="font-size:9pt;border:none;">No.: X</td><td style="font-size:9pt;text-align:right;border:none;">Book No.: Y</td></tr></table>
   - Field label + value: <p style="margin:0;line-height:1;"><span style="font-size:9pt;"><b>Label:</b> value</span></p>
   - Two fields on same line: <table style="width:100%;border:none;border-collapse:collapse;margin:0;"><tr><td style="font-size:9pt;border:none;width:50%;line-height:1;"><b>Label1:</b> val1</td><td style="font-size:9pt;border:none;line-height:1;"><b>Label2:</b> val2</td></tr></table>
   - Three fields on same line: use 3-col borderless table, same style
   - CRITICAL: Do NOT invent section headers (FATHER, MOTHER, REGISTRATION DETAILS, etc.) not in the original. Only translate what exists.
   - Signature block: right-aligned, 9pt, line-height:1, margin:0
   - Do NOT bold values. Only bold labels and document title.
5. Consular terminology and formatting rules:
   - ONLY personal names (people's names) → write in UPPERCASE Latin without diacritics: e.g. Nguyễn Thịnh Trọng → NGUYEN THINH TRONG
   - All other text → normal Title Case or sentence case, NOT uppercase
   - "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" → "SOCIALIST REPUBLIC OF VIETNAM" (ALL CAPS, bold)
   - "Độc lập - Tự do - Hạnh phúc" → "Independence – Freedom – Happiness"
   - "Giấy khai sinh" → "Birth Certificate", "Bản chính" → "Original", "Bản sao" → "Copy"
   - "Họ và tên" → "Full name", "Giới tính" → "Gender", "Nam" → "Male", "Nữ" → "Female"
   - "Ngày, tháng, năm sinh" / "Ngày tháng năm sinh" → "Date of birth"
   - "Nơi sinh" → "Place of birth", "Dân tộc" → "Ethnic group", "Quốc tịch" → "Nationality"
   - "Nơi thường trú" / "Địa chỉ thường trú" → "Permanent residence"
   - "Họ và tên cha" → "Father's full name", "Họ và tên mẹ" → "Mother's full name"
   - "Năm sinh" → "Year of birth", "Ngày đăng ký" → "Date of registration"
   - "Người đi khai sinh" → "Birth declarer", "Quan hệ" → "Relationship"
   - "Người thực hiện" → "Registrar", "Người ký giấy khai sinh" → "Signer of Birth Certificate"
   - "Chủ tịch" → "Chairman", "Phó chủ tịch" → "Vice Chairman", "Giám đốc" → "Director"
   - "Số định danh cá nhân" → "Personal identification number"
   - "Quê quán" → "Place of origin"
   - "Thửa đất số" → "Land lot No.", "Tờ bản đồ số" → "Map sheet No."
   - "Diện tích" → "Area", "Lâu dài" → "Long-term", "Sử dụng riêng" → "Private use"
   - "Đất ở tại đô thị" → "Urban residential land"
   - "Mục đích sử dụng" → "Purpose of use", "Thời hạn sử dụng" → "Duration of use"
   - "Giấy chứng nhận quyền sử dụng đất" → "Certificate of Land Use Rights"
   - "Sở Tài nguyên và Môi trường" → "Department of Natural Resources and Environment"
   - "Ông" → "Mr.", "Bà" → "Mrs."

Do NOT wrap your response in markdown code fences.
Return ONLY the HTML fragment.

--- OCR TEXT ---
{text}
--- END ---
"""


def translate_scanned_to_html(raw_text: str, api_key: str | None = None) -> str:
    """
    For scanned/pure-image PDFs where the OCR text is unreliable:
    send the raw OCR text to Gemini and ask it to reconstruct + translate → clean HTML.
    """
    key = api_key or GEMINI_API_KEY
    if not raw_text.strip():
        return "<p style='color:#999;text-align:center;'>No text extracted from this page.</p>"

    prompt = RECONSTRUCT_PROMPT.replace("{text}", raw_text[:6000])
    for model in GEMINI_MODELS:
        try:
            text = _call_gemini(model, key, prompt)
            text = re.sub(r"^```[a-z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
            if text and len(text) > 30:
                logger.info(f"Scanned reconstruction succeeded with model: {model}")
                return text
        except urllib.error.HTTPError as e:
            logger.warning(f"Model {model} HTTP {e.code}, trying next…")
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")

    return _fallback_translate_html(raw_text)


def translate_html_page(html: str, api_key: str | None = None, is_scanned: bool = False) -> str:
    """
    Translate a single HTML page fragment.
    Tries Gemini; falls back to Google if Gemini fails.
    """
    key = api_key or GEMINI_API_KEY
    if not html.strip():
        return html

    if key:
        try:
            result = _gemini_translate_html(html, key, is_scanned=is_scanned)
            if result and len(result) > 20:
                return result
            logger.warning("Gemini returned empty/short HTML, using fallback.")
        except Exception as e:
            logger.warning(f"Gemini HTML translation failed: {e}. Using fallback.")

    return _fallback_translate_html(html)


def translate_html_document(pages: list[dict], api_key: str | None = None) -> list[dict]:
    """
    Translate a list of HTML pages (output of html_extractor.pdf_to_html_pages).
    Returns the same list with an added "translated_html" key per page.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _translate_page(page: dict) -> dict:
        translated = translate_html_page(
            page["html"],
            api_key,
            is_scanned=page.get("is_scanned", False),
        )
        return {**page, "translated_html": translated}

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_translate_page, pages))
    return results
