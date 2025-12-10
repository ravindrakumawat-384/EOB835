from datetime import datetime
from typing import Optional
import uuid
import psycopg2

# Example connection (replace with your config)
def get_pg_conn():
    return psycopg2.connect(
        dbname="eob_db",
        user="aman0622",
        password="password123",
        host="127.0.0.1",
        port="5432"
    )

def insert_upload_file(
    org_id: str,
    batch_id: Optional[str],
    filename: str,
    s3_path: str,
    mime_type: str,
    file_size: int,
    file_hash: str,
    upload_source: str,
    uploaded_by: str,
    status: str = "uploaded"
) -> str:
    conn = get_pg_conn()
    cur = conn.cursor()
    
    # Check if a file with this hash already exists
    cur.execute("SELECT id FROM upload_files WHERE hash = %s", (file_hash,))
    existing_file = cur.fetchone()
    
    if existing_file:
        file_id = existing_file[0]
        print(f"📋 File with hash {file_hash} already exists with ID: {file_id}")
        # Update existing record
        cur.execute(
            """
            UPDATE upload_files SET
                original_filename = %s,
                storage_path = %s,
                uploaded_at = %s,
                processing_status = %s
            WHERE id = %s
            """,
            (filename, s3_path, datetime.utcnow(), status, file_id)
        )
    else:
        # Generate new UUID for file ID
        file_id = str(uuid.uuid4())
        print(f"📋 Creating new file record with ID: {file_id}, hash: {file_hash}")
        cur.execute(
            """
            INSERT INTO upload_files (
                id, org_id, batch_id, original_filename, storage_path, mime_type, file_size, hash, upload_source, uploaded_by, uploaded_at, processing_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (file_id, org_id, batch_id, filename, s3_path, mime_type, file_size, file_hash, upload_source, uploaded_by, datetime.utcnow(), status)
        )
    
    conn.commit()
    cur.close()
    conn.close()
    return file_id

def update_file_status(file_id: str, status: str, error_message: Optional[str] = None) -> bool:
    """
    Update the processing status and error message of an uploaded file.
    
    Args:
        file_id: The file ID to update
        status: New processing status (e.g., 'unreadable', 'processed', 'failed')
        error_message: Optional error message to store in processing_error_message field
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    conn = None
    cur = None
    try:
        print(f"🔄 Attempting to update file status: file_id={file_id}, status={status}")
        conn = get_pg_conn()
        cur = conn.cursor()
        
        # First check if the file exists
        cur.execute("SELECT id, processing_status FROM upload_files WHERE id = %s", (file_id,))
        existing_record = cur.fetchone()
        
        if not existing_record:
            print(f"❌ File with ID {file_id} not found in database")
            return False
        
        print(f"📋 Found existing record: id={existing_record[0]}, current_status={existing_record[1]}")
        
        # Update the record
        if error_message:
            print(f"📝 Updating with error message: {error_message[:100]}...")
            cur.execute(
                """
                UPDATE upload_files 
                SET processing_status = %s, processing_error_message = %s, updated_at = %s
                WHERE id = %s
                """,
                (status, error_message, datetime.utcnow(), file_id)
            )
        else:
            print(f"📝 Updating status only (no error message)")
            cur.execute(
                """
                UPDATE upload_files 
                SET processing_status = %s, updated_at = %s
                WHERE id = %s
                """,
                (status, datetime.utcnow(), file_id)
            )
        
        conn.commit()
        rows_affected = cur.rowcount
        
        if rows_affected > 0:
            print(f"✅ Successfully updated {rows_affected} row(s)")
        else:
            print(f"⚠️ No rows were affected by the update")
        
        return rows_affected > 0
        
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL error updating file status: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"❌ General error updating file status: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def mark_processing_failed(file_id: str, error_details: str, failure_stage: str = "processing") -> bool:
    """
    Mark a file as processing failed with detailed error information.
    
    Args:
        file_id: The file ID to update
        error_details: Detailed error message describing what went wrong
        failure_stage: Stage where processing failed (e.g., 'text_extraction', 'ai_processing', 'validation')
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    # Combine failure stage and error details for comprehensive error message
    full_error_message = f"[{failure_stage.upper()}] {error_details}"
    
    # Use the enhanced update_file_status function
    print(f"🚨 Marking file as processing failed: {file_id}")
    print(f"📝 Error: {full_error_message}")
    
    return update_file_status(file_id, "failed", full_error_message)


def set_detected_template_version(file_id: str, template_version_id: str = None, status: str = None, ai_template_confidence: float = None, ai_match_low_confidence: Optional[bool] = None) -> bool:
    """
    Update the upload_files record to set the detected_template_version_id and optionally update processing_status.

    Args:
        file_id: upload_files.id
        template_version_id: template_versions.id to set (or None to clear)
        status: optional processing status to set (e.g., 'needs_template' or 'processed')

    Returns:
        bool: True if update succeeded
    """
    conn = None
    cur = None
    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        # Ensure file exists
        cur.execute("SELECT id FROM upload_files WHERE id = %s", (file_id,))
        if not cur.fetchone():
            return False

        # Build update dynamically to optionally include ai_template_confidence
        updates = []
        params = []
        if template_version_id is not None:
            updates.append('detected_template_version_id = %s')
            params.append(template_version_id)
        if status is not None:
            updates.append('processing_status = %s')
            params.append(status)
        if ai_template_confidence is not None:
            updates.append('ai_template_confidence = %s')
            params.append(ai_template_confidence)
        if ai_match_low_confidence is not None:
            updates.append('ai_match_low_confidence = %s')
            params.append(ai_match_low_confidence)

        if not updates:
            return False

        updates.append('updated_at = %s')
        params.append(datetime.utcnow())
        params.append(file_id)

        sql = f"UPDATE upload_files SET {', '.join(updates)} WHERE id = %s"
        cur.execute(sql, tuple(params))

        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error updating detected_template_version: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def check_database_schema() -> dict:
    """
    Check if the required database columns exist and return schema information.
    
    Returns:
        dict: Schema information and missing columns
    """
    conn = None
    cur = None
    try:
        print("🔍 Checking database schema...")
        conn = get_pg_conn()
        cur = conn.cursor()
        
        # Check if upload_files table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'upload_files'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            return {"error": "upload_files table does not exist"}
        
        # Check required columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'upload_files' 
            ORDER BY column_name;
        """)
        columns = cur.fetchall()
        
        required_columns = ['processing_status', 'processing_error_message', 'updated_at']
        existing_columns = [col[0] for col in columns]
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        # Get sample data
        cur.execute("SELECT id, processing_status, processing_error_message FROM upload_files LIMIT 3")
        sample_data = cur.fetchall()
        
        return {
            "table_exists": table_exists,
            "all_columns": columns,
            "existing_columns": existing_columns,
            "missing_columns": missing_columns,
            "sample_data": sample_data
        }
        
    except Exception as e:
        return {"error": f"Database check failed: {e}"}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def test_database_update(test_file_id: str = "test_debug_file") -> bool:
    """
    Test database update functionality with a test file ID.
    
    Args:
        test_file_id: Test file ID to use for testing
        
    Returns:
        bool: True if test was successful
    """
    print(f"🧪 Testing database update with file ID: {test_file_id}")
    
    # First, check if we can connect to database
    try:
        conn = get_pg_conn()
        print("✅ Database connection successful")
        conn.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Check schema
    schema_info = check_database_schema()
    if "error" in schema_info:
        print(f"❌ Schema check failed: {schema_info['error']}")
        return False
    
    print(f"📋 Database schema check:")
    print(f"   - Table exists: {schema_info['table_exists']}")
    print(f"   - Missing columns: {schema_info['missing_columns']}")
    print(f"   - Sample data count: {len(schema_info['sample_data'])}")
    
    # Try to update a test record
    success = update_file_status(test_file_id, "test_status", "Test error message")
    print(f"📊 Update test result: {success}")
    
    return success











