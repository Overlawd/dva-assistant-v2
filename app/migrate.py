#!/usr/bin/env python3
"""
migrate.py — Schema verification for DVA Assistant v2

Ensures the database schema matches init.sql. Idempotent — safe to run multiple times.

Run:
    docker exec dva-web python migrate.py
    # or
    docker exec dva-db psql -U postgres -d dva_db -f /docker-entrypoint-initdb.d/init.sql
"""

import sys
import os
from datetime import datetime

import psycopg2
from psycopg2 import sql


def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    
    # Parse connection string
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip("/")
    )


def column_exists(conn, table: str, column: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table, column))
        return cur.fetchone() is not None


def constraint_exists(conn, table: str, constraint_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = %s AND constraint_name = %s
        """, (table, constraint_name))
        return cur.fetchone() is not None


def verify_and_fix_schema(conn):
    """Verify schema matches init.sql and fix any issues."""
    issues_fixed = []
    
    with conn.cursor() as cur:
        # Check scraped_content unique constraint
        if not constraint_exists(conn, "scraped_content", "scraped_content_url_chunk_key"):
            cur.execute("""
                ALTER TABLE scraped_content 
                ADD CONSTRAINT scraped_content_url_chunk_key UNIQUE (source_url, chunk_index)
            """)
            conn.commit()
            issues_fixed.append("Added UNIQUE(source_url, chunk_index) constraint")
        
        # Check query_audit_log columns
        if not column_exists(conn, "query_audit_log", "user_flagged"):
            cur.execute("ALTER TABLE query_audit_log ADD COLUMN user_flagged BOOLEAN DEFAULT FALSE")
            conn.commit()
            issues_fixed.append("Added user_flagged column to query_audit_log")
            
        if not column_exists(conn, "query_audit_log", "flag_reason"):
            cur.execute("ALTER TABLE query_audit_log ADD COLUMN flag_reason TEXT")
            conn.commit()
            issues_fixed.append("Added flag_reason column to query_audit_log")
            
        if not column_exists(conn, "query_audit_log", "model_used"):
            cur.execute("ALTER TABLE query_audit_log ADD COLUMN model_used VARCHAR(100)")
            conn.commit()
            issues_fixed.append("Added model_used column to query_audit_log")
        
        # Check conversation_memory columns
        if not column_exists(conn, "conversation_memory", "is_flagged"):
            cur.execute("ALTER TABLE conversation_memory ADD COLUMN is_flagged BOOLEAN DEFAULT FALSE")
            conn.commit()
            issues_fixed.append("Added is_flagged column to conversation_memory")
            
        if not column_exists(conn, "conversation_memory", "correction"):
            cur.execute("ALTER TABLE conversation_memory ADD COLUMN correction TEXT")
            conn.commit()
            issues_fixed.append("Added correction column to conversation_memory")
            
        if not column_exists(conn, "conversation_memory", "log_id"):
            cur.execute("ALTER TABLE conversation_memory ADD COLUMN log_id INTEGER REFERENCES query_audit_log(log_id)")
            conn.commit()
            issues_fixed.append("Added log_id column to conversation_memory")
        
        # Check scrape_seeds columns
        if not column_exists(conn, "scrape_seeds", "fail_count"):
            cur.execute("ALTER TABLE scrape_seeds ADD COLUMN fail_count INTEGER DEFAULT 0")
            conn.commit()
            issues_fixed.append("Added fail_count column to scrape_seeds")
    
    return issues_fixed


def show_status(conn):
    """Show current database status."""
    with conn.cursor() as cur:
        # Trust level distribution
        cur.execute("""
            SELECT trust_level, source_type, 
                   COUNT(DISTINCT source_url) as pages, 
                   COUNT(*) as chunks
            FROM scraped_content
            GROUP BY trust_level, source_type
            ORDER BY trust_level, source_type
        """)
        rows = cur.fetchall()
        
        print("\n📊 Content Summary:")
        if rows:
            print(f"   {'Level':<8} {'Source':<14} {'Pages':>8} {'Chunks':>8}")
            print(f"   {'-'*44}")
            for r in rows:
                print(f"   {r[0]:<8} {r[1]:<14} {r[2]:>8} {r[3]:>8}")
        else:
            print("   (no content yet)")
        
        # Table counts
        tables = ['scraped_content', 'query_audit_log', 'conversation_memory', 'scrape_seeds']
        print("\n📁 Table Counts:")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   {table}: {count}")


def main():
    print("=" * 60)
    print("DVA Assistant v2 — Schema Verification")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    conn = None
    try:
        conn = get_connection()
        print("✅ Connected to database")
        
        # Verify and fix schema
        issues = verify_and_fix_schema(conn)
        
        if issues:
            print("\n🔧 Issues Fixed:")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print("\n✅ Schema is up to date — no fixes needed")
        
        # Show status
        show_status(conn)
        
        print("\n" + "=" * 60)
        print("✅ Verification complete")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
