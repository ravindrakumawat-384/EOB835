"""
Template API Usage Examples with Existing Database Schema
=========================================================

This demonstrates how to use the template API that now integrates 
with your existing PostgreSQL tables and MongoDB collection.

Database Tables Used:
- PostgreSQL: templates, template_versions
- MongoDB: template_builder_sessions

The API supports 27+ file formats and uses AI for dynamic key extraction.
"""

import json

# Example 1: Upload a template file (any supported format)
template_upload_example = {
    "endpoint": "POST /api/template/upload",
    "description": "Upload any file type for template processing",
    "supported_formats": [
        "PDF", "DOCX", "DOC", "TXT", "RTF", "ODT", "XLSX", "XLS", "CSV", 
        "PPT", "PPTX", "HTML", "XML", "JSON", "YAML", "Images (OCR)",
        "Archives (ZIP, RAR, TAR)", "and more..."
    ],
    "curl_example": """
curl -X POST "http://localhost:8000/api/template/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_document.pdf"
    """,
    "response_example": {
        "template_id": "550e8400-e29b-41d4-a716-446655440000",
        "version_id": "660e8400-e29b-41d4-a716-446655440001",
        "session_id": "770e8400-e29b-41d4-a716-446655440002",
        "filename": "sample_document.pdf",
        "file_info": {
            "type": ".pdf",
            "mime_type": "application/pdf",
            "size_bytes": 15420,
            "processing_method": "pdf_extraction",
            "expected_confidence": 85
        },
        "raw_text_length": 2341,
        "dynamic_keys_found": 8,
        "dynamic_keys": [
            "patient_name", "policy_number", "claim_amount",
            "date_of_service", "provider_name", "diagnosis_code"
        ],
        "json_data": {
            "patient_name": "John Smith",
            "policy_number": "POL123456",
            "claim_amount": "$1,250.00",
            "date_of_service": "2024-01-15",
            "provider_name": "ABC Medical Center",
            "diagnosis_code": "Z00.00",
            "extraction_confidence": 87
        },
        "ai_confidence": 87,
        "records_created": 2,
        "message": "Template processed successfully as .pdf file using pdf_extraction and saved to existing database schema"
    }
}

# Example 2: Get template by ID
template_get_example = {
    "endpoint": "GET /api/template/{template_id}",
    "description": "Retrieve complete template information",
    "curl_example": """
curl -X GET "http://localhost:8000/api/template/550e8400-e29b-41d4-a716-446655440000"
    """,
    "response_example": {
        "template_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Template-sample_document.pdf-20241201_143022",
        "type": "dynamic_extraction",
        "status": "active",
        "org_id": "9ac493f7-cc6a-4d7d-8646-affb00ed58da",
        "payer_id": None,
        "created_at": "2024-12-01T14:30:22.123456",
        "current_version": {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "version_number": 1,
            "ai_model_name": "gpt-4o-mini",
            "notes": "Generated from sample_document.pdf. Dynamic keys: patient_name, policy_number, claim_amount"
        },
        "session_data": {
            "session_id": "770e8400-e29b-41d4-a716-446655440002",
            "filename": "sample_document.pdf",
            "extracted_data": {
                "patient_name": "John Smith",
                "policy_number": "POL123456",
                "claim_amount": "$1,250.00"
            },
            "dynamic_keys": ["patient_name", "policy_number", "claim_amount"],
            "ai_confidence": 87,
            "file_metadata": {
                "size": 15420,
                "mime_type": "application/pdf",
                "processing_method": "ai_dynamic_extraction"
            },
            "status": "completed",
            "created_at": "2024-12-01T14:30:22.456789"
        }
    }
}

# Example 3: List all templates
template_list_example = {
    "endpoint": "GET /api/template/list",
    "description": "List all templates with pagination",
    "curl_example": """
curl -X GET "http://localhost:8000/api/template/list?limit=10"
    """,
    "response_example": [
        {
            "template_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Template-sample_document.pdf-20241201_143022",
            "type": "dynamic_extraction", 
            "status": "active",
            "created_at": "2024-12-01T14:30:22.123456",
            "current_version": 1,
            "ai_model": "gpt-4o-mini",
            "filename": "sample_document.pdf",
            "ai_confidence": 87,
            "dynamic_keys_count": 6,
            "file_size": 15420,
            "mime_type": "application/pdf"
        }
    ]
}

# Example 4: Get supported file types
supported_types_example = {
    "endpoint": "GET /api/template/supported-types",
    "description": "Get list of all supported file formats",
    "curl_example": """
curl -X GET "http://localhost:8000/api/template/supported-types"
    """,
    "response_example": {
        "supported_types": [
            {
                "extension": ".pdf",
                "mime_types": ["application/pdf"],
                "method": "pdf_extraction",
                "confidence": 85,
                "description": "PDF documents with text and image support"
            },
            {
                "extension": ".docx", 
                "mime_types": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
                "method": "docx_extraction",
                "confidence": 90,
                "description": "Microsoft Word 2007+ documents"
            }
        ],
        "total_supported": 27
    }
}

# Database Schema Information
database_schema_info = {
    "postgresql_tables": {
        "templates": {
            "purpose": "Main template records",
            "key_fields": ["id", "name", "type", "status", "org_id", "payer_id", "current_version_id"],
            "description": "Stores basic template information and links to current version"
        },
        "template_versions": {
            "purpose": "Template version history", 
            "key_fields": ["id", "template_id", "version_number", "status", "ai_generated", "ai_model_name"],
            "description": "Tracks different versions of templates with AI model information"
        }
    },
    "mongodb_collections": {
        "template_builder_sessions": {
            "purpose": "Detailed template processing data",
            "key_fields": ["template_id", "version_id", "filename", "raw_text", "extracted_data", "dynamic_keys"],
            "description": "Stores the actual extracted text, JSON data, and processing metadata"
        }
    }
}

# Integration Benefits
integration_benefits = {
    "advantages": [
        "Uses your existing database tables - no new schema needed",
        "Supports 27+ file formats with intelligent type detection",
        "AI-powered dynamic key extraction (no predefined templates)",
        "Comprehensive error handling and validation",
        "MongoDB for flexible session data storage",
        "PostgreSQL for structured template and version management",
        "Automatic confidence scoring for AI extractions",
        "File size and content validation",
        "Detailed logging and debugging information"
    ],
    "use_cases": [
        "Process any document format for template creation",
        "Extract structured data from unstructured documents",
        "Build dynamic templates without predefined schemas", 
        "Version control for template modifications",
        "Audit trail of template processing sessions",
        "Multi-format document ingestion pipeline"
    ]
}

if __name__ == "__main__":
    print("Template API Integration Examples")
    print("=" * 50)
    print()
    
    print("📁 Supported File Formats:")
    for fmt in template_upload_example["supported_formats"]:
        print(f"  • {fmt}")
    print()
    
    print("🏗️ Database Integration:")
    print("  • PostgreSQL: templates, template_versions")
    print("  • MongoDB: template_builder_sessions")
    print()
    
    print("🔧 Key Features:")
    for benefit in integration_benefits["advantages"][:5]:
        print(f"  • {benefit}")
    print()
    
    print("📋 Example Upload Response:")
    response = template_upload_example["response_example"]
    print(f"  Template ID: {response['template_id']}")
    print(f"  Dynamic Keys: {len(response['dynamic_keys'])} found")
    print(f"  AI Confidence: {response['ai_confidence']}%")
    print(f"  File Type: {response['file_info']['type']}")
    print()
    
    print("For complete examples, see the dictionaries above! 🚀")