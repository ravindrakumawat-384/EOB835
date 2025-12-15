# Template JSON Data to Payer Table Integration

## Summary

Successfully implemented automatic payer data extraction from template JSON and storage in the PostgreSQL payers table.

## Implementation Details

### Database Schema
```sql
CREATE TABLE payers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  name TEXT NOT NULL,
  payer_code TEXT NULL,
  default_template_id UUID NULL,
  ai_detection_metadata JSONB NULL,
  created_by UUID NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Data Sources

**MongoDB Collections:**
- `template_builder_sessions` - Contains template JSON data with extracted information

**PostgreSQL Tables:**
- `payers` - Target table for storing payer information

### Extraction Logic

The system extracts payer data using multiple strategies:

1. **Direct JSON Field Matching**
   - `payer_name`, `payer`, `insurance_company`, `insurer`, `carrier`
   - `insurance_carrier`, `plan_name`, `health_plan`, `insurance_plan`
   - `company_name`, `organization_name`, `insurance_name`

2. **Nested Structure Search**
   - Searches within `claims[]` array for payer information
   - Searches within `payments[]` array for payer information  
   - Searches within `raw_key_value_pairs` object

3. **Filename Pattern Recognition**
   ```
   bcbs → Blue Cross Blue Shield
   uhc/united → UnitedHealthcare
   aetna → Aetna
   cigna → Cigna
   humana → Humana
   anthem → Anthem
   kaiser → Kaiser Permanente
   fallon → Fallon Health
   regence → Regence BlueCross BlueShield
   ```

### Key Functions

#### `extract_and_save_payer_data(json_data, org_id, filename=None)`
- Extracts payer information from template JSON
- Creates new payer records in PostgreSQL
- Handles duplicate detection
- Returns payer_id if successful

#### `process_existing_templates_for_payer_data(org_id)`
- Bulk processes all existing template sessions
- Extracts payer data from historical templates
- Returns processing statistics

### AI Detection Metadata

Each extracted payer includes metadata:
```json
{
  "source": "template_json_extraction",
  "confidence": 85,
  "detected_fields": {
    "payer_name": "UnitedHealthcare",
    "payer_code": "UHC001"
  },
  "extraction_timestamp": "2025-12-08T15:44:40.383077",
  "template_fields_used": ["payer_name", "payer_code"]
}
```

### Integration Points

1. **Automatic Processing**: When new templates are processed via `save_template_data()`, payer extraction happens automatically

2. **Bulk Processing**: Use `process_existing_templates_for_payer_data()` to process historical templates

3. **Manual Testing**: Use `test_payer_extraction.py` to test and verify functionality

## Results

✅ **Successfully Tested With:**
- Template files: `bcbs 6732.pdf`, `fallon 1894084.pdf`
- Extracted payers: Blue Cross Blue Shield, Fallon Health
- Proper PostgreSQL storage with AI metadata
- Duplicate detection working correctly

## Usage

### Automatic Processing
Payer extraction happens automatically when processing new templates through the existing template upload API.

### Manual Bulk Processing
```python
from app.services.template_db_service import process_existing_templates_for_payer_data

# Process all existing templates
results = process_existing_templates_for_payer_data("org-id-here")
print(f"Created {results['payers_created']} new payers")
```

### Testing
```bash
python3 test_payer_extraction.py
```

This implementation provides intelligent, automated payer data extraction from template JSON while maintaining data integrity and providing comprehensive audit trails through AI detection metadata.