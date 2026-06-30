"""
HTML translator: sends PDF pages directly to Gemini, returns translated HTML.
"""
import re
import logging
import os

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyBjAY03-8JWPUivjmIn3uwJBOu2HTPB2Cc"
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-1.5-flash",
]

VISION_PROMPT = """\
You are a Vietnamese-to-English legal document translator for consular purposes.

Read this Vietnamese PDF and output an HTML fragment that:
1. Translates ALL Vietnamese text to English — nothing left in Vietnamese
2. Reproduces the EXACT same visual layout and structure as the original document
3. Uses inline CSS for all styling

Layout rules:
- Keep the same number of columns, same table structure, same field arrangement as the original
- Borderless layout tables (headers, 2-col fields, signatures): use <table style="width:100%;border-collapse:collapse;table-layout:fixed"> with <td style="border:none;word-wrap:break-word">
- Data tables with visible lines (grade tables, tax detail tables): use <table style="width:100%;border-collapse:collapse;table-layout:fixed"> with <td style="border:1px solid #666;padding:2px 4px;word-wrap:break-word">
- Document title (e.g. BIRTH CERTIFICATE, STATE BUDGET PAYMENT SLIP): always as a standalone <p style="text-align:center;font-size:13pt;font-weight:bold;margin:8px 0"> — NOT inside a table cell
- "SOCIALIST REPUBLIC OF VIETNAM": font-size:10pt; font-weight:bold; text-align:center
- "Independence - Freedom - Happiness": font-size:9pt; font-style:italic; text-align:center
- Default text: font-size:9pt; line-height:1.5
- Labels bold, values normal

Translation rules:
- Personal names → UPPERCASE Latin no diacritics (NGUYEN VAN AN)
- "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" → "SOCIALIST REPUBLIC OF VIETNAM"
- "Độc lập - Tự do - Hạnh phúc" → "Independence - Freedom - Happiness"
- Dates: write as "August 12th, 2010" or "March 7th, 1968" (month name + ordinal day + year)
- Standard terms: Giấy khai sinh→Birth Certificate, Giấy đăng ký kết hôn→Marriage Certificate,
  Học bạ→School Report, Giấy nộp tiền vào ngân sách nhà nước→State Budget Payment Slip,
  Người nộp thuế→Taxpayer, Thuế GTGT→VAT, Tổng cộng→Total, Họ và tên→Full name,
  Ngày tháng năm sinh→Date of birth, Nơi sinh→Place of birth, Dân tộc→Ethnic group,
  Quốc tịch→Nationality, Chủ tịch→Chairman

Ignore circular stamps/seals — do not include their text.

Return ONLY the HTML fragment. No markdown, no explanation.
"""


def _call_gemini(model: str, api_key: str, prompt_text: str, retries: int = 3,
                 file_b64: str | None = None, mime_type: str = "application/pdf") -> str:
    import time
    import base64
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    if file_b64:
        contents = [
            types.Part.from_bytes(data=base64.b64decode(file_b64), mime_type=mime_type),
            types.Part.from_text(text=prompt_text),
        ]
    else:
        contents = [types.Part.from_text(text=prompt_text)]

    config = types.GenerateContentConfig(temperature=0.05, max_output_tokens=16384)
    last_err = None
    for attempt in range(retries):
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            return response.text.strip()
        except Exception as e:
            last_err = e
            if any(c in str(e) for c in ("400", "404", "INVALID_ARGUMENT")):
                raise
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_err


def translate_pdf_page_to_html(pdf_b64: str, api_key: str | None = None) -> str:
    """Send one PDF page to Gemini, return translated HTML fragment."""
    key = api_key or GEMINI_API_KEY
    for model in GEMINI_MODELS:
        try:
            raw = _call_gemini(model, key, VISION_PROMPT, file_b64=pdf_b64, mime_type="application/pdf")
            result = re.sub(r"^```[a-z]*\s*", "", raw)
            result = re.sub(r"\s*```$", "", result).strip()
            if result and len(result) > 30:
                logger.info(f"PDF translation succeeded: {model}")
                return result
        except Exception as e:
            logger.warning(f"PDF translate model {model} failed: {e}")
    return ""


# Compatibility aliases — kept so existing imports don't break
def translate_scanned_to_html(raw_text: str, api_key: str | None = None) -> str:
    return ""

def translate_scanned_image_to_html(image_b64: str, api_key: str | None = None) -> str:
    return translate_pdf_page_to_html(image_b64, api_key)

def translate_html_page(html: str, api_key: str | None = None, is_scanned: bool = False) -> str:
    return html  # no longer used

def translate_html_document(pages: list[dict], api_key: str | None = None) -> list[dict]:
    return pages  # no longer used
