import io
from typing import Optional
import mimetypes
# from paddleocr import PaddleOCR

# PDF
try:
    from pdf2image import convert_from_bytes  # Renders PDF pages to PIL Images for OCR
except ImportError:
    convert_from_bytes = None
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
# DOCX
try:
    import docx
except ImportError:
    docx = None
# Images
try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
except ImportError:
    pytesseract = None
    Image = None
    ImageFilter = None
    ImageEnhance = None

# ocr_model = PaddleOCR(use_angle_cls=True, lang='en')

def extract_text_from_file(content: bytes, filename: str, mime_type: Optional[str] = None) -> str:
    """
    Extract text from PDF, DOCX, TXT, or image files.
    Preference order:
    - PDFs: OCR with Tesseract (via pdf2image) first, then fall back to text extractors.
    - Images: OCR with Tesseract.
    - DOCX/TXT: Native text extraction.
    Returns extracted text or a diagnostic placeholder if not supported.
    """
    print("Starting text extraction...")
    if not mime_type:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # PDF
    if mime_type == "application/pdf":
        # Collect from multiple strategies and merge for maximal coverage
        sources = []

        # 1) pdfplumber: extract text and tables (with improved spacing)
        if pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    page_texts = []
                    table_texts = []
                    for page in pdf.pages:
                        # Text with spacing tolerance
                        txt = page.extract_text(layout=True) or ""
                        if txt:
                            page_texts.append(txt)
                        # Tables (flatten cells)
                        try:
                            tables = page.extract_tables() or []
                            for t in tables:
                                rows = []
                                for row in t:
                                    if not row:
                                        continue
                                    rows.append(" ".join((c or "").strip() for c in row))
                                if rows:
                                    table_texts.append("\n".join(rows))
                        except Exception:
                            # Table extraction can fail depending on page structure; skip silently
                            pass
                    text = "\n".join(page_texts + table_texts)
                    if text.strip():
                        sources.append(text)
            except Exception as e:
                sources.append(f"[pdfplumber extraction failed: {e}]")

        # 2) PyPDF2 fallback
        # if PyPDF2:
        #     try:
        #         reader = PyPDF2.PdfReader(io.BytesIO(content))
        #         text = "\n".join(page.extract_text() or "" for page in reader.pages)
        #         if text.strip():
        #             sources.append(text)
        #     except Exception as e:
        #         sources.append(f"[PyPDF2 extraction failed: {e}]")

        # 3) OCR with Tesseract (preferred for scanned PDFs)
        # if convert_from_bytes and pytesseract and Image:
        #     try:
        #         pages = convert_from_bytes(content, dpi=300)
        #         ocr_text_chunks = []
        #         for img in pages:
        #             # Preprocess to improve OCR
        #             try:
        #                 if ImageEnhance:
        #                     img = ImageEnhance.Contrast(img).enhance(1.6)
        #                 if ImageFilter:
        #                     img = img.filter(ImageFilter.SHARPEN)
        #                 img = img.convert("L")
        #             except Exception:
        #                 # If preprocessing fails, continue with original image
        #                 pass
        #             custom_config = "--oem 1 --psm 6"
        #             ocr_text_chunks.append(pytesseract.image_to_string(img, config=custom_config))
        #         ocr_text = "\n".join(ocr_text_chunks)
        #         if ocr_text.strip():
        #             sources.append(ocr_text)
        #     except Exception:
        #         # Continue to merging if OCR fails
        #         pass

        # 4) Merge all sources and return
        combined = "\n".join(s for s in sources if s)
        if combined.strip():
            return combined

        # If we reach here for PDFs and still have nothing but OCR deps missing, emit a helpful hint
        if not (convert_from_bytes and pytesseract and Image):
            missing = []
            if not convert_from_bytes:
                missing.append("pdf2image")
            if not pytesseract:
                missing.append("pytesseract")
            if not Image:
                missing.append("Pillow")
            return f"[PDF OCR/text extraction unavailable; missing: {', '.join(missing)}]"
    # DOCX
    if mime_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword") and docx:
        try:
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
            if text.strip():
                return text
        except Exception as e:
            return f"[DOCX extraction failed: {e}]"
    # TXT
    if mime_type.startswith("text"):
        try:
            text = content.decode(errors="replace")
            if text.strip():
                return text
        except Exception as e:
            return f"[Text decode failed: {e}]"
    # Image
    if mime_type.startswith("image") and pytesseract and Image:
        try:
            img = Image.open(io.BytesIO(content))
            try:
                # Similar preprocessing to aid OCR on images
                if ImageEnhance:
                    img = ImageEnhance.Contrast(img).enhance(1.6)
                if ImageFilter:
                    img = img.filter(ImageFilter.SHARPEN)
                img = img.convert("L")
            except Exception:
                pass
            custom_config = "--oem 1 --psm 6"
            text = pytesseract.image_to_string(img, config=custom_config)
            if text.strip():
                return text
        except Exception as e:
            return f"[Image OCR failed: {e}]"
    # Fallback: always try to decode as text
    try:
        text = content.decode(errors="replace")
        if text.strip():
            return text
    except Exception as e:
        return f"[Fallback decode failed: {e}]"
    return f"[Unsupported or empty file type: {mime_type}]"
