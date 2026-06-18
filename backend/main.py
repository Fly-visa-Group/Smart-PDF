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
from services.translation import extract_structured, translate_document, build_docx_from_translation, detect_document_type, translate_with_templates

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
    except Exception as e:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
