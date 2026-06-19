from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io, json, os

from services.pdf_merger import merge_pdfs
from services.pdf_compressor import compress_pdf
from services.pdf_translator import translate_text
from services.pdf_reader import read_pdf_metadata
from services.pdf_page_merger import merge_pages_by_manifest
from services.pdf_to_word import convert_pdf_bytes_to_docx_bytes, parse_pdf_to_blocks, build_docx_from_blocks
from services.translation import extract_structured, translate_document, build_docx_from_translation
from services.translation.html_extractor import pdf_to_html_pages
from services.translation.html_translator import translate_scanned_to_html

# Upload limits: unlimited (no cap applied)

import urllib.parse
def make_safe_filename_header(filename: str) -> str:
    quoted = urllib.parse.quote(filename or "document")
    return f"attachment; filename*=UTF-8''{quoted}"

app = FastAPI(title="SmartPDF API", description="Backend for SmartPDF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/merge")
async def api_merge(files: list[UploadFile] = File(...)):
    try:
        file_contents = [await f.read() for f in files]
        merged_pdf = merge_pdfs(file_contents)
        return StreamingResponse(
            io.BytesIO(merged_pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/merge-pages")
async def api_merge_pages(
    files: list[UploadFile] = File(...),
    manifest: str = Form(...),
):
    """Merge specific pages in a custom order.
    manifest JSON: [{ "file_index": 0, "page": 1 }, ...]
    """
    try:
        manifest_data = json.loads(manifest)
        file_contents = [await f.read() for f in files]
        merged_pdf = merge_pages_by_manifest(file_contents, manifest_data)
        return StreamingResponse(
            io.BytesIO(merged_pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compress")
async def api_compress(
    file: UploadFile = File(...),
    level: str = Form("medium")
):
    try:
        # Validate file type - only PDF allowed
        filename = file.filename or ""
        if not filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail=f"File không hợp lệ: '{filename}'. Công cụ Nén PDF chỉ hỗ trợ file PDF (.pdf)."
            )
        
        content = await file.read()
        compressed = compress_pdf(content, level=level)
        return StreamingResponse(
            io.BytesIO(compressed),
            media_type="application/pdf",
            headers={"Content-Disposition": make_safe_filename_header(f"compressed_{file.filename}")}
        )
    except Exception:
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=tb)

@app.post("/api/read")
async def api_read(file: UploadFile = File(...)):
    try:
        content = await file.read()
        info = read_pdf_metadata(content)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/translate")
async def api_translate(text: str = Form(...)):
    try:
        translated = translate_text(text)
        return {"translated_text": translated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/translate-pdf")
async def api_translate_pdf(
    file: UploadFile = File(...),
    doc_type: str = Form("auto")
):
    """
    Translate a Vietnamese PDF to English (bilingual JSON response).
    Uses DeepL if DEEPL_API_KEY env var is set, else falls back to Google Translate.
    Returns structured bilingual data for frontend side-by-side rendering.
    """
    try:
        content = await file.read()
        deepl_key = os.environ.get("DEEPL_API_KEY")

        # 1. Extract structured text with layout info
        structured = extract_structured(content)

        # 2. Translate all blocks (routes to template if matching specialized doc types)
        result = translate_document(structured, deepl_api_key=deepl_key, manual_doc_type=doc_type)

        # Include original filename so frontend can suggest output name
        result["original_filename"] = file.filename or "document.pdf"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/translate-pdf/html")
async def api_translate_pdf_html(
    file: UploadFile = File(...),
):
    """
    HTML-based translation pipeline:
    - Text PDFs: PDF → structured HTML → Gemini translates preserving all tags/styles
    - Scanned/image PDFs: OCR text → Gemini reconstructs + translates → clean HTML
    """
    try:
        content = await file.read()
        pages = pdf_to_html_pages(content)

        # For scanned pages we need structured OCR text — extract once
        has_scanned = any(p.get("is_scanned") for p in pages)
        structured_by_page: dict = {}
        if has_scanned:
            structured = extract_structured(content)
            for ps in structured.get("pages", []):
                raw_text = "\n".join(
                    b.get("text", "") for b in ps.get("blocks", [])
                    if b.get("type") != "table" and b.get("text", "").strip()
                )
                structured_by_page[ps["page_num"]] = raw_text

        import re as _re
        from concurrent.futures import ThreadPoolExecutor
        from services.translation.html_translator import translate_html_page

        def _translate_one(page):
            if page.get("is_scanned"):
                raw_text = structured_by_page.get(page["page_num"], "")
                if not raw_text.strip():
                    raw_text = _re.sub(r"<[^>]+>", " ", page["html"]).strip()
                translated_html = translate_scanned_to_html(raw_text)
            else:
                translated_html = translate_html_page(page["html"], is_scanned=False)
            return {**page, "translated_html": translated_html}

        # Translate all pages in parallel (up to 4 at once)
        with ThreadPoolExecutor(max_workers=4) as ex:
            translated_pages = list(ex.map(_translate_one, pages))

        return {
            "original_filename": file.filename or "document.pdf",
            "total_pages": len(translated_pages),
            "pages": translated_pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/translate-pdf/download-docx")
async def api_translate_pdf_docx(
    file: UploadFile = File(...),
    doc_type: str = Form("auto")
):
    """
    Translate a Vietnamese PDF to English and return a formatted DOCX document directly.
    """
    try:
        content = await file.read()
        deepl_key = os.environ.get("DEEPL_API_KEY")

        # 1. Extract structured text with layout info (including tables)
        structured = extract_structured(content)

        # 2. Translate all blocks (routes to template if matching specialized doc types)
        result = translate_document(structured, deepl_api_key=deepl_key, manual_doc_type=doc_type)

        # 3. Build DOCX bytes from the result blocks
        docx_bytes = build_docx_from_translation(result)

        # Format output filename: <original>_translated.docx
        base_name = (file.filename or "document").rsplit(".", 1)[0]
        out_filename = f"{base_name}_translated.docx"

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": make_safe_filename_header(out_filename)}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class DownloadEditedRequest(BaseModel):
    result: dict


@app.post("/api/translate-pdf/download-pdf")
async def api_translate_pdf_download_pdf(request: DownloadEditedRequest):
    """Convert translated HTML pages to a formatted PDF using WeasyPrint."""
    try:
        import weasyprint

        result = request.result
        pages = result.get("pages", [])

        # Build full HTML document from all pages
        page_htmls = []
        for page in pages:
            html = page.get("translated_html", "")
            page_htmls.append(
                f'<div class="doc-page">{html}</div>'
            )

        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  @page {{ margin: 2cm 2.2cm; size: A4; }}
  body {{ font-family: "Times New Roman", Times, serif; font-size: 11pt; color: #1a202c; }}
  .doc-page {{ page-break-after: always; }}
  .doc-page:last-child {{ page-break-after: avoid; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ vertical-align: top; }}
  p {{ margin: 2px 0; line-height: 1.4; }}
</style>
</head>
<body>{"".join(page_htmls)}</body>
</html>"""

        pdf_bytes = weasyprint.HTML(string=full_html).write_pdf()

        base_name = (result.get("original_filename") or "document").rsplit(".", 1)[0]
        out_filename = f"{base_name}_translated.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": make_safe_filename_header(out_filename)},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/translate-pdf/download-edited-docx")
async def api_translate_pdf_download_edited_docx(request: DownloadEditedRequest):
    try:
        result = request.result
        docx_bytes = build_docx_from_translation(result)
        out_filename = "translated_edited.docx"
        if "original_filename" in result:
            base_name = result["original_filename"].rsplit(".", 1)[0]
            out_filename = f"{base_name}_translated.docx"

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": make_safe_filename_header(out_filename)}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/api/pdf-to-word")
async def api_pdf_to_word(file: UploadFile = File(...)):
    try:
        content = await file.read()
        converted_docx = convert_pdf_bytes_to_docx_bytes(content)
        base_name = (file.filename or "converted").rsplit(".", 1)[0]
        return StreamingResponse(
            io.BytesIO(converted_docx),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": make_safe_filename_header(f"{base_name}.docx")}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf-to-word/parse")
async def api_pdf_to_word_parse(file: UploadFile = File(...)):
    try:
        content = await file.read()
        parsed_blocks = parse_pdf_to_blocks(content)
        parsed_blocks["original_filename"] = file.filename or "document.pdf"
        return parsed_blocks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DownloadEditedWordRequest(BaseModel):
    blocks_data: dict
    original_filename: str = "document.pdf"


@app.post("/api/pdf-to-word/download-edited")
async def api_pdf_to_word_download_edited(request: DownloadEditedWordRequest):
    try:
        docx_bytes = build_docx_from_blocks(request.blocks_data)
        base_name = request.original_filename.rsplit(".", 1)[0]
        out_filename = f"{base_name}.docx"
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": make_safe_filename_header(out_filename)}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PDF → Images ──────────────────────────────────────────────────────────────
@app.post("/api/pdf-to-images")
async def api_pdf_to_images(
    file: UploadFile = File(...),
    dpi: int = Form(150),
    fmt: str = Form("png"),   # "png" or "jpg"
):
    try:
        content = await file.read()
        doc = __import__("fitz").open(stream=content, filetype="pdf")
        zoom = dpi / 72
        mat = __import__("fitz").Matrix(zoom, zoom)
        images = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png" if fmt == "png" else "jpeg")
            import base64
            images.append({
                "page": i + 1,
                "data": base64.b64encode(img_bytes).decode(),
                "mime": "image/png" if fmt == "png" else "image/jpeg",
                "ext": fmt,
            })
        doc.close()
        return {"total": len(images), "images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Images / PDF → PDF ────────────────────────────────────────────────────────
@app.post("/api/images-to-pdf")
async def api_images_to_pdf(files: list[UploadFile] = File(...)):
    try:
        import fitz
        doc = fitz.open()
        for f in files:
            data = await f.read()
            img_doc = fitz.open(stream=data, filetype="image")
            rect = img_doc[0].rect
            page = doc.new_page(width=rect.width, height=rect.height)
            page.show_pdf_page(rect, img_doc, 0)
            img_doc.close()
        pdf_bytes = doc.tobytes()
        doc.close()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=converted.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Word → PDF ────────────────────────────────────────────────────────────────
@app.post("/api/word-to-pdf")
async def api_word_to_pdf(file: UploadFile = File(...)):
    try:
        import tempfile, os
        from docx2pdf import convert
        content = await file.read()
        suffix = ".docx" if (file.filename or "").endswith(".docx") else ".doc"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
            tmp_in.write(content)
            tmp_in_path = tmp_in.name
        tmp_out_path = tmp_in_path.replace(suffix, ".pdf")
        try:
            convert(tmp_in_path, tmp_out_path)
            with open(tmp_out_path, "rb") as f:
                pdf_bytes = f.read()
        finally:
            os.unlink(tmp_in_path)
            if os.path.exists(tmp_out_path):
                os.unlink(tmp_out_path)
        base = (file.filename or "document").rsplit(".", 1)[0]
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": make_safe_filename_header(f"{base}.pdf")},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Image format conversion (JPG ↔ PNG, etc.) ─────────────────────────────────
@app.post("/api/convert-image")
async def api_convert_image(
    file: UploadFile = File(...),
    to_format: str = Form("png"),   # "png", "jpg", "webp"
):
    try:
        from PIL import Image as PILImage
        content = await file.read()
        img = PILImage.open(io.BytesIO(content)).convert("RGB")
        out = io.BytesIO()
        fmt_map = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}
        pil_fmt = fmt_map.get(to_format.lower(), "PNG")
        img.save(out, format=pil_fmt, quality=95)
        out.seek(0)
        mime = "image/png" if pil_fmt == "PNG" else ("image/webp" if pil_fmt == "WEBP" else "image/jpeg")
        base = (file.filename or "image").rsplit(".", 1)[0]
        ext = "png" if pil_fmt == "PNG" else ("webp" if pil_fmt == "WEBP" else "jpg")
        return StreamingResponse(
            out, media_type=mime,
            headers={"Content-Disposition": make_safe_filename_header(f"{base}.{ext}")},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
