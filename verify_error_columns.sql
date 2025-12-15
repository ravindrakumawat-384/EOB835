-- SQL script to ensure the upload_files table has the required columns for error handling

-- Check if processing_error_message column exists, add if missing
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='upload_files' AND column_name='processing_error_message') THEN
        ALTER TABLE upload_files ADD COLUMN processing_error_message TEXT;
        RAISE NOTICE 'Added processing_error_message column';
    ELSE
        RAISE NOTICE 'processing_error_message column already exists';
    END IF;
END $$;

-- Check if updated_at column exists, add if missing
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='upload_files' AND column_name='updated_at') THEN
        ALTER TABLE upload_files ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        RAISE NOTICE 'Added updated_at column';
    ELSE
        RAISE NOTICE 'updated_at column already exists';
    END IF;
END $$;

-- Verify the table structure
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'upload_files' 
  AND column_name IN ('processing_status', 'processing_error_message', 'updated_at')
ORDER BY column_name;

-- Show sample data to verify current status values
SELECT id, original_filename, processing_status, processing_error_message, updated_at 
FROM upload_files 
ORDER BY uploaded_at DESC 
LIMIT 5;