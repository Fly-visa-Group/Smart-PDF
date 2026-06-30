import io
import fitz  # PyMuPDF


def merge_pdfs(files: list[bytes], rotations: list[int] | None = None) -> bytes:
    """Merge full PDFs in order, optionally applying per-file rotation (degrees)."""
    result = fitz.open()
    for i, f_bytes in enumerate(files):
        src = fitz.open(stream=f_bytes, filetype="pdf")
        result.insert_pdf(src)
        rot = (rotations[i] if rotations and i < len(rotations) else 0) % 360
        if rot:
            # Apply rotation to the pages just inserted
            page_offset = result.page_count - len(src)
            for p_idx in range(len(src)):
                page = result[page_offset + p_idx]
                page.set_rotation((page.rotation + rot) % 360)
        src.close()

    out = io.BytesIO()
    result.save(out, garbage=4, deflate=True)
    result.close()
    return out.getvalue()


def merge_pages_by_manifest(files_bytes: list[bytes], manifest: list[dict]) -> bytes:
    """
    Merge specific pages in a custom order.
    manifest: [{ "file_index": 0, "page": 1, "rotation": 0 }, ...]
    page is 1-indexed; rotation is optional extra degrees to apply.
    """
    docs = [fitz.open(stream=b, filetype="pdf") for b in files_bytes]
    result = fitz.open()

    for entry in manifest:
        file_idx = entry["file_index"]
        page_num = entry["page"] - 1  # 0-indexed
        extra_rot = entry.get("rotation", 0) % 360
        doc = docs[file_idx]
        if 0 <= page_num < len(doc):
            result.insert_pdf(doc, from_page=page_num, to_page=page_num)
            if extra_rot:
                inserted = result[-1]
                inserted.set_rotation((inserted.rotation + extra_rot) % 360)

    out = io.BytesIO()
    result.save(out, garbage=4, deflate=True)
    result.close()
    for doc in docs:
        doc.close()

    return out.getvalue()
