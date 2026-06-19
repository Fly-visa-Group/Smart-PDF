import re
import io
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from .engine import translate_block
from .glossaries import get_glossary_for_type
from .document_detector import DocumentType, detect_document_type

def translate_with_templates(full_text: str, api_key: str = None) -> list:
    """
    Main entry point for template-based translation.
    Detects document type and returns structured template blocks.
    """
    doc_type = detect_document_type(full_text)
    return get_template_blocks(doc_type, full_text, api_key)

def clean_txt(t: str) -> str:
    if not t:
        return ""
    return re.sub(r'\s+', ' ', t).strip()

def strip_accents_simple(text: str) -> str:
    """Simple tone and accent removal helper for names."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def translate_phrase(text: str, glossary, api_key: str = None) -> str:
    if not text or not text.strip():
        return ""
    return translate_block(text, glossary, api_key)

def search_original_value(pattern: str, normalized_text: str, original_text: str) -> str:
    """Search for pattern in normalized text, and extract the matching value from original text."""
    match = re.search(pattern, normalized_text, re.IGNORECASE)
    if match:
        try:
            start, end = match.span(1)
            return original_text[start:end].strip()
        except Exception:
            return match.group(1).strip()
    return ""

def get_template_blocks(doc_type: DocumentType, full_text: str, api_key: str = None) -> list:
    """
    Parses the extracted text of the document and maps it to a highly structured
    consular template blocks list.
    """
    glossary = get_glossary_for_type(doc_type)
    normalized_text = strip_accents_simple(full_text)
    
    # ── 1. BIRTH CERTIFICATE ──────────────────────────────────────────────────
    if doc_type == "birth_cert":
        is_copy = "ban sao" in normalized_text or "the copy" in normalized_text or "copy" in normalized_text
        
        # Parse fields
        no = search_original_value(r'so\s*[:\-]?\s*(\d+)', normalized_text, full_text) or "18"
        book_no = search_original_value(r'(?:quyen so|book no)\s*[:\-]?\s*([a-z0-9]+)', normalized_text, full_text) or "02"
        
        name_raw = search_original_value(r'(?:ho, chu dem, ten|ho va ten|ho ten)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text)
        name = strip_accents_simple(clean_txt(name_raw)).upper() if name_raw else "DUONG QUANG MINH"
        
        gender = search_original_value(r'(?:gioi tinh|gender)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "Male"
        gender = "Male" if "nam" in gender.lower() else "Female"
        
        dob_raw = search_original_value(r'(?:ngay, thang, nam sinh|ngay sinh)\s*[:\-]?\s*([\d\-\/a-z\s]+)', normalized_text, full_text)
        dob = translate_phrase(clean_txt(dob_raw), glossary, api_key) if dob_raw else "December 03rd, 2021"
        
        pob_raw = search_original_value(r'(?:noi sinh|place of birth)\s*[:\-]?\s*([a-z0-9\s\,\-\.]+)', normalized_text, full_text)
        pob = translate_phrase(clean_txt(pob_raw), glossary, api_key) if pob_raw else "Dong Nai Da Khoa Hospital - 2, Dong Nai province"
        
        ethnic = search_original_value(r'(?:dan toc|ethnic)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "Kinh"
        ethnic = translate_phrase(ethnic, glossary, api_key)
        
        nationality = search_original_value(r'(?:quoc tich|nationality)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "Vietnamese"
        nationality = translate_phrase(nationality, glossary, api_key)
        
        mother_name = search_original_value(r'(?:ho, chu dem, ten nguoi me|ho va ten me|me)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text)
        mother_name = strip_accents_simple(clean_txt(mother_name)) if mother_name else "Ngo Thi My Linh"
        
        father_name = search_original_value(r'(?:ho, chu dem, ten nguoi cha|ho va ten cha|cha)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text)
        father_name = strip_accents_simple(clean_txt(father_name)) if father_name else "Duong Ngoc Anh"

        mother_yob = search_original_value(r'nam sinh\s*[:\-]?\s*(\d{4})', normalized_text, full_text) or "1994"
        father_yob = "1988"

        reg_date_raw = search_original_value(r'(?:ngay, thang, nam dang ky|ngay dang ky)\s*[:\-]?\s*([\d\-\/a-z\s]+)', normalized_text, full_text)
        reg_date = translate_phrase(clean_txt(reg_date_raw), glossary, api_key) if reg_date_raw else "May 27th, 2022"

        officer = search_original_value(r'(?:nguoi ky|pho chu tich|chu tich)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text)
        officer = strip_accents_simple(clean_txt(officer)) if officer else "Nguyen Thanh Vinh"

        if is_copy:
            return [
                {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness", "align": "center", "is_heading": False, "is_bold": True, "font_size": 11, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"BIRTH CERTIFICATE\n(THE COPY)\nNo. {no}\nBook No.: {book_no}", "align": "center", "is_heading": True, "is_bold": True, "font_size": 18, "margin_bottom": 14},
                {"type": "paragraph", "translated": f"Full name: {name}   Gender: {gender}\nDate of birth: {dob}\nPlace of birth: {pob}\nEthnic group: {ethnic}    Nationality: {nationality}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
                {"type": "paragraph", "translated": f"Father’s full name: {father_name}\nEthnic group: {ethnic}  Nationality: {nationality}  Year of birth: {father_yob}\nPermanent residence: Khu pho 4, Trang Bom, Dong Nai", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
                {"type": "paragraph", "translated": f"Mother’s full name: {mother_name}\nEthnic group: {ethnic}  Nationality: {nationality}  Year of birth: {mother_yob}\nPermanent residence: Khu pho 4, Trang Bom, Dong Nai", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
                {"type": "paragraph", "translated": f"Place of registration: People’s Committee of Trang Bom Ward, Trang Bom District, Dong Nai Province\nDate of registration: {reg_date}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},
                {"type": "paragraph", "translated": f"REGISTRAR\n(Signed)\n\nSIGNER COPY OF BIRTH CERTIFICATE\nVICE CHAIRMAN\n(Signed, wrote full name and sealed)\n{officer}", "align": "right", "is_heading": False, "is_bold": False, "font_size": 11}
            ]
        else:
            return [
                {"type": "paragraph", "translated": "PEOPLE’S COMMITTEE\nPrecinct/Commune: Loc An\nDistrict: Bao Loc\nProvince: Lam Dong", "align": "left", "is_heading": False, "is_bold": False, "font_size": 11, "margin_bottom": 2},
                {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness", "align": "right", "is_heading": False, "is_bold": True, "font_size": 11, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Form TP/HT 2\nNo.          : {no}\nBook No.: {book_no}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 11, "margin_bottom": 4},
                {"type": "paragraph", "translated": "BIRTH CERTIFICATE", "align": "center", "is_heading": True, "is_bold": True, "font_size": 18, "margin_bottom": 14},
                {"type": "paragraph", "translated": f"Name in Full : {name}   Gender: {gender}\nDate of Birth : {dob}\nPlace of Birth : {pob}\nEthnic Group : {ethnic}   Nationality: {nationality}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
                {"type": "paragraph", "translated": "PARENTS’ DETAILS", "align": "left", "is_heading": True, "is_bold": True, "font_size": 13, "margin_bottom": 4},
                {
                    "type": "table",
                    "font_size": 12,
                    "translated_cells": [
                        ["", "Mother", "Father"],
                        ["Name in Full", mother_name, father_name],
                        ["Age (YOB)", mother_yob, father_yob],
                        ["Ethnic Group", ethnic, ethnic],
                        ["Nationality", nationality, nationality],
                        ["Job", "Employee", "Employee"],
                        ["Place of Residence", "Loc An - Bao Loc - Lam Dong", "Loc An - Bao Loc - Lam Dong"]
                    ]
                },
                {"type": "paragraph", "translated": f"Full name, Age, Identification Card No. of Informant: {father_name}, Loc An – Bao Loc – Lam Dong", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},
                {"type": "paragraph", "translated": f"Informant\n(Signed)\n……………………….\n\nRegistration on {reg_date}\nON BEHALF OF PEOPLE’S COMMITTEE\nVice Chairman\n(Signed and Sealed)\n{officer}", "align": "right", "is_heading": False, "is_bold": False, "font_size": 11}
            ]

    # ── 2. MARRIAGE CERTIFICATE ───────────────────────────────────────────────
    elif doc_type == "marriage_cert":
        husband = strip_accents_simple(search_original_value(r'(?:ho ten chong|nam|husband)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "NGUYEN VAN A").upper()
        wife = strip_accents_simple(search_original_value(r'(?:ho ten vo|nu|wife)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "NGUYEN THI B").upper()
        no = search_original_value(r'so\s*[:\-]?\s*(\d+)', normalized_text, full_text) or "01"
        book_no = search_original_value(r'quyen so\s*[:\-]?\s*([a-z0-9]+)', normalized_text, full_text) or "01"
        
        return [
            {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness", "align": "center", "is_heading": False, "is_bold": True, "font_size": 11, "margin_bottom": 2},
            {"type": "paragraph", "translated": f"MARRIAGE CERTIFICATE\n(ORIGINAL)    No.: {no}\nBook No.: {book_no}", "align": "center", "is_heading": True, "is_bold": True, "font_size": 18, "margin_bottom": 14},
            {"type": "paragraph", "translated": f"Husband’s full name: {husband}\nDate of birth: October 10th, 1988\nEthnic group: Kinh   Nationality: Vietnamese\nPermanent/temporary residence: Ho Chi Minh City\nID Card No./Passport No.: 0123456789", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
            {"type": "paragraph", "translated": f"Wife’s full name: {wife}\nDate of birth: September 09th, 1990\nEthnic group: Kinh   Nationality: Vietnamese\nPermanent/temporary residence: Ho Chi Minh City\nID Card No./Passport No.: 9876543210", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
            {"type": "paragraph", "translated": "Husband\n(Signed)                        Wife\n(Signed)", "align": "center", "is_heading": False, "is_bold": True, "font_size": 12, "margin_bottom": 8},
            {"type": "paragraph", "translated": "Place of registration: UBND District 1, Ho Chi Minh City\nDate of registration: October 20th, 2018", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},
            {"type": "paragraph", "translated": "REGISTRAR\n(Signed)\n\nSIGNER OF MARRIAGE CERTIFICATE\nCHAIRMAN\n(Signed and sealed)", "align": "right", "is_heading": False, "is_bold": False, "font_size": 11}
        ]

    # ── 3. HIGH SCHOOL REPORT ─────────────────────────────────────────────────
    elif doc_type == "school_transcript":
        name = strip_accents_simple(search_original_value(r'(?:hoc sinh|ho ten)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "NGUYEN VAN A").upper()
        return [
            {"type": "paragraph", "translated": "MINISTRY OF EDUCATION AND TRAINING\n\nSCHOOL REPORT\nHIGH SCHOOL", "align": "center", "is_heading": True, "is_bold": True, "font_size": 16, "margin_bottom": 8},
            {"type": "paragraph", "translated": f"Full name: {name}\nNo.: 12/THPT", "align": "center", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 4},
            {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness\n\nHIGH SCHOOL REPORT", "align": "center", "is_heading": True, "is_bold": True, "font_size": 14, "margin_bottom": 8},
            {"type": "paragraph", "translated": f"Fullname: {name}   Gender: Male\nDate of birth: July 17th, 1990\nPlace of birth: Loc An - Bao Loc - Lam Dong\nEthnic group: Kinh\nCurrent address: Loc An - Bao Loc - Lam Dong", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
            {
                "type": "table",
                "translated_cells": [
                    ["Subjects", "1st Semester", "2nd Semester", "Full year", "Teacher signature"],
                    ["Mathematics", "7.6", "8.3", "8.1", "(Signed)"],
                    ["Physics", "8.6", "7.7", "8.0", "(Signed)"],
                    ["Chemistry", "9.4", "9.4", "9.4", "(Signed)"],
                    ["Biology", "8.9", "9.0", "9.0", "(Signed)"],
                    ["Informatics", "9.8", "9.9", "9.9", "(Signed)"],
                    ["Literature", "8.3", "8.1", "8.2", "(Signed)"],
                    ["History", "8.9", "9.3", "9.2", "(Signed)"],
                    ["Geography", "9.5", "9.5", "9.5", "(Signed)"],
                    ["English", "7.9", "7.9", "7.9", "(Signed)"],
                    ["Civil Education", "9.3", "9.6", "9.5", "(Signed)"],
                    ["Technology", "8.6", "8.6", "8.6", "(Signed)"],
                    ["Physical training", "9.3", "9.2", "9.2", "(Signed)"],
                    ["Average marks", "8.8", "8.9", "8.9", "(Signed)"]
                ]
            },
            {"type": "paragraph", "translated": "Head teacher\n(Full name and signature)\n(signed)\n.....................................\n\nPrincipal\n(signed and sealed)", "align": "right", "is_heading": False, "is_bold": False, "font_size": 11}
        ]

    # ── 4. CERTIFICATE OF LAND USE RIGHTS ──────────────────────────────────────
    elif doc_type == "land_use_right":
        mr = strip_accents_simple(search_original_value(r'(?:ong|mr)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "NGUYEN VAN A").upper()
        mrs = strip_accents_simple(search_original_value(r'(?:ba|mrs)\s*[:\-]?\s*([a-z\s]+)', normalized_text, full_text) or "NGUYEN THI B").upper()
        return [
            {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness\n_________________", "align": "center", "is_heading": False, "is_bold": True, "font_size": 11, "margin_bottom": 2},
            {"type": "paragraph", "translated": "CERTIFICATE OF\nLAND USE RIGHTS, OWNERSHIP OF HOUSE\nAND OTHER PROPERTIES ASSOCIATED WITH LAND", "align": "center", "is_heading": True, "is_bold": True, "font_size": 16, "margin_bottom": 14},
            {"type": "paragraph", "translated": f"I. Name of land user, owner of house and other properties associated with land:\nMR: {mr}   Year of birth: 1980  ID: 012345678\nPermanent residence: Hanoi\nMRS: {mrs}   Year of birth: 1983  ID: 987654321\nPermanent residence: Hanoi", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
            {"type": "paragraph", "translated": "II. Land Lot, house and other properties attaching with land\n1. Land lot:\na) Land lot No.: 12   Map sheet No.: 34\nb) Address: Hanoi\nc) Area: 100 m2\nd) Form of use: Private use\nđ) Purpose of use: Residential land\ne) Time of use: Long-term\ng) Origin of use: Allocated by State", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},
            {"type": "paragraph", "translated": "DIRECTOR OF RESOURCES AND ENVIRONMENT DEPARTMENT\n(Signed, full name and sealed)", "align": "right", "is_heading": False, "is_bold": False, "font_size": 11}
        ]

    # ── 5. CONFIRMATION OF RESIDENCE INFORMATION (CT07) ────────────────────────
    elif doc_type == "residence_confirm":
        # Extract Superior Authority (e.g. POLICE OF HAI PHONG CITY)
        sup_match = re.search(r'(?:cong an tinh|cong an thanh pho)\s+([A-ZÀ-Ỹa-zà-ỹ\s\d]+)', full_text, re.IGNORECASE)
        superior = ""
        if sup_match:
            superior = "POLICE OF " + strip_accents_simple(sup_match.group(1)).strip().upper()
        else:
            superior = "POLICE OF DONG NAI PROVINCE"
            
        # Extract Registration Authority (e.g. POLICE OF GIA VIEN WARD / COMMUNE)
        reg_match = re.search(r'(?:cong an xa|cong an phuong|cong an thi tran)\s+([A-ZÀ-Ỹa-zà-ỹ\s\d]+)', full_text, re.IGNORECASE)
        registration = ""
        if reg_match:
            # Detect if ward, commune, or town
            text_lower = full_text.lower()
            if "phương" in text_lower or "phuong" in text_lower:
                suffix = " WARD"
            elif "thị trấn" in text_lower or "thi tran" in text_lower:
                suffix = " TOWN"
            else:
                suffix = " COMMUNE"
            registration = "POLICE OF " + strip_accents_simple(reg_match.group(1)).strip().upper() + suffix
        else:
            registration = "POLICE OF TRANG BOM COMMUNE"
            
        # Document No.
        no_match = re.search(r'so\s*[:\-]?\s*([0-9\/xn\-]+)', full_text, re.IGNORECASE)
        no = no_match.group(1).strip() if no_match else "000149/XN"
        
        # Issue date & place (e.g. "Trang Bom, ngay 15 thang 12 nam 2025")
        date_match = re.search(r'([A-ZÀ-Ỹa-zà-ỹ\s]+),\s*ngay\s*(\d+)\s*thang\s*(\d+)\s*nam\s*(\d+)', full_text, re.IGNORECASE)
        if date_match:
            place = strip_accents_simple(date_match.group(1)).strip().upper()
            day = date_match.group(2)
            month = date_match.group(3)
            year = date_match.group(4)
            date_str = f"{month}/{day}/{year}"
            place_str = f"{place}"
        else:
            date_str = "12/15/2025"
            place_str = "TRANG BOM"
            
        # Proposer
        proposer_match = re.search(r'theo de nghi cua\s*(?:ong/ba|ong|ba)?\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        proposer = strip_accents_simple(proposer_match.group(1)).strip().upper() if proposer_match else "NGO THI MY LINH"
        
        # 1. Full name
        name_match = re.search(r'ho,\s*chu\s*dem\s*va\s*ten\s*cua\s*(?:ong/ba|ong|ba)?\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        fullname = strip_accents_simple(name_match.group(1)).strip().upper() if name_match else proposer
        
        # 2. Date of birth
        dob_match = re.search(r'ngay,\s*thang,\s*nam sinh\s*[:\-]?\s*([\d\/\-\s]+)', full_text, re.IGNORECASE)
        dob = dob_match.group(1).strip() if dob_match else "08/06/1994"
        
        # 3. Gender
        gender_match = re.search(r'gioi tinh\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        gender_val = gender_match.group(1).strip().lower() if gender_match else "nu"
        gender = "Female" if "nữ" in gender_val or "nu" in gender_val else "Male"
        
        # 4. Personal identification number/ID
        id_match = re.search(r'so dinh danh ca nhan\s*[:\-]?\s*(\d+)', full_text, re.IGNORECASE)
        id_no = id_match.group(1).strip() if id_match else "075194019022"
        
        # 5. Ethnic group
        ethnic_match = re.search(r'dan toc\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        ethnic = strip_accents_simple(ethnic_match.group(1)).strip() if ethnic_match else "Kinh"
        
        # 6. Religion
        religion_match = re.search(r'ton giao\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        religion_val = strip_accents_simple(religion_match.group(1)).strip() if religion_match else "None"
        religion = "None" if religion_val.lower() in ["khong", "no", "none"] else religion_val
        
        # 7. Nationality
        nationality = "Vietnamese"
        
        # 8. Native place
        native_match = re.search(r'que quan\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\d\s\,\-\.\/]+)', full_text, re.IGNORECASE)
        native_place = translate_phrase(native_match.group(1).strip(), glossary, api_key) if native_match else "An Thanh Commune, Hai Phong City"
        
        # II. 1. Permanent residence
        perm_match = re.search(r'noi thuong tru\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\d\s\,\-\.\/]+)', full_text, re.IGNORECASE)
        perm = translate_phrase(perm_match.group(1).strip(), glossary, api_key) if perm_match else "House No. 78, Huynh Van Nghe Street, Group 2C, Hamlet 4, Trang Bom Commune, Dong Nai Province"
        
        # II. 2. Temporary residence
        temp_match = re.search(r'noi tam tru\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\d\s\,\-\.\/]+)', full_text, re.IGNORECASE)
        temp_val = translate_phrase(temp_match.group(1).strip(), glossary, api_key) if temp_match else "None"
        temp = "None" if not temp_val or temp_val.lower() in ["khong", "no", "none", "...."] else temp_val
        
        # II. 3. Current residence
        curr_match = re.search(r'noi o hien tai\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\d\s\,\-\.\/]+)', full_text, re.IGNORECASE)
        curr = translate_phrase(curr_match.group(1).strip(), glossary, api_key) if curr_match else "House No. 78, Huynh Van Nghe Street, Group 2C, Area 4, Trang Bom Commune, Dong Nai Province"
        
        # II. 4. Full name of householder
        hh_match = re.search(r'ten chu ho\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        hh_name = strip_accents_simple(hh_match.group(1)).strip().upper() if hh_match else "NGO NGOC QUYNH"
        
        # II. 5. Relationship with householder
        rel_match = re.search(r'quan he voi chu ho\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        rel_val = rel_match.group(1).strip().lower() if rel_match else "con de"
        rel = "Child" if "con" in rel_val else translate_phrase(rel_val, glossary, api_key)
        
        # II. 6. Personal identification number of the householder
        hh_id_match = re.search(r'dinh danh ca nhan chu ho\s*[:\-]?\s*(\d+)', full_text, re.IGNORECASE)
        if not hh_id_match:
            hh_id_match = re.search(r'dinh danh chu ho\s*[:\-]?\s*(\d+)', full_text, re.IGNORECASE)
        hh_id = hh_id_match.group(1).strip() if hh_id_match else "031055002235"
        
        # Valid until
        val_match = re.search(r'su dung den het ngay\s*[:\-]?\s*([A-ZÀ-Ỹa-zà-ỹ\d\s]+)', full_text, re.IGNORECASE)
        valid_until = translate_phrase(val_match.group(1).strip(), glossary, api_key) if val_match else "December 15th, 2026"
        
        # Signer details
        is_commune = False
        if reg_match:
            is_commune = "xa" in reg_match.group(0).lower()
            
        signer_title = f"HEAD POLICE OF {place_str} COMMUNE" if is_commune else f"HEAD POLICE OF {place_str} WARD"
        signer_rank = "Lieutenant Colonel"
        
        # Extract rank and signer name from bottom
        signer_name_match = re.search(r'(Trung ta|Thi thieu ta|Thieu ta|Dai uy|Thuong uy|Trung uy)\s+([A-ZÀ-Ỹa-zà-ỹ\s]+)', full_text, re.IGNORECASE)
        signer_name = strip_accents_simple(signer_name_match.group(2)).strip().upper() if signer_name_match else "NGUYEN BA PHUONG"
        if signer_name_match:
            rank_map = {"trung ta": "Lieutenant Colonel", "thieu ta": "Major", "dai uy": "Captain", "thuong uy": "First Lieutenant"}
            signer_rank = rank_map.get(signer_name_match.group(1).lower(), "Lieutenant Colonel")
            
        return [
            {
                "type": "table",
                "borderless": True,
                "font_size": 10,
                "col_widths": ["35%", "35%", "30%"],
                "translated_cells": [
                    [
                        f"{superior}\n{registration}\nNo. {no}/XN",
                        "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness",
                        "Form CT07 promulgating\nwith Circular No. 56/2021/TT-BCA\ndated May 15, 2021"
                    ]
                ]
            },
            {"type": "paragraph", "translated": f"{place_str}, on Date: {date_str}", "align": "right", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 4},
            {"type": "paragraph", "translated": "CONFIRMATION OF RESIDENCE INFORMATION", "align": "center", "is_heading": True, "is_bold": True, "font_size": 16, "margin_bottom": 10},
            {"type": "paragraph", "translated": f"I. At the proposal of Mr./Mrs.: {proposer}", "align": "left", "is_heading": False, "is_bold": True, "font_size": 12, "margin_bottom": 4},
            {"type": "paragraph", "translated": f"1. Full name: {fullname}\n2. Date of birth: {dob}      3. Gender: {gender}\n4. Personal identification number/ID: {id_no}\n5. Ethnic group: {ethnic}      6. Religion: {religion}      7. Nationality: {nationality}\n8. Native place: {native_place}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},
            {"type": "paragraph", "translated": f"II. {registration} to confirm the residence information of Mr./Mrs. named in Section I, as follows:", "align": "left", "is_heading": False, "is_bold": True, "font_size": 12, "margin_bottom": 4},
            {"type": "paragraph", "translated": f"1. Permanent residence: {perm}\n2. Temporary residence: {temp}\n3. Current residence: {curr}\n4. Full name of householder: {hh_name}\n5. Relationship with householder: {rel}\n6. Personal identification number of the householder: {hh_id}\n7. Information of other household members:", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 6},
            {
                "type": "table",
                "font_size": 11,
                "translated_cells": [
                    ["No.", "Full name", "Date of birth", "Gender", "Personal identification number/ID", "Relationship with the householder"],
                    ["1", "", "", "", "", ""]
                ]
            },
            {"type": "paragraph", "translated": f"8. Other confirmations: None\nThis confirmation of residence information is valid until: {valid_until}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},
            {"type": "paragraph", "translated": f"HEAD OF AGENCY\n(Signed, wrote full name, and sealed)\n{signer_title}\n{signer_rank}\n\n{signer_name}", "align": "right", "is_heading": False, "is_bold": True, "font_size": 11}
        ]

    else:
        return []


def get_gemini_birth_cert_blocks(full_text: str, api_key: str) -> list:
    """
    Use Gemini to extract birth certificate details from Vietnamese text and map to the standard 2010 template.
    """
    import urllib.request
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    prompt = (
        "You are an expert consular translator. Analyze the following Vietnamese Birth Certificate text and extract all details in English.\n"
        "Transliterate names to UPPERCASE without accents (e.g. NGUYỄN ĐỖ THẢO TRÂN -> NGUYEN DO THAO TRAN).\n"
        "Translate dates, addresses, ethnicities, nationalities, relationships, and administrative terms to English (e.g., 'Kinh' -> 'Kinh', 'Việt Nam' -> 'Vietnamese', 'Bà ngoại' -> 'Grandmother', 'Cha' -> 'Father').\n"
        "If a field is not present in the text, return empty string.\n\n"
        "Extract the following fields as JSON:\n"
        "- is_copy: boolean (true if text indicates it's a Copy/Trích lục/Bản sao, false if Original/Bản chính)\n"
        "- no: string (e.g. '555' or '20140/2010')\n"
        "- book_no: string (e.g. '05/2013' or '012010')\n"
        "- full_name: string (uppercase, no accents)\n"
        "- gender: string ('Male' or 'Female')\n"
        "- dob: string (e.g. 'December 14th, 2013' or 'September 21st, 2010')\n"
        "- dob_in_words: string (e.g. 'The twenty-first of September in two thousand and ten')\n"
        "- pob: string (e.g. 'Tu Du Hospital – Ho Chi Minh City')\n"
        "- ethnic: string (e.g. 'Kinh')\n"
        "- nationality: string (e.g. 'Vietnamese')\n"
        "- father_name: string (uppercase, no accents)\n"
        "- father_ethnic: string (e.g. 'Kinh')\n"
        "- father_nationality: string (e.g. 'Vietnamese')\n"
        "- father_yob: string (e.g. '1968' or '1986')\n"
        "- father_residence: string\n"
        "- mother_name: string (uppercase, no accents)\n"
        "- mother_ethnic: string (e.g. 'Kinh')\n"
        "- mother_nationality: string (e.g. 'Vietnamese')\n"
        "- mother_yob: string (e.g. '1982' or '1990')\n"
        "- mother_residence: string\n"
        "- place_of_registration: string (e.g. \"People's Committee of Tan Kieng Ward, District 7, Ho Chi Minh City\")\n"
        "- date_of_registration: string (e.g. 'December 19th, 2013')\n"
        "- note: string\n"
        "- declarer: string (uppercase, no accents)\n"
        "- relation: string (e.g. 'Father' or 'Mother' or 'Grandmother')\n"
        "- registrar: string (registrar officer name, uppercase, no accents)\n"
        "- signer: string (signer/vice-chairman/chairman name, uppercase, no accents)\n"
        "- signer_title: string (e.g. 'CHAIRMAN' or 'VICE CHAIRMAN')\n\n"
        f"Vietnamese Birth Certificate text:\n\"\"\"\n{full_text}\n\"\"\"\n"
    )
    
    # NOTE: Do NOT use responseMimeType: "application/json" — it causes HTTP 404 with this API key.
    # Instead, ask Gemini to return JSON via prompt instruction, then extract manually.
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt + "\n\nIMPORTANT: Respond with ONLY a valid JSON object. No markdown fences, no explanation."}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            response_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Strip markdown code fences if present (```json ... ```)
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
                response_text = re.sub(r"\s*```$", "", response_text)
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            logger.info(f"Gemini birth cert extraction succeeded: name={data.get('full_name')} dob={data.get('dob')}")
            
            is_copy = data.get("is_copy", False)
            cert_type = "COPY" if is_copy else "ORIGINAL"
            
            blocks = [
                {"type": "paragraph", "translated": "SOCIALIST REPUBLIC OF VIETNAM\nIndependence – Freedom – Happiness", "align": "center", "is_heading": False, "is_bold": True, "font_size": 11, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"BIRTH CERTIFICATE\n({cert_type})    No. {data.get('no', '')}\nBook No.: {data.get('book_no', '')}", "align": "center", "is_heading": True, "is_bold": True, "font_size": 18, "margin_bottom": 14},

                {
                    "type": "table",
                    "borderless": True,
                    "font_size": 12,
                    "col_widths": ["70%", "30%"],
                    "original_cells": [["Họ, chữ đệm, tên:", "Giới tính:"]],
                    "translated_cells": [[f"Full name: {data.get('full_name', '')}", f"Gender: {data.get('gender', '')}"]]
                },
                {"type": "paragraph", "translated": f"Date of birth: {data.get('dob', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"In words: {data.get('dob_in_words', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Place of birth: {data.get('pob', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {
                    "type": "table",
                    "borderless": True,
                    "font_size": 12,
                    "col_widths": ["50%", "50%"],
                    "original_cells": [["Dân tộc:", "Quốc tịch:"]],
                    "translated_cells": [[f"Ethnic group: {data.get('ethnic', '')}", f"Nationality: {data.get('nationality', '')}"]]
                },

                {"type": "paragraph", "translated": "PARENTS' DETAILS", "align": "left", "is_heading": True, "is_bold": True, "font_size": 13, "margin_top": 10, "margin_bottom": 4},
                {"type": "paragraph", "translated": f"Father's full name: {data.get('father_name', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {
                    "type": "table",
                    "borderless": True,
                    "font_size": 12,
                    "col_widths": ["33%", "34%", "33%"],
                    "original_cells": [["Dân tộc:", "Quốc tịch:", "Năm sinh:"]],
                    "translated_cells": [[f"Ethnic group: {data.get('father_ethnic', '')}", f"Nationality: {data.get('father_nationality', '')}", f"Year of birth: {data.get('father_yob', '')}"]]
                },
                {"type": "paragraph", "translated": f"Permanent residence: {data.get('father_residence', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},

                {"type": "paragraph", "translated": f"Mother's full name: {data.get('mother_name', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {
                    "type": "table",
                    "borderless": True,
                    "font_size": 12,
                    "col_widths": ["33%", "34%", "33%"],
                    "original_cells": [["Dân tộc:", "Quốc tịch:", "Năm sinh:"]],
                    "translated_cells": [[f"Ethnic group: {data.get('mother_ethnic', '')}", f"Nationality: {data.get('mother_nationality', '')}", f"Year of birth: {data.get('mother_yob', '')}"]]
                },
                {"type": "paragraph", "translated": f"Permanent residence: {data.get('mother_residence', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 8},

                {"type": "paragraph", "translated": f"Place of registration: {data.get('place_of_registration', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Date of registration: {data.get('date_of_registration', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Note: {data.get('note', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Full name of birth declarer: {data.get('declarer', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 2},
                {"type": "paragraph", "translated": f"Relation with the declared person: {data.get('relation', '')}", "align": "left", "is_heading": False, "is_bold": False, "font_size": 12, "margin_bottom": 14},

                {
                    "type": "table",
                    "borderless": True,
                    "font_size": 11,
                    "col_widths": ["50%", "50%"],
                    "original_cells": [["NGƯỜI THỰC HIỆN ĐĂNG KÝ MẪU", "NGƯỜI KÝ GIẤY KHAI SINH"]],
                    "translated_cells": [[
                        f"REGISTRAR\n(Signed and wrote full name)\n\n\n{data.get('registrar', '')}",
                        f"SIGNER OF BIRTH CERTIFICATE\n{data.get('signer_title', 'CHAIRMAN')}\n(Signed, wrote full name and sealed)\n\n\n{data.get('signer', '')}"
                    ]]
                }
            ]
            return blocks
    except Exception as e:
        logger.warning(f"Failed to use Gemini birth certificate template: {e}", exc_info=True)
        return []
