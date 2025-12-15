#!/usr/bin/env python3
"""
Test script to verify MD5 file ID generation
"""

import hashlib
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.file_validation import calculate_file_hash

def test_md5_file_id():
    """Test MD5 hash generation for file content"""
    
    # Test with sample content
    test_content = b"This is a test file content for MD5 hash generation"
    
    # Calculate MD5 hash
    file_hash = calculate_file_hash(test_content)
    
    # Verify it's MD5 (32 characters, hexadecimal)
    print(f"Generated file hash: {file_hash}")
    print(f"Hash length: {len(file_hash)} characters")
    print(f"Is hexadecimal: {all(c in '0123456789abcdef' for c in file_hash.lower())}")
    
    # Verify it matches manual MD5 calculation
    expected_hash = hashlib.md5(test_content).hexdigest()
    print(f"Expected hash: {expected_hash}")
    print(f"Hashes match: {file_hash == expected_hash}")
    
    # Test with different content
    test_content2 = b"Different content should produce different hash"
    file_hash2 = calculate_file_hash(test_content2)
    print(f"\nSecond file hash: {file_hash2}")
    print(f"Hashes are different: {file_hash != file_hash2}")

if __name__ == "__main__":
    test_md5_file_id()