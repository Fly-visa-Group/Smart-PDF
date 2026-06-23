"""
HTML-based translator using Gemini.

Takes the structured HTML output of html_extractor and asks Gemini to:
  - Translate Vietnamese text content to English
  - Preserve every HTML tag and inline style exactly
  - Apply standard consular terminology

Falls back to Google Translate per-paragraph if Gemini fails.
"""
import re
import logging
import os
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyBjAY03-8JWPUivjmIn3uwJBOu2HTPB2Cc"
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


def _call_gemini(model: str, api_key: str, prompt_text: str, retries: int = 3,
                  file_b64: str | None = None, mime_type: str = "application/pdf") -> str:
    """Call Gemini via google-genai SDK. Supports text-only or multimodal (PDF/image)."""
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
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response.text.strip()
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "400" in err_str or "404" in err_str or "INVALID_ARGUMENT" in err_str:
                raise  # don't retry auth/model errors
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_err


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

VISION_PROMPT = """\
You are an expert Vietnamese-to-English legal document translator with deep knowledge of Vietnamese government forms.

You are looking at an image of a scanned Vietnamese legal/administrative document. The image may contain 1 or 2 pages stacked vertically.

⚠️ PRIMARY GOAL: Reproduce the EXACT same visual layout as the original document, translated to English.
- If the original has a 2-column layout → your HTML must have a 2-column layout
- If the original has a bordered table → your HTML must have a bordered table with the same columns
- If the original has a 3-part header (left/center/right) → your HTML must have the same 3-part header
- If the original has fields arranged side-by-side → your HTML must arrange them side-by-side
- Match the visual structure AS CLOSELY AS POSSIBLE using HTML tables and inline styles

Your task:
1. Read ALL text in the image carefully — every field, every value, every label, every number
2. Translate ALL text from Vietnamese to English (NOTHING left in Vietnamese in output)
3. Reproduce the document layout exactly using HTML with inline styles
4. Use font-size:8pt, line-height:1.1 as default. Title/heading: 11-13pt bold centered.

HTML LAYOUT RULES:
- 3-part document header: <table style="width:100%;border-collapse:collapse;margin:0 0 4px 0;"><tr><td style="border:none;width:33%;font-size:8pt;vertical-align:top;">left text</td><td style="border:none;text-align:center;font-size:8pt;font-weight:bold;vertical-align:top;">SOCIALIST REPUBLIC OF VIETNAM<br><span style="font-weight:normal;font-style:italic;">Independence – Freedom – Happiness</span></td><td style="border:none;width:33%;text-align:right;font-size:8pt;vertical-align:top;">right text</td></tr></table>
- Document title: <p style="text-align:center;margin:4px 0;font-size:13pt;font-weight:bold;">TITLE</p>
- Two-column fields (wife/husband, left/right person): <table style="width:100%;border-collapse:collapse;margin:0;"><tr><td style="border:none;width:50%;font-size:8pt;padding:1px 4px 1px 0;vertical-align:top;"><b>Label:</b> value</td><td style="border:none;width:50%;font-size:8pt;padding:1px 0 1px 4px;vertical-align:top;"><b>Label:</b> value</td></tr></table>
- Single full-width field: <p style="margin:1px 0;font-size:8pt;"><b>Label:</b> value</p>
- Bordered data table (transcripts, tax slips): <table style="width:100%;border-collapse:collapse;margin:4px 0;font-size:7.5pt;"><tr style="background:#f5f5f5;"><th style="border:1px solid #666;padding:2px 4px;text-align:center;">Col</th>...</tr><tr><td style="border:1px solid #666;padding:2px 4px;">data</td>...</tr></table>
- 3-column signature block: <table style="width:100%;border-collapse:collapse;margin:4px 0;"><tr><td style="border:none;width:33%;text-align:center;font-size:8pt;"><b>ROLE 1</b><br><i>(Sign and write full name)</i><br><br>NAME</td><td style="border:none;width:33%;text-align:center;font-size:8pt;">...</td><td style="border:none;width:33%;text-align:center;font-size:8pt;">...</td></tr></table>

TRANSLATION RULES:
- Personal names → UPPERCASE Latin without diacritics: NGUYEN VAN AN
- "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" → "SOCIALIST REPUBLIC OF VIETNAM" (bold, ALL CAPS)
- "Độc lập - Tự do - Hạnh phúc" → "Independence – Freedom – Happiness" (italic)
- "Giấy khai sinh" → "Birth Certificate"; "Bản chính" → "Original"; "Bản sao" → "Copy"
- "Giấy đăng ký kết hôn" / "Chứng nhận kết hôn" → "Marriage Certificate"
- "Họ và tên" → "Full name"; "Giới tính" → "Gender"; "Nam" → "Male"; "Nữ" → "Female"
- "Ngày tháng năm sinh" → "Date of birth"; "Nơi sinh" → "Place of birth"
- "Dân tộc" → "Ethnic group"; "Quốc tịch" → "Nationality"
- "Nơi thường trú" / "Địa chỉ thường trú" → "Permanent address"
- "Quê quán" → "Native village/place of origin"
- "Nghề nghiệp" → "Occupation"; "Số CMND/CCCD/Hộ chiếu" → "ID Card/Passport No."
- "Họ tên cha" → "Father's name"; "Họ tên mẹ" → "Mother's name"
- "Ngày đăng ký" → "Date of registration"
- "Người thực hiện" → "Registrar"; "Chủ tịch" → "Chairman"; "Phó Chủ tịch" → "Vice Chairman"
- "Học bạ" → "School Report"; "Bảng điểm" → "Transcript"
- "Môn học" → "Subject"; "Trung bình" → "Average"; "Xếp loại" → "Classification"
- "Giấy chứng nhận quyền sử dụng đất" → "Certificate of Land Use Rights"
- "Giấy nộp tiền vào ngân sách nhà nước" → "State Budget Payment Slip"
- "Người nộp thuế" → "Taxpayer"; "Mã số thuế" → "Tax code"
- "Thuế GTGT" → "VAT"; "Thuế thu nhập cá nhân" → "Personal Income Tax"
- "Tổng cộng" / "Tổng số tiền" → "Total"; "Số tiền bằng chữ" → "Amount in words"
- "Người nộp tiền" → "Payer"; "Kế toán trưởng" → "Chief Accountant"
- "Thủ trưởng đơn vị" → "Head of Unit"; "Kiểm soát viên" → "Controller"
- "Ông" → "Mr."; "Bà" → "Mrs."

Do NOT wrap output in markdown code fences.
Return ONLY the HTML fragment — no explanations, no preamble.
"""

