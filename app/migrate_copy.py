"""
Very simple migration - just copy scraped_content directly without ON CONFLICT
"""

import sys
sys.path.insert(0, '/app')

from migrate_from_v1 import get_engine
from sqlalchemy import text

V1_URL = "postgresql://postgres:vets_secure_pw@dva-db:5432/dva_db"
V2_URL = "postgresql://postgres:vets_secure_pw@dva-db-v2:5432/dva_db"

def copy_scraped_content():
    print("\n=== Copying scraped_content ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        total = v1_conn.execute(text("SELECT COUNT(*) FROM scraped_content")).scalar()
        print(f"Found {total} records in v1")
    
    # Use PostgreSQL COPY for fast bulk transfer
    with v1_engine.connect() as v1_conn:
        with v2_engine.connect() as v2_conn:
            # Clear existing data
            v2_conn.execute(text("TRUNCATE TABLE scraped_content RESTART IDENTITY CASCADE"))
            v2_conn.commit()
            
            # Copy using INSERT...SELECT with ON CONFLICT DO NOTHING
            result = v1_conn.execute(text("""
                INSERT INTO scraped_content 
                    (source_type, source_library, source_url, chunk_index, chunk_total,
                     title, page_text, embedding, trust_level, content_hash, last_scraped, created_at)
                SELECT 
                    source_type, source_library, source_url, chunk_index, chunk_total,
                    title, page_text, embedding, trust_level, content_hash, last_scraped, created_at
                FROM scraped_content
                ON CONFLICT (source_url, chunk_index) DO NOTHING
            """))
            v2_conn.commit()
            print(f"Copied {total} records")
    
    return {"migrated": total}


def copy_conversation_memory():
    print("\n=== Copying conversation_memory ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        total = v1_conn.execute(text("SELECT COUNT(*) FROM conversation_memory")).scalar()
        print(f"Found {total} records in v1")
    
    with v1_engine.connect() as v1_conn:
        with v2_engine.connect() as v2_conn:
            v2_conn.execute(text("TRUNCATE TABLE conversation_memory RESTART IDENTITY CASCADE"))
            v2_conn.commit()
            
            # Copy only common columns between v1 and v2
            v1_conn.execute(text("""
                INSERT INTO conversation_memory 
                    (user_id, question, answer, sources_cited, query_timestamp, confidence_score)
                SELECT 
                    user_id, question, answer, sources_cited, query_timestamp, confidence_score
                FROM conversation_memory
            """))
            v2_conn.commit()
            print(f"Copied {total} records")
    
    return {"migrated": total}


def copy_query_audit_log():
    print("\n=== Copying query_audit_log ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        total = v1_conn.execute(text("SELECT COUNT(*) FROM query_audit_log")).scalar()
        print(f"Found {total} records in v1")
    
    with v1_engine.connect() as v1_conn:
        with v2_engine.connect() as v2_conn:
            v2_conn.execute(text("TRUNCATE TABLE query_audit_log RESTART IDENTITY CASCADE"))
            v2_conn.commit()
            
            # Copy common columns
            v1_conn.execute(text("""
                INSERT INTO query_audit_log 
                    (question, answer_snippet, sources_used, trust_levels,
                     has_conflict, used_sql, debug_sql, source_count, latency_ms, error)
                SELECT 
                    question, answer_snippet, sources_used, trust_levels,
                    has_conflict, used_sql, debug_sql, source_count, latency_ms, error
                FROM query_audit_log
            """))
            v2_conn.commit()
            print(f"Copied {total} records")
    
    return {"migrated": total}


if __name__ == "__main__":
    print("=" * 60)
    print("DIRECT COPY MIGRATION v1 → v2")
    print("=" * 60)
    
    copy_scraped_content()
    copy_conversation_memory()
    copy_query_audit_log()
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
