import io
from typing import Optional
import mimetypes

# PDF
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
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

def extract_text_from_file(content: bytes, filename: str, mime_type: Optional[str] = None) -> str:
    """
    Extract text from PDF, DOCX, TXT, or image files. Returns extracted text or a placeholder if not supported.
    """
    if not mime_type:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # PDF
    if mime_type == "application/pdf":
        # Prefer pdfplumber if available
        if pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                if text.strip():
                    return text
            except Exception as e:
                return f"[pdfplumber extraction failed: {e}]"
        # Fallback to PyPDF2
        if PyPDF2:
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                if text.strip():
                    return text
            except Exception as e:
                return f"[PyPDF2 extraction failed: {e}]"
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
            text = pytesseract.image_to_string(img)
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
