#!/usr/bin/env python3

"""
Initialize the new 835 export tables in the database
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pg_upload_files import get_pg_conn

def create_export_tables():
    """Create the new export tables"""
    
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        print("🗄️ Creating exports_835 table...")
        
        # Create exports_835 table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exports_835 (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id UUID NOT NULL,
                export_reference TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending','generated','downloaded','failed')),
                generated_by UUID NULL,
                generated_at TIMESTAMPTZ NULL,
                error_message TEXT NULL
            )
        """)
        
        print("🗄️ Creating export_items table...")
        
        # Create export_items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS export_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                export_id UUID NOT NULL,
                payment_id UUID NULL,
                claim_id UUID NULL,
                FOREIGN KEY (export_id) REFERENCES exports_835(id)
            )
        """)
        
        print("🔍 Creating indexes...")
        
        # Create indexes for performance
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exports_835_org_id ON exports_835(org_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exports_835_status ON exports_835(status)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exports_835_generated_at ON exports_835(generated_at)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_items_export_id ON export_items(export_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_items_claim_id ON export_items(claim_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_items_payment_id ON export_items(payment_id)
        """)
        
        conn.commit()
        print("✅ Successfully created export tables and indexes!")
        
        # Show table info
        print("\n📊 Table Information:")
        
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name IN ('exports_835', 'export_items')
            ORDER BY table_name, ordinal_position
        """)
        
        current_table = None
        for row in cur.fetchall():
            table_name, column_name, data_type, is_nullable, column_default = row
            
            if table_name != current_table:
                print(f"\n📋 {table_name}:")
                current_table = table_name
            
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            default = f" DEFAULT {column_default}" if column_default else ""
            print(f"   {column_name}: {data_type} {nullable}{default}")
        
        # Show indexes
        print("\n🔍 Indexes:")
        cur.execute("""
            SELECT schemaname, tablename, indexname, indexdef
            FROM pg_indexes 
            WHERE tablename IN ('exports_835', 'export_items')
            AND schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        for row in cur.fetchall():
            schema, table, index_name, index_def = row
            print(f"   {table}.{index_name}")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()
    
    return True

def check_existing_tables():
    """Check if the old table exists and show migration path"""
    
    conn = get_pg_conn()
    cur = conn.cursor()
    
    try:
        # Check for old table
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'edi_835_files'
            )
        """)
        
        old_table_exists = cur.fetchone()[0]
        
        if old_table_exists:
            print("⚠️ Found old 'edi_835_files' table")
            
            # Count records in old table
            cur.execute("SELECT COUNT(*) FROM edi_835_files")
            old_count = cur.fetchone()[0]
            
            print(f"   Records in old table: {old_count}")
            
            if old_count > 0:
                print("📋 Migration needed! Old data found.")
                print("   Consider migrating data from 'edi_835_files' to new tables")
                print("   Old table structure stored EDI content directly")
                print("   New structure stores files in S3 with references")
        
        # Check new tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('exports_835', 'export_items')
        """)
        
        new_tables = [row[0] for row in cur.fetchall()]
        
        print(f"\n📊 New tables status:")
        for table in ['exports_835', 'export_items']:
            status = "✅ EXISTS" if table in new_tables else "❌ MISSING"
            print(f"   {table}: {status}")
        
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
    finally:
        cur.close()
        conn.close()

def main():
    """Main function"""
    
    print("🚀 Initializing 835 Export Tables")
    print("=" * 40)
    
    # Check existing tables
    check_existing_tables()
    
    print("\n" + "=" * 40)
    
    # Create new tables
    success = create_export_tables()
    
    if success:
        print("\n✅ Database initialization completed!")
        print("\n📋 Next Steps:")
        print("   1. Update your application to use the new endpoints")
        print("   2. Test the /generate-835/ endpoint with claim IDs")
        print("   3. Verify S3 file uploads are working")
        print("   4. Test presigned URL downloads")
    else:
        print("\n❌ Database initialization failed!")

if __name__ == "__main__":
    main()