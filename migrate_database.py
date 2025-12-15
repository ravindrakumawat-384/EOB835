#!/usr/bin/env python3
"""
Database migration script to add missing columns for error handling.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pg_upload_files import get_pg_conn

def add_missing_columns():
    """Add missing columns to the upload_files table."""
    print("🔧 Adding missing columns to upload_files table...")
    
    conn = None
    cur = None
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        
        # Add updated_at column if it doesn't exist
        print("📝 Adding updated_at column...")
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='upload_files' AND column_name='updated_at'
                ) THEN
                    ALTER TABLE upload_files ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                    RAISE NOTICE 'Added updated_at column';
                ELSE
                    RAISE NOTICE 'updated_at column already exists';
                END IF;
            END $$;
        """)
        
        # Update existing records to have updated_at value
        print("📝 Updating existing records with updated_at values...")
        cur.execute("""
            UPDATE upload_files 
            SET updated_at = uploaded_at 
            WHERE updated_at IS NULL;
        """)
        
        conn.commit()
        print("✅ Database migration completed successfully!")
        
        # Verify the changes
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'upload_files' 
              AND column_name IN ('processing_status', 'processing_error_message', 'updated_at')
            ORDER BY column_name;
        """)
        
        columns = cur.fetchall()
        print("\n📋 Verified columns:")
        for col_name, col_type in columns:
            print(f"   - {col_name}: {col_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🚀 Starting database migration...")
    success = add_missing_columns()
    if success:
        print("\n🎉 Migration completed successfully!")
    else:
        print("\n💥 Migration failed!")
        sys.exit(1)