from typing import Dict, Any, Tuple
import json
import re
from ..utils.logger import get_logger

logger = get_logger(__name__)

def validate_extracted_text(text: str, filename: str) -> Tuple[bool, str]:
    """
    Validate if the extracted text contains meaningful content.
    
    Args:
        text: Extracted text from file
        filename: Original filename for logging
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not text or text.strip() == "":
        return False, "No text could be extracted from the file"
    
    # Check if text is too short (likely corrupted or empty file)
    if len(text.strip()) < 50:
        return False, "Extracted text is too short, file may be corrupted"
    
    # Check for common corruption indicators
    corruption_indicators = [
        "unable to extract text",
        "file corrupted",
        "invalid file format",
        "extraction failed"
    ]
    
    text_lower = text.lower()
    for indicator in corruption_indicators:
        if indicator in text_lower:
            return False, f"File corruption detected: {indicator}"
    
    # Check if text contains mostly garbage characters (corrupted binary data)
    printable_chars = sum(1 for c in text if c.isprintable())
    total_chars = len(text)
    
    if total_chars > 0 and (printable_chars / total_chars) < 0.7:
        return False, "Text contains too many non-printable characters, file may be corrupted"
    
    # Check for minimum expected content patterns for EOB/remittance files
    eob_patterns = [
        r'\b\d{2}[/-]\d{2}[/-]\d{4}\b',  # Date patterns
        r'\$\d+\.?\d*',  # Dollar amounts
        r'\b[A-Z]{2,}\b',  # Insurance company codes/names
        r'\bpat(ient)?\b|member\b|claim\b',  # Medical terms
        r'\bpay(er|ment)\b|check\b|eob\b',  # Payment terms
        r'\b\d{10,}\b',  # Policy/claim numbers
    ]
    
    pattern_matches = 0
    for pattern in eob_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            pattern_matches += 1
    
    # Require at least 3 patterns to be considered readable EOB content
    if pattern_matches < 3:
        return False, f"File content is unreadable - only {pattern_matches} of {len(eob_patterns)} expected patterns found"
    
    return True, "Text validation passed"

def validate_ai_extraction_result(ai_result: Dict[str, Any], filename: str) -> Tuple[bool, str]:
    """
    Validate the AI extraction result for completeness and correctness.
    
    Args:
        ai_result: Result from AI extraction
        filename: Original filename for logging
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not ai_result:
        return False, "AI extraction returned empty result"
    
    # Check for error indicators in the result
    if "error" in ai_result:
        return False, f"AI extraction error: {ai_result['error']}"
    
    # Check confidence level - if too low, file is likely unreadable
    confidence = ai_result.get("confidence", 0)
    if confidence < 40:  # Low confidence threshold indicates unreadable content
        return False, f"File appears unreadable - AI extraction confidence too low: {confidence}%"
    
    # Validate basic structure
    required_keys = ["payer_info", "payment", "claims"]
    for key in required_keys:
        if key not in ai_result:
            return False, f"Missing required key in AI result: {key}"
    
    # Validate payer info
    payer_info = ai_result.get("payer_info", {})
    if not payer_info.get("name") or payer_info.get("name") == "Unknown Payer":
        logger.warning(f"No payer information extracted from {filename}")
    
    # Check if we have at least some claims or payment information
    claims = ai_result.get("claims", [])
    payment = ai_result.get("payment", {})
    
    has_claims = len(claims) > 0
    has_payment = payment.get("payment_amount", 0) > 0
    
    if not has_claims and not has_payment:
        return False, "No meaningful claims or payment information extracted"
    
    return True, "AI extraction validation passed"

def validate_json_conversion(data: Any, filename: str) -> Tuple[bool, str]:
    """
    Validate that data can be properly converted to JSON.
    
    Args:
        data: Data to be converted to JSON
        filename: Original filename for logging
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Try to serialize to JSON
        json_str = json.dumps(data, default=str, ensure_ascii=False)
        
        # Try to parse it back
        parsed_data = json.loads(json_str)
        
        # Check if the parsed data is meaningful
        if not parsed_data:
            return False, "JSON conversion resulted in empty data"
        
        return True, "JSON conversion validation passed"
        
    except (TypeError, ValueError, json.JSONEncodeError) as e:
        return False, f"JSON conversion failed: {str(e)}"

def comprehensive_file_validation(
    text: str, 
    ai_result: Dict[str, Any], 
    filename: str
) -> Tuple[bool, str]:
    """
    Run comprehensive validation on file processing results.
    
    Args:
        text: Extracted text
        ai_result: AI extraction result
        filename: Original filename
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Step 1: Validate extracted text
    text_valid, text_error = validate_extracted_text(text, filename)
    if not text_valid:
        return False, f"Text validation failed: {text_error}"
    
    # Step 2: Validate AI extraction
    ai_valid, ai_error = validate_ai_extraction_result(ai_result, filename)
    if not ai_valid:
        return False, f"AI extraction validation failed: {ai_error}"
    
    # Step 3: Validate JSON conversion
    json_valid, json_error = validate_json_conversion(ai_result, filename)
    if not json_valid:
        return False, f"JSON conversion validation failed: {json_error}"
    
    return True, "All validations passed"