RECONSTRUCT_PROMPT = None  # Deprecated — use Vision pipeline instead. Kept for import compat.
_RECONSTRUCT_PROMPT_REMOVED = """\
REMOVED — You are an expert Vietnamese-to-English consular document translator and HTML formatter.

⚠️ CRITICAL RULE: Your output HTML must contain ENGLISH TEXT ONLY. Every word must be translated from Vietnamese to English. Do NOT leave any Vietnamese words in your output. This is a TRANSLATION task, not a transcription task.

Below is raw OCR text extracted from a scanned Vietnamese legal document (may be 1 or 2 pages combined).
The OCR text may contain errors: missing diacritics, merged words, wrong characters.
If the text contains "--- PAGE 2 (table/details section) ---", it means the second page belongs to the same document — combine both sections into ONE complete HTML output covering all content from both pages.

Your task:
1. Identify the document type (birth certificate, marriage certificate, land certificate, tax payment slip, etc.)
2. Reconstruct the correct Vietnamese content from context, fixing OCR errors
3. Translate EVERYTHING to formal English — ALL labels, ALL values, ALL headers, ALL text in the output HTML must be in English
4. Format as a SINGLE compact HTML fragment that MUST fit on one A4 page. Rules:
   - All text uses line-height:1; margin:0; padding:0 — no extra spacing anywhere
   - Document title: <p style="text-align:center;margin:2px 0 0 0;line-height:0.8;"><span style="font-size:11pt;font-weight:bold;">TITLE</span></p>
   - Header lines (SOCIALIST REPUBLIC OF VIETNAM, Independence...): <p style="text-align:center;margin:0;line-height:0.8;"><span style="font-size:8pt;font-weight:bold;">text</span></p>
   - Subtitle (ORIGINAL/COPY): <p style="text-align:center;margin:0;line-height:0.8;"><span style="font-size:8pt;">(text)</span></p>
   - No./Book No.: <table style="width:100%;border:none;border-collapse:collapse;margin:0;"><tr><td style="font-size:8pt;border:none;line-height:0.8;">No.: X</td><td style="font-size:8pt;text-align:right;border:none;line-height:0.8;">Book No.: Y</td></tr></table>
   - Field label + value: <p style="margin:0;line-height:0.8;"><span style="font-size:8pt;"><b>Label:</b> value</span></p>
   - Two fields on same line: <table style="width:100%;border:none;border-collapse:collapse;margin:0;"><tr><td style="font-size:8pt;border:none;width:50%;line-height:0.8;"><b>Label1:</b> val1</td><td style="font-size:8pt;border:none;line-height:0.8;"><b>Label2:</b> val2</td></tr></table>
   - Three fields on same line: use 3-col borderless table, same style
   - CRITICAL: Do NOT invent section headers (FATHER, MOTHER, REGISTRATION DETAILS, etc.) not in the original. Only translate what exists.
   - Signature block: right-aligned, 8pt, line-height:0.8, margin:0
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
   TAX / FINANCE DOCUMENT TERMS:
   - "Giấy nộp tiền vào ngân sách nhà nước" → "State Budget Payment Slip"
   - "Mẫu số" → "Form No.", "Mã hiệu" → "Code", "Số" / "Số:" → "No.:", "Số tham chiếu" → "Reference No."
   - "Tiền mặt" → "Cash", "Chuyển khoản" → "Transfer", "Loại tiền" → "Currency", "Khác" → "Other"
   - "Người nộp thuế" → "Taxpayer", "Mã số thuế" → "Tax code"
   - "Địa chỉ" → "Address", "Quận/Huyện" → "District", "Tỉnh, TP" → "Province/City"
   - "Người nộp thay" → "Payer on behalf"
   - "Đề nghị NH/KBNN" → "Requesting Bank/State Treasury"
   - "Trích TK số" → "Debit Account No.", "hoặc thu tiền mặt để nộp NSNN theo" → "or collect cash for State Budget payment according to"
   - "TK thu NSNN" → "State Budget collection account"
   - "TK tạm thu" → "Temporary collection account"
   - "TK thu hồi hoàn thuế GTGT" → "VAT refund recovery account"
   - "Vào tài khoản của KBNN" → "To the account of State Treasury"
   - "Phòng giao dịch" → "Transaction Office", "KBNN khu vực" → "State Treasury Area"
   - "Mở tại NH ủy nhiệm thu" → "Opened at collecting authorized bank"
   - "Nộp theo văn bản của cơ quan có thẩm quyền" → "Payment according to document of competent authority"
   - "Kiểm toán nhà nước" → "State Audit", "Thanh tra tài chính" → "Financial Inspectorate"
   - "Thanh tra Chính phủ" → "Government Inspectorate", "Cơ quan có thẩm quyền khác" → "Other competent authority"
   - "Tên cơ quan quản lý thu" → "Name of managing tax authority"
   - "Phần dành cho người nộp thuế ghi" → "For taxpayer to fill in"
   - "Phần dành cho NH ủy nhiệm thu/ NH phối hợp thu/ KBNN ghi" → "For authorized collecting bank / cooperating bank / State Treasury to fill in"
   - "Số tờ khai/Số quyết định/Số thông báo/Mã định danh hồ sơ (ID)" → "Declaration No./Decision No./Notification No./Date/ID"
   - "Kỳ thuế/Ngày quyết định/Ngày thông báo" → "Tax period/Date"
   - "Nội dung các khoản nộp NSNN" → "Content of State Budget payments"
   - "Mã chương" → "Chapter code", "Mã NDKT (TM)" → "Sub-item code (TM)", "Mã DBHC" → "Admin area code (DBHC)"
   - "Số tiền VND" → "Amount in VND", "Số ngoại tệ nguyên tệ" → "Original currency amount"
   - "Thuế giá trị gia tăng" / "Thuế GTGT" → "Value added tax (VAT)"
   - "Thuế giá trị gia tăng hàng sản xuất trong nước" → "Value added tax on domestically manufactured goods"
   - "Tổng số tiền" → "Total amount", "Tổng cộng" → "Total"
   - "Tổng số tiền bằng chữ" → "Total amount in words"
   - "Người nộp thuế" (signature) → "FOR TAXPAYER", "NH ủy nhiệm thu/KBNN" (signature) → "FOR AUTHORIZED COLLECTING BANK / STATE TREASURY"
   - "Ký, ghi rõ họ tên, đóng dấu (nếu có)" → "(Sign, write full name, and stamp if applicable)"
   - "Ký, ghi rõ họ tên, chức vụ và đóng dấu" → "(Sign, write full name, position, and stamp)"
   - "CN" → "Branch", "Ngân hàng TMCP Quân đội" → "Military Commercial Joint Stock Bank"
   - "Thuế thu nhập cá nhân" → "Personal income tax", "Thuế thu nhập doanh nghiệp" → "Corporate income tax"
   TABLE RECONSTRUCTION RULES (for tax payment slip detail pages):
   - The payment table has columns: STT | Declaration No./ID | Tax period | Content of State Budget payments | Original currency amount | Amount (VND) | Chapter code | Sub-item code (TM) | Admin area code (DBHC)
   - Typical rows: Row 1 = Value added tax (VAT on domestic production), Sub-item 1701; Row 2 = Personal income tax from production/business, Sub-item 1003; Chapter code is always 757
   - If OCR text is garbled and some amounts are missing, infer from Total: e.g. if Total=1,200,000 and PIT=400,000, then VAT=800,000
   - Render the table WITH visible borders: <table style="width:100%;border-collapse:collapse;margin:2px 0;font-size:7pt;">
   - Header row: <tr style="background:#f0f0f0;"><th style="border:1px solid #999;padding:2px 3px;text-align:center;">No.</th><th ...>Declaration No./ID</th>...</tr>
   - Data rows: <tr><td style="border:1px solid #999;padding:2px 3px;text-align:center;">1</td>...</tr>
   - Total row: <tr><td colspan="5" style="border:1px solid #999;padding:2px;font-weight:bold;">Total</td><td style="border:1px solid #999;padding:2px;text-align:right;font-weight:bold;">1,200,000</td><td colspan="3" style="border:1px solid #999;"></td></tr>
   - "FOR STATE TREASURY TO FILL IN UPON ACCOUNTING:" section: use a compact bordered box, 7pt
   - Signature section: two columns — left = PAYER, right = bank + date + staff names
   - Do NOT omit any section visible in OCR (accounting box, signatures, staff names)
   MARRIAGE CERTIFICATE (Chứng nhận kết hôn / Giấy đăng ký kết hôn) TEMPLATE:
   Use this exact layout when the document is a marriage certificate:
   <table style="width:100%;border-collapse:collapse;font-size:8pt;margin:0;"><tr>
     <td style="border:none;width:35%;vertical-align:top;line-height:1.2;"><b>Province/City:</b> ___<br><b>District:</b> ___<br><b>Commune/Ward:</b> ___</td>
     <td style="border:none;text-align:center;vertical-align:top;line-height:1.2;"><b>SOCIALIST REPUBLIC OF VIETNAM</b><br><i>Independence – Freedom – Happiness</i></td>
     <td style="border:none;width:25%;text-align:right;vertical-align:top;line-height:1.2;"><b>Form TP-HT6</b><br><b>Book No.:</b> ___<br><b>No.:</b> ___</td>
   </tr></table>
   <p style="text-align:center;font-size:14pt;font-weight:bold;margin:6px 0 4px 0;">MARRIAGE CERTIFICATE</p>
   Then use 2-column borderless table for all fields:
   Wife (left column) | Husband (right column)
   Fields: Full name | Date of birth | Native village (Quê quán) | Permanent residence | Occupation | Ethnic group | Nationality | ID card / Passport No.
   Then date/place row, then 3-column signature: Wife's signature | Husband's signature | ON BEHALF OF PEOPLE'S COMMITTEE CHAIRMAN (Signed and sealed)
   SCHOOL TRANSCRIPT (Học bạ / Bảng điểm) TEMPLATE:
   Use this layout when the document is a school transcript or report card:
   Header: SCHOOL TRANSCRIPT or ACADEMIC TRANSCRIPT (centered, bold)
   Student info fields: Full name, Gender, Date of birth, School year(s), Permanent address
   Subject table with borders: <table style="width:100%;border-collapse:collapse;font-size:8pt;margin:4px 0;">
     Header row: SUBJECTS | Grade 10 | Grade 11 | Grade 12 (or Semester 1 | Semester 2 etc.)
     Rows: Mathematics, Physics, Chemistry, Biology, Computer Science, Vietnamese Literature, History, Geography, English, etc.
     Average grade row at bottom
   </table>
   Evaluation table: Academic Ability | Moral Training rows with same grade columns
   Grading system explanation if present
   Signature block at bottom right: Date/place, Certified by Principal/Vice Principal

Do NOT wrap your response in markdown code fences.
Return ONLY the HTML fragment.

--- OCR TEXT ---
{text}
--- END ---
"""


