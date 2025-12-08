import hashlib
from typing import Optional

def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()

# Dummy in-memory hash store for demonstration (replace with DB lookup)
_uploaded_hashes = set()
_generated_hashes = set()

def check_hash_exists(file_hash: str) -> bool:
    """Check if file hash exists in the uploaded files DB (replace with real DB)."""
    return file_hash in _uploaded_hashes

def is_835_generated(file_hash: str) -> bool:
    """Check if file with this hash has already been processed as 835 (replace with real DB)."""
    return file_hash in _generated_hashes

def register_uploaded_hash(file_hash: str, generated: bool = False):
    _uploaded_hashes.add(file_hash)
    if generated:
        _generated_hashes.add(file_hash)

# Format validation for EOB/remittance files
def is_valid_format(content: bytes) -> bool:
    """
    Accept multiple file formats for EOB/remittance processing:
    - PDF files (start with %PDF)
    - Text files (readable as text)
    - Word documents (DOCX)
    - Images (for OCR)
    """
    # PDF files
    if content.startswith(b'%PDF'):
        return True
    
    # DOCX files (ZIP format with specific structure)
    if content.startswith(b'PK') and b'word/document.xml' in content:
        return True
    
    # Image files (PNG, JPEG, TIFF for OCR)
    if (content.startswith(b'\x89PNG') or  # PNG
        content.startswith(b'\xff\xd8\xff') or  # JPEG
        content.startswith(b'II*\x00') or  # TIFF
        content.startswith(b'MM\x00*')):  # TIFF
        return True
    
    # Text files - try to decode as UTF-8
    try:
        content.decode('utf-8')
        return True
    except UnicodeDecodeError:
        pass
    
    # If none of the above, reject
    return False
