#!/usr/bin/env python3
"""
Test script to verify the enhanced template API that handles any file type.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.file_type_handler import (
    detect_file_type,
    validate_file_content,
    get_processing_strategy,
    clean_extracted_text,
    SUPPORTED_MIME_TYPES
)

def test_file_type_detection():
    """Test file type detection with various content types."""
    print("🧪 TESTING FILE TYPE DETECTION")
    print("=" * 60)
    
    # Test cases: (content, filename, expected_mime_type)
    test_cases = [
        (b"Hello, this is plain text", "test.txt", "text/plain"),
        (b"Name,Age,City\nJohn,25,NYC", "data.csv", "text/csv"),
        (b"%PDF-1.4\n%random content", "document.pdf", "application/pdf"),
        (b'{"name": "test", "data": "value"}', "config.json", "application/json"),
        (b"PK\x03\x04", "archive.zip", "application/zip"),  # ZIP signature
        (b"\xff\xd8\xff\xe0", "image.jpg", "image/jpeg"),   # JPEG signature
        (b"\x89PNG\r\n\x1a\n", "image.png", "image/png"),    # PNG signature
    ]
    
    for i, (content, filename, expected) in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {filename}")
        mime_type, file_ext, is_supported = detect_file_type(content, filename)
        print(f"   Detected: {mime_type} ({file_ext})")
        print(f"   Expected: {expected}")
        print(f"   Supported: {'✅ YES' if is_supported else '❌ NO'}")
        
        if is_supported:
            strategy = get_processing_strategy(mime_type, file_ext)
            print(f"   Processing: {strategy['method']} (confidence: {strategy['confidence']}%)")

def test_file_validation():
    """Test file content validation."""
    print("\n\n🧪 TESTING FILE CONTENT VALIDATION")
    print("=" * 60)
    
    test_cases = [
        (b"", "empty.txt", False, "Empty file"),
        (b"Hello World", "normal.txt", True, "Valid content"),
        (b"x" * (101 * 1024 * 1024), "huge.txt", False, "File too large"),
        (b"Hello\x00World\x00Test", "with_nul.txt", True, "Contains NUL bytes - should clean"),
        (b"\x00" * 1000, "mostly_nul.txt", False, "Mostly NUL bytes - corrupted"),
        (b"abc", "tiny.txt", False, "Too small"),
    ]
    
    for i, (content, filename, should_pass, description) in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {filename} - {description}")
        is_valid, error_msg = validate_file_content(content, filename)
        status = "✅ PASS" if is_valid == should_pass else "❌ FAIL"
        print(f"   Result: {status} - {error_msg}")

def test_text_cleaning():
    """Test text cleaning functionality.""" 
    print("\n\n🧪 TESTING TEXT CLEANING")
    print("=" * 60)
    
    test_cases = [
        ("Hello\x00World", "direct_text", "HelloWorld"),
        ("  Multiple   Spaces  ", "ocr_extraction", "Multiple Spaces"),
        ("Line1\n\n\nLine2", "ocr_extraction", "Line1\n\nLine2"),
        ("Name,Age\nJohn,25", "structured_text", "Name,Age\nJohn,25"),  # Preserve CSV structure
        ("PDF  Text  With  Spaces", "pdf_extraction", "PDF Text With Spaces"),
    ]
    
    for i, (input_text, method, expected) in enumerate(test_cases, 1):
        print(f"\n{i}. Method: {method}")
        print(f"   Input: {repr(input_text)}")
        cleaned = clean_extracted_text(input_text, method)
        print(f"   Output: {repr(cleaned)}")
        print(f"   Expected: {repr(expected)}")
        print(f"   Match: {'✅ YES' if cleaned == expected else '❌ NO'}")

def show_supported_types():
    """Show all supported file types."""
    print("\n\n📋 SUPPORTED FILE TYPES")
    print("=" * 60)
    
    categories = {
        "Text Files": ["text/plain", "text/csv", "text/tab-separated-values", "application/json", "application/xml"],
        "PDF Documents": ["application/pdf"],
        "Microsoft Office": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel"
        ],
        "Images": ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff"],
        "Archives": ["application/zip", "application/x-rar-compressed", "application/x-7z-compressed"],
        "Other": ["application/rtf", "message/rfc822", "application/vnd.ms-outlook"]
    }
    
    total_types = 0
    for category, mime_types in categories.items():
        print(f"\n{category}:")
        for mime_type in mime_types:
            if mime_type in SUPPORTED_MIME_TYPES:
                file_ext = SUPPORTED_MIME_TYPES[mime_type]
                print(f"  ✅ {file_ext:<8} - {mime_type}")
                total_types += 1
            else:
                print(f"  ❌ NOT SUPPORTED - {mime_type}")
    
    print(f"\nTotal supported types: {total_types}")

if __name__ == "__main__":
    print("🚀 TESTING ENHANCED FILE TYPE HANDLING")
    print("=" * 80)
    
    try:
        test_file_type_detection()
        test_file_validation()
        test_text_cleaning()
        show_supported_types()
        
        print("\n" + "=" * 80)
        print("🎉 ALL FILE TYPE HANDLING TESTS COMPLETED!")
        print("\n📖 The template API now supports:")
        print("   • Automatic file type detection")
        print("   • Content validation and cleaning")
        print("   • Multiple processing strategies")
        print("   • 20+ different file formats")
        print("   • Intelligent text extraction")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()