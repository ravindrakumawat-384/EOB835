-- Migration: add ai_match_low_confidence to upload_files
-- Run this in your Postgres DB (e.g., psql -d eob_db -f thisfile.sql)

ALTER TABLE upload_files
ADD COLUMN IF NOT EXISTS ai_match_low_confidence boolean DEFAULT false;

-- Optional: create an index if you plan to query on this column
CREATE INDEX IF NOT EXISTS idx_upload_files_ai_match_low_confidence ON upload_files (ai_match_low_confidence);
