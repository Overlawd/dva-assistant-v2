"""
Simplified migration for core data from v1 to v2
Focuses on scraped_content (knowledge base), conversation_memory, and query_audit_log
"""

import sys
sys.path.insert(0, '/app')

from migrate_from_v1 import get_engine
from sqlalchemy import text

V1_URL = "postgresql://postgres:vets_secure_pw@host.docker.internal:5432/dva_db"
V2_URL = "postgresql://postgres:vets_secure_pw@host.docker.internal:5433/dva_db"


def migrate_scraped_content_simple(batch_size=50):
    """Simple direct copy of scraped_content from v1 to v2."""
    print("\n=== Migrating scraped_content (simple) ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        total = v1_conn.execute(text("SELECT COUNT(*) FROM scraped_content")).scalar()
        print(f"Found {total} records in v1")
    
    migrated = 0
    offset = 0
    
    while offset < total:
        with v1_engine.connect() as v1_conn:
            rows = v1_conn.execute(text(f"""
                SELECT source_type, source_library, source_url, 
                       chunk_index, chunk_total, title, page_text, 
                       embedding, trust_level, content_hash, last_scraped, created_at
                FROM scraped_content
                ORDER BY content_id
                LIMIT {batch_size} OFFSET {offset}
            """)).fetchall()
        
        if not rows:
            break
        
        with v2_engine.connect() as v2_conn:
            for row in rows:
                try:
                    v2_conn.execute(text("""
                        INSERT INTO scraped_content 
                            (source_type, source_library, source_url, chunk_index, chunk_total,
                             title, page_text, embedding, trust_level, content_hash, last_scraped, created_at)
                        VALUES 
                            (:source_type, :source_library, :source_url, :chunk_index, :chunk_total,
                             :title, :page_text, :embedding, :trust_level, :content_hash, :last_scraped, :created_at)
                        ON CONFLICT (source_url, chunk_index) DO UPDATE SET
                            title = EXCLUDED.title,
                            page_text = EXCLUDED.page_text,
                            content_hash = EXCLUDED.content_hash,
                            last_scraped = EXCLUDED.last_scraped
                    """), {
                        "source_type": row[0],
                        "source_library": row[1],
                        "source_url": row[2],
                        "chunk_index": row[3],
                        "chunk_total": row[4],
                        "title": row[5],
                        "page_text": row[6],
                        "embedding": row[7],
                        "trust_level": row[8],
                        "content_hash": row[9],
                        "last_scraped": row[10],
                        "created_at": row[11],
                    })
                    migrated += 1
                except Exception as e:
                    print(f"Error: {e}")
            
            v2_conn.commit()
        
        offset += batch_size
        print(f"Progress: {min(offset, total)}/{total}")
    
    print(f"Migrated {migrated} scraped_content records")
    return {"migrated": migrated}


def migrate_conversation_simple():
    """Migrate conversation_memory."""
    print("\n=== Migrating conversation_memory ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        rows = v1_conn.execute(text("""
            SELECT user_id, question, answer, sources_cited, query_timestamp,
                   confidence_score, is_flagged, correction, log_id
            FROM conversation_memory
        """)).fetchall()
        print(f"Found {len(rows)} records in v1")
    
    migrated = 0
    with v2_engine.connect() as v2_conn:
        for row in rows:
            try:
                v2_conn.execute(text("""
                    INSERT INTO conversation_memory 
                        (user_id, question, answer, sources_cited, query_timestamp,
                         confidence_score, is_flagged, correction, log_id)
                    VALUES (:user_id, :question, :answer, :sources_cited, :query_timestamp,
                            :confidence_score, :is_flagged, :correction, :log_id)
                """), {
                    "user_id": row[0],
                    "question": row[1],
                    "answer": row[2],
                    "sources_cited": row[3],
                    "query_timestamp": row[4],
                    "confidence_score": row[5],
                    "is_flagged": row[6],
                    "correction": row[7],
                    "log_id": row[8],
                })
                migrated += 1
            except Exception as e:
                print(f"Error: {e}")
        v2_conn.commit()
    
    print(f"Migrated {migrated} conversation_memory records")
    return {"migrated": migrated}


def migrate_audit_log_simple():
    """Migrate query_audit_log."""
    print("\n=== Migrating query_audit_log ===")
    
    v1_engine = get_engine(V1_URL)
    v2_engine = get_engine(V2_URL)
    
    with v1_engine.connect() as v1_conn:
        rows = v1_conn.execute(text("""
            SELECT logged_at, question, answer_snippet, sources_used, trust_levels,
                   has_conflict, used_sql, debug_sql, source_count, latency_ms,
                   error, user_flagged, flag_reason
            FROM query_audit_log
        """)).fetchall()
        print(f"Found {len(rows)} records in v1")
    
    migrated = 0
    with v2_engine.connect() as v2_conn:
        for row in rows:
            try:
                v2_conn.execute(text("""
                    INSERT INTO query_audit_log 
                        (logged_at, question, answer_snippet, sources_used, trust_levels,
                         has_conflict, used_sql, debug_sql, source_count, latency_ms,
                         error, user_flagged, flag_reason)
                    VALUES (:logged_at, :question, :answer_snippet, :sources_used, :trust_levels,
                            :has_conflict, :used_sql, :debug_sql, :source_count, :latency_ms,
                            :error, :user_flagged, :flag_reason)
                """), {
                    "logged_at": row[0],
                    "question": row[1],
                    "answer_snippet": row[2],
                    "sources_used": row[3],
                    "trust_levels": row[4],
                    "has_conflict": row[5],
                    "used_sql": row[6],
                    "debug_sql": row[7],
                    "source_count": row[8],
                    "latency_ms": row[9],
                    "error": row[10],
                    "user_flagged": row[11],
                    "flag_reason": row[12],
                })
                migrated += 1
            except Exception as e:
                print(f"Error: {e}")
        v2_conn.commit()
    
    print(f"Migrated {migrated} query_audit_log records")
    return {"migrated": migrated}


if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLIFIED MIGRATION v1 → v2")
    print("=" * 60)
    
    migrate_scraped_content_simple()
    migrate_conversation_simple()
    migrate_audit_log_simple()
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
