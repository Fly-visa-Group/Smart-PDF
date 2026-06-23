from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io, json, os, logging, traceback

from services.pdf_merger import merge_pdfs
from services.pdf_compressor import compress_pdf
from services.pdf_page_merger import merge_pages_by_manifest
from services.pdf_to_word import convert_pdf_bytes_to_docx_bytes, parse_pdf_to_blocks, build_docx_from_blocks
from services.translation import extract_structured, build_docx_from_translation
from services.translation.html_extractor import pdf_to_html_pages
from services.translation.html_translator import translate_scanned_to_html

# Upload limits: unlimited (no cap applied)

import urllib.parse
def make_safe_filename_header(filename: str) -> str:
    quoted = urllib.parse.quote(filename or "document")
    return f"attachment; filename*=UTF-8''{quoted}"

app = FastAPI(title="SmartPDF API", description="Backend for SmartPDF")
logger = logging.getLogger(__name__)

@app.get("/")
async def root():
    return {
        "service": "SmartPDF API",
        "status": "ok",
        "health": "/health",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

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

@app.post("/api/translate-pdf/html")
async def api_translate_pdf_html(
    file: UploadFile = File(...),
):
    """
    HTML-based translation pipeline:
    - Text PDFs: PDF → structured HTML → Gemini translates preserving all tags/styles
    - Scanned/image PDFs: render page → PNG → Gemini Vision (reads layout visually, no OCR errors)
    Paired pages (e.g. tax slip page1+page2) are sent as a combined image to Gemini.
    """
    import base64
    import fitz  # PyMuPDF
    import re as _re
    from concurrent.futures import ThreadPoolExecutor
    from services.translation.html_translator import translate_html_page, translate_pdf_page_to_html

    def _extract_pages_as_pdf_b64(pdf_bytes: bytes, *page_nums: int) -> str:
        """Extract one or more pages from a PDF and return as base64 PDF bytes."""
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        out = fitz.open()
        for page_num in page_nums:
            out.insert_pdf(src, from_page=page_num - 1, to_page=page_num - 1)
        return base64.b64encode(out.tobytes()).decode()

    try:
        content = await file.read()
        pages = pdf_to_html_pages(content)

        # For pairing: use PyMuPDF text extraction to gauge if page 2 has real content
        def _page_text_len(page_num: int) -> int:
            doc = fitz.open(stream=content, filetype="pdf")
            return len(doc[page_num - 1].get_text().strip())

        # Group consecutive scanned pages in pairs when page 2 has real content (>200 chars)
        page_groups: list[dict] = []
        i = 0
        while i < len(pages):
            p = pages[i]
            next_p = pages[i + 1] if i + 1 < len(pages) else None
            if p.get("is_scanned") and next_p and next_p.get("is_scanned") and _page_text_len(next_p["page_num"]) > 200:
                page_groups.append({"pages": [p, next_p], "paired": True})
                i += 2
            else:
                page_groups.append({"pages": [p], "paired": False})
                i += 1

        def _translate_group(group):
            page_list = group["pages"]
            if group["paired"]:
                # Send both pages as a single 2-page PDF → one Gemini call
                b64 = _extract_pages_as_pdf_b64(content, page_list[0]["page_num"], page_list[1]["page_num"])
                translated_html = translate_pdf_page_to_html(b64)
                if not translated_html:
                    # fallback: translate individually
                    h1 = translate_pdf_page_to_html(_extract_pages_as_pdf_b64(content, page_list[0]["page_num"]))
                    h2 = translate_pdf_page_to_html(_extract_pages_as_pdf_b64(content, page_list[1]["page_num"]))
                    translated_html = h1 + h2
                group_pages = [p["page_num"] for p in page_list]
                lead = {**page_list[0], "translated_html": translated_html,
                        "group_id": page_list[0]["page_num"], "is_group_lead": True,
                        "group_pages": group_pages}
                follower = {**page_list[1], "translated_html": "",
                            "group_id": page_list[0]["page_num"], "is_group_lead": False,
                            "group_pages": group_pages}
                return [lead, follower]
            else:
                p = page_list[0]
                if p.get("is_scanned"):
                    b64 = _extract_pages_as_pdf_b64(content, p["page_num"])
                    translated_html = translate_pdf_page_to_html(b64)
                    if not translated_html:
                        translated_html = "<p style='color:#e53e3e;text-align:center;'>Translation failed for this page.</p>"
                else:
                    translated_html = translate_html_page(p["html"], is_scanned=False)
                return [{**p, "translated_html": translated_html,
                         "group_id": p["page_num"], "is_group_lead": True,
                         "group_pages": [p["page_num"]]}]

        # Translate groups in parallel (max 4 concurrent Gemini calls)
        with ThreadPoolExecutor(max_workers=4) as ex:
            group_results = list(ex.map(_translate_group, page_groups))
        translated_pages = [page for group in group_results for page in group]

        return {
            "original_filename": file.filename or "document.pdf",
            "total_pages": len(translated_pages),
            "pages": translated_pages,
        }
    except Exception as e:
        logger.error("/api/translate-pdf/html failed")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"translate_html_failed: {str(e)}")


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


# ── Split PDF ─────────────────────────────────────────────────────────────────
@app.post("/api/split")
async def api_split(
    file: UploadFile = File(...),
    ranges: str = Form(...),  # e.g. "1-3,4,5-7" or "1,2,3"
):
    """
    Split a PDF by page ranges. ranges = comma-separated items like "1-3,4,5-7".
    Returns a ZIP containing one PDF per range.
    """
    try:
        import fitz, zipfile
        content = await file.read()
        doc = fitz.open(stream=content, filetype="pdf")
        total = doc.page_count

        # Parse ranges
        segments = []
        for part in ranges.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                start, end = int(a.strip()) - 1, int(b.strip()) - 1
            else:
                start = end = int(part) - 1
            start = max(0, min(start, total - 1))
            end   = max(0, min(end,   total - 1))
            segments.append((start, end))

        if not segments:
            raise HTTPException(status_code=400, detail="Không có range hợp lệ")

        base = (file.filename or "document").rsplit(".", 1)[0]
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (s, e) in enumerate(segments, 1):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=s, to_page=e)
                pdf_bytes = new_doc.tobytes()
                new_doc.close()
                label = f"trang_{s+1}" if s == e else f"trang_{s+1}-{e+1}"
                zf.writestr(f"{base}_{label}.pdf", pdf_bytes)
        doc.close()
        zip_buf.seek(0)
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={"Content-Disposition": make_safe_filename_header(f"{base}_split.zip")},
        )
    except HTTPException:
        raise
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
