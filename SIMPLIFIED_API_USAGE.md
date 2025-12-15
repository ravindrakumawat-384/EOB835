# Simplified 835 Generation API

## ✅ Your Exact Request Format

```bash
curl -X POST "http://localhost:8001/generate-835/" \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "03d3e06b-2dbc-4eb5-8055-c8e28d10d266"
  }'
```

## 📋 What Happens

1. **Input**: Only `claim_id` is required
2. **Defaults**: System uses default values for optional fields
3. **Processing**: 
   - Fetches claim data using the claim_id
   - Generates 835 EDI format file
   - Names file with claim number: `{CLAIM_NUMBER}_835_{TIMESTAMP}.txt`
   - Uploads to S3: `s3://bucket/exports/835/YYYY/MM/DD/{filename}`
   - Stores record in database with claim reference

## 🎯 Response Example

```json
{
  "success": true,
  "export_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "export_reference": "EXP835-EXTRACTED-001-20251207_182030",
  "file_name": "EXTRACTED-001_835_20251207_182030.txt",
  "s3_path": "s3://eob-dev-bucket/exports/835/2025/12/07/EXTRACTED-001_835_20251207_182030.txt",
  "file_size_kb": 2.5,
  "claim_number": "EXTRACTED-001",
  "total_amount": 150.0,
  "service_lines_count": 1,
  "generated_at": "2025-12-07T18:20:30.123456",
  "status": "generated",
  "message": "835 file generated and uploaded to S3"
}
```

## 🔧 API Configuration

```python
class Generate835Request(BaseModel):
    claim_id: str                                           # ✅ REQUIRED
    org_id: str = "00000000-0000-0000-0000-000000000000"    # ✅ Optional (default provided)
    generated_by: Optional[str] = None                      # ✅ Optional (can be None)
```

## 📁 File Naming & Storage

- **File Name**: `{CLAIM_NUMBER}_835_{TIMESTAMP}.txt`
- **Local**: `/tmp/{filename}` (temporary)
- **S3**: `s3://eob-dev-bucket/exports/835/YYYY/MM/DD/{filename}`
- **Export Reference**: `EXP835-{CLAIM_NUMBER}-{TIMESTAMP}`

## 🗄️ Database Records

### exports_835 table
- Links to the generated file in S3
- Contains export reference and metadata

### export_items table  
- Links export to specific claim_id
- Enables querying by claim

## 🚀 Start Server

```bash
cd /home/ditsdev370/Project/EOB835
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 🧪 Test Your Request

```bash
# Your simplified format
curl -X POST "http://localhost:8001/generate-835/" \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "03d3e06b-2dbc-4eb5-8055-c8e28d10d266"
  }'
```

## ✅ Status: READY TO USE

Your exact request format is **already supported** and will:
- ✅ Generate 835 file with claim data
- ✅ Name file with claim number  
- ✅ Store in S3 with organized structure
- ✅ Create database record with claim reference
- ✅ Return all file and reference information