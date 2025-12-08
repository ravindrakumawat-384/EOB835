import uuid
from datetime import datetime
from typing import Optional
import psycopg2

# Example connection (replace with your config)
def get_pg_conn():
    return psycopg2.connect(
        dbname="eob_db",
        user="aman0622",
        password="password1234",
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
    file_id = str(uuid.uuid4())
    now = datetime.utcnow()
    cur.execute(
        """
        INSERT INTO upload_files (
            id, org_id, batch_id, original_filename, storage_path, mime_type, file_size, hash, upload_source, uploaded_by, uploaded_at, processing_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (file_id, org_id, batch_id, filename, s3_path, mime_type, file_size, file_hash, upload_source, uploaded_by, now, status)
    )
    conn.commit()
    cur.close()
    conn.close()
    return file_id











