# 835 Form Generation with Claim ID Reference & S3 Storage

## ✅ Current Implementation Overview

The system is **already configured** to generate 835 forms with claim ID reference and store files in S3 with claim number-based naming.

## 🎯 Key Features Implemented

### 1. **Claim ID Reference System**
- Input: `claim_id` parameter in API request
- Database lookup: Fetches claim data using claim_id
- Reference tracking: Links export to specific claim via `export_items` table

### 2. **Claim Number-Based File Naming**
```
Format: {CLAIM_NUMBER}_835_{TIMESTAMP}.txt
Example: EXTRACTED-001_835_20251207_180315.txt
```

### 3. **S3 Storage Structure**
```
s3://eob-dev-bucket/exports/835/{YYYY}/{MM}/{DD}/{CLAIM_NUMBER}_835_{TIMESTAMP}.txt

Example:
s3://eob-dev-bucket/exports/835/2025/12/07/EXTRACTED-001_835_20251207_180315.txt
```

### 4. **Export Reference System**
```
Format: EXP835-{CLAIM_NUMBER}-{TIMESTAMP}
Example: EXP835-EXTRACTED-001-20251207_180315
```

## 📋 API Usage

### Generate 835 Form
```bash
POST /generate-835/
Content-Type: application/json

{
  "claim_id": "03d3e06b-2dbc-4eb5-8055-c8e28d10d266",
  "org_id": "123e4567-e89b-12d3-a456-426614174000",
  "generated_by": "456e7890-e89b-12d3-a456-426614174001"
}
```

### Response
```json
{
  "success": true,
  "export_id": "uuid",
  "export_reference": "EXP835-EXTRACTED-001-20251207_180315",
  "file_name": "EXTRACTED-001_835_20251207_180315.txt",
  "s3_path": "s3://eob-dev-bucket/exports/835/2025/12/07/EXTRACTED-001_835_20251207_180315.txt",
  "claim_number": "EXTRACTED-001",
  "total_amount": 150.0,
  "service_lines_count": 1,
  "generated_at": "2025-12-07T18:03:15",
  "status": "generated",
  "message": "835 file generated and uploaded to S3"
}
```

## 🗄️ Database Schema

### exports_835 Table
```sql
CREATE TABLE exports_835 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  export_reference TEXT NOT NULL,           -- EXP835-{CLAIM_NUMBER}-{TIMESTAMP}
  storage_path TEXT NOT NULL,               -- S3 path
  status TEXT NOT NULL CHECK (status IN ('pending','generated','downloaded','failed')),
  generated_by UUID NULL,
  generated_at TIMESTAMPTZ NULL,
  error_message TEXT NULL
);
```

### export_items Table
```sql
CREATE TABLE export_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  export_id UUID NOT NULL,                 -- Links to exports_835.id
  payment_id UUID NULL,                     -- Links to payments table
  claim_id UUID NULL,                       -- Links to claims table (KEY REFERENCE)
  FOREIGN KEY (export_id) REFERENCES exports_835(id)
);
```

## 🔍 Additional Endpoints

### List Exports
```bash
GET /generate-835/exports?org_id={org_id}&limit=20
```

### Get Specific Export
```bash
GET /generate-835/exports/{export_id}
```

### Download Export (Presigned URL)
```bash
POST /generate-835/exports/{export_id}/download
```

### Debug Claim Data
```bash
GET /generate-835/debug/claim/{claim_id}
```

## 📁 File Organization

### Local Temporary Storage
```
/tmp/EXTRACTED-001_835_20251207_180315.txt
```

### S3 Permanent Storage
```
eob-dev-bucket/
└── exports/
    └── 835/
        └── 2025/
            └── 12/
                └── 07/
                    ├── EXTRACTED-001_835_20251207_180315.txt
                    ├── CLAIM-123_835_20251207_180420.txt
                    └── BC-789_835_20251207_180530.txt
```

## 🔗 Data Flow

1. **Input**: `claim_id` → API request
2. **Lookup**: Database fetch claim data by claim_id
3. **Generate**: 835 EDI content with actual claim data
4. **Name**: File with claim number: `{CLAIM_NUMBER}_835_{TIMESTAMP}.txt`
5. **Store**: Upload to S3 in organized date structure
6. **Record**: Save export metadata in `exports_835` table
7. **Link**: Create relationship in `export_items` table with claim_id
8. **Return**: Export ID, S3 path, and download info

## 🎯 Benefits

✅ **Claim-Centric**: Every file is tied to a specific claim_id
✅ **Easy Identification**: File name starts with claim number
✅ **Organized Storage**: Date-based S3 folder structure
✅ **Audit Trail**: Complete tracking with timestamps
✅ **Scalable**: UUID-based relationships for large datasets
✅ **Secure**: Presigned URLs for controlled access
✅ **Searchable**: Query by claim_id, export_id, or date range

## 🧪 Testing

Run the test suite:
```bash
python test_835_claim_reference.py
```

This will verify:
- Claim ID reference works
- File naming includes claim number  
- S3 storage is properly organized
- Database relationships are correct
- Download functionality works

## 🔧 Status

**✅ FULLY IMPLEMENTED** - The system already meets all requirements:
- Uses claim_id as reference ✅
- Stores files in S3 with claim number ✅  
- Proper database relationships ✅
- Export reference includes claim info ✅
- Organized file structure ✅