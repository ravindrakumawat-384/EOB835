"""
Database migration script to add error_message and updated_at columns to upload_files table.
Run this if the columns don't exist.
"""

import psycopg2

def get_pg_conn():
    return psycopg2.connect(
        dbname="eob_db",
        user="aman0622",
        password="password1234",
        host="127.0.0.1",
        port="5432"
    )

def add_missing_columns():
    """Add error_message and updated_at columns if they don't exist"""
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Check if error_message column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'upload_files' AND column_name = 'error_message'
        """)
        
        if not cur.fetchone():
            print("Adding error_message column...")
            cur.execute("""
                ALTER TABLE upload_files 
                ADD COLUMN error_message TEXT
            """)
        else:
            print("error_message column already exists")
        
        # Check if updated_at column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'upload_files' AND column_name = 'updated_at'
        """)
        
        if not cur.fetchone():
            print("Adding updated_at column...")
            cur.execute("""
                ALTER TABLE upload_files 
                ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
        else:
            print("updated_at column already exists")
        
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_missing_columns()