def _clean_gemini_html(text: str) -> str:
    text = re.sub(r"^```[a-z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def translate_pdf_page_to_html(pdf_b64: str, api_key: str | None = None) -> str:
    """
    Send a single-page (or two-page) PDF directly to Gemini as application/pdf.
    Gemini reads the PDF natively — no OCR, no image rendering needed.
    Works for both text PDFs and scanned/image PDFs.
    """
    key = api_key or GEMINI_API_KEY
    for model in GEMINI_MODELS:
        try:
            raw = _call_gemini(model, key, VISION_PROMPT, file_b64=pdf_b64, mime_type="application/pdf")
            result = _clean_gemini_html(raw)
            if result and len(result) > 30:
                logger.info(f"PDF translation succeeded with model: {model}")
                return result
        except Exception as e:
            logger.warning(f"PDF translate: model {model} failed: {e}, trying next…")
    return ""


# Keep old names as aliases for any code that still imports them
def translate_scanned_image_to_html(image_b64: str, api_key: str | None = None) -> str:
    return translate_pdf_page_to_html(image_b64, api_key)

def translate_scanned_to_html(raw_text: str, api_key: str | None = None) -> str:
    return ""


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

    For scanned pages with image_b64: uses Gemini vision (highest quality).
    Falls back to OCR-text path if vision fails.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _translate_page(page: dict) -> dict:
        is_scanned = page.get("is_scanned", False)
        image_b64 = page.get("image_b64")

        # Best path: send actual image to Gemini vision
        if is_scanned and image_b64:
            translated = translate_scanned_image_to_html(image_b64, api_key)
            if translated:
                return {**page, "translated_html": translated}
            logger.warning(f"Page {page['page_num']}: vision failed, falling back to OCR text path")

        # Fallback: OCR text → Gemini text
        translated = translate_html_page(
            page["html"],
            api_key,
            is_scanned=is_scanned,
        )
        return {**page, "translated_html": translated}

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_translate_page, pages))
    return results
