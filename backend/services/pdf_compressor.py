import io
import fitz  # PyMuPDF

def compress_pdf(file_bytes: bytes, level: str = "medium") -> bytes:
    """
    Compress a PDF using PyMuPDF image re-rendering.
    Levels:
      - 'medium': Good quality, significantly smaller size. (100 DPI, 70% JPEG quality)
      - 'extreme': Lower quality, very small size. (65 DPI, 35% JPEG quality)
      - 'ultra': Absolute smallest size. (36 DPI, 20% JPEG quality)
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    new_doc = fitz.open()

    if level == "ultra":
        zoom = 0.5      # ~36 DPI equivalent
        quality = 20    # very low quality
    elif level == "extreme":
        zoom = 0.9      # ~65 DPI equivalent
        quality = 35     # low quality
    else: # medium
        zoom = 1.4      # ~100 DPI equivalent
        quality = 70    # good quality

    for page in doc:
        # Render page to image at desired resolution
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        
        # Save as compressed JPEG bytes
        img_bytes = pix.tobytes("jpeg", jpg_quality=quality)
        
        # Insert into a new PDF page with the original dimensions
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=img_bytes)
        
    out_io = io.BytesIO()
    # Save with garbage collection and deflation enabled
    new_doc.save(out_io, garbage=4, deflate=True)
    new_doc.close()
    doc.close()
    
    return out_io.getvalue()
