import mimetypes
import magic
from typing import Dict, Any, Tuple, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Supported file types for template processing
SUPPORTED_MIME_TYPES = {
    # Text files
    'text/plain': 'TXT',
    'text/csv': 'CSV', 
    'text/tab-separated-values': 'TSV',
    
    # PDF files
    'application/pdf': 'PDF',
    
    # Microsoft Office
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'application/msword': 'DOC',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/vnd.ms-excel': 'XLS',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
    'application/vnd.ms-powerpoint': 'PPT',
    
    # Images (with OCR capability)
    'image/jpeg': 'JPG',
    'image/png': 'PNG',
    'image/gif': 'GIF', 
    'image/bmp': 'BMP',
    'image/tiff': 'TIFF',
    'image/webp': 'WEBP',
    
    # Archives (will extract and process contents)
    'application/zip': 'ZIP',
    'application/x-rar-compressed': 'RAR',
    'application/x-7z-compressed': '7Z',
    
    # Other document formats
    'application/rtf': 'RTF',
    'application/json': 'JSON',
    'application/xml': 'XML',
    'text/xml': 'XML',
    'application/vnd.oasis.opendocument.text': 'ODT',
    'application/vnd.oasis.opendocument.spreadsheet': 'ODS',
    
    # Email formats
    'message/rfc822': 'EML',
    'application/vnd.ms-outlook': 'MSG'
}

def detect_file_type(content: bytes, filename: str) -> Tuple[str, str, bool]:
    """
    Detect file type using multiple methods for accurate identification.
    
    Returns:
        Tuple[mime_type, file_extension, is_supported]
    """
    try:
        # Method 1: Use python-magic for content-based detection
        try:
            mime_type = magic.from_buffer(content, mime=True)
        except:
            mime_type = None
        
        # Method 2: Use mimetypes based on filename
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(filename)
        
        # Method 3: Fallback based on file extension
        if not mime_type:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            extension_map = {
                'txt': 'text/plain',
                'pdf': 'application/pdf', 
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'doc': 'application/msword',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'xls': 'application/vnd.ms-excel',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
                'tiff': 'image/tiff',
                'csv': 'text/csv',
                'json': 'application/json',
                'xml': 'application/xml'
            }
            mime_type = extension_map.get(ext, 'application/octet-stream')
        
        # Determine file extension
        file_ext = SUPPORTED_MIME_TYPES.get(mime_type, 'UNKNOWN')
        is_supported = mime_type in SUPPORTED_MIME_TYPES
        
        logger.info(f"File type detection: {filename} -> {mime_type} ({file_ext}) - Supported: {is_supported}")
        
        return mime_type, file_ext, is_supported
        
    except Exception as e:
        logger.error(f"Error detecting file type for {filename}: {e}")
        return 'application/octet-stream', 'UNKNOWN', False

def validate_file_content(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validate file content for processing.
    
    Returns:
        Tuple[is_valid, error_message]
    """
    try:
        # Check file size (max 100MB)
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
        if len(content) > MAX_FILE_SIZE:
            return False, f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})"
        
        # Check for empty files
        if len(content) == 0:
            return False, "Empty file uploaded"
        
        # Check for NUL bytes (binary corruption)
        if b'\x00' in content:
            # Count NUL bytes
            nul_count = content.count(b'\x00')
            total_bytes = len(content)
            nul_percentage = (nul_count / total_bytes) * 100
            
            if nul_percentage > 50:
                return False, f"File appears corrupted: {nul_percentage:.1f}% NUL bytes"
            else:
                logger.warning(f"File {filename} contains {nul_count} NUL bytes ({nul_percentage:.1f}%) - will attempt to clean")
        
        # Check for minimum content
        if len(content) < 10:
            return False, "File too small to contain meaningful data"
        
        return True, "File validation passed"
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"

def get_processing_strategy(mime_type: str, file_ext: str) -> Dict[str, Any]:
    """
    Determine the best processing strategy based on file type.
    """
    strategies = {
        'text/plain': {'method': 'direct_text', 'confidence': 95, 'ocr_needed': False},
        'text/csv': {'method': 'structured_text', 'confidence': 90, 'ocr_needed': False},
        'application/json': {'method': 'structured_data', 'confidence': 95, 'ocr_needed': False},
        'application/pdf': {'method': 'pdf_extraction', 'confidence': 85, 'ocr_needed': True},
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
            'method': 'office_extraction', 'confidence': 90, 'ocr_needed': False
        },
        'application/msword': {'method': 'office_extraction', 'confidence': 85, 'ocr_needed': False},
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
            'method': 'spreadsheet_extraction', 'confidence': 90, 'ocr_needed': False
        },
        'application/vnd.ms-excel': {'method': 'spreadsheet_extraction', 'confidence': 85, 'ocr_needed': False},
        'image/jpeg': {'method': 'ocr_extraction', 'confidence': 70, 'ocr_needed': True},
        'image/png': {'method': 'ocr_extraction', 'confidence': 75, 'ocr_needed': True},
        'image/gif': {'method': 'ocr_extraction', 'confidence': 65, 'ocr_needed': True},
        'image/bmp': {'method': 'ocr_extraction', 'confidence': 70, 'ocr_needed': True},
        'image/tiff': {'method': 'ocr_extraction', 'confidence': 80, 'ocr_needed': True}
    }
    
    return strategies.get(mime_type, {
        'method': 'fallback_extraction', 
        'confidence': 50, 
        'ocr_needed': True
    })

def clean_extracted_text(text: str, processing_method: str) -> str:
    """
    Clean and normalize extracted text based on processing method.
    """
    if not text:
        return ""
    
    # Remove NUL bytes and other control characters
    text = text.replace('\x00', '')
    
    # Method-specific cleaning
    if processing_method == 'structured_text':
        # Preserve structure for CSV/TSV - minimal cleaning
        text = text.replace('\x00', '')  # Only remove NUL bytes
        lines = text.split('\n')
        text = '\n'.join(line.strip() for line in lines if line.strip())
    
    elif processing_method == 'ocr_extraction':
        # OCR often produces extra spaces and line breaks
        text = ' '.join(text.split())
        text = text.replace('  ', ' ').replace('\n\n\n', '\n\n')
    
    elif processing_method == 'pdf_extraction':
        # PDFs sometimes have weird spacing
        text = ' '.join(text.split())
        text = text.replace('  ', ' ')
    
    else:
        # Default cleaning - remove excessive whitespace
        text = ' '.join(text.split())
    
    # Ensure UTF-8 compatibility
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    return text.strip()