import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

V1_DB_URL = "postgresql://postgres:vets_secure_pw@dva-db:5432/dva_db"
V2_DB_URL = "postgresql://postgres:vets_secure_pw@dva-db-v2:5432/dva_db"

def get_connection(db_url):
    return psycopg2.connect(db_url)

def migrate_scraped_content():
    print("Migrating scraped_content...")
    with get_connection(V1_DB_URL) as conn1, get_connection(V2_DB_URL) as conn2:
        with conn1.cursor(cursor_factory=RealDictCursor) as cur1, \
             conn2.cursor() as cur2:
            cur1.execute("""
                SELECT content_id, source_type, source_library, source_url, 
                       chunk_index, chunk_total, title, page_text, embedding,
                       content_hash, trust_level, last_scraped, created_at
                FROM scraped_content
            """)
            rows = cur1.fetchall()
            print(f"  Found {len(rows)} rows in v1")
            
            count = 0
            for row in rows:
                try:
                    cur2.execute("""
                        INSERT INTO scraped_content 
                        (source_type, source_library, source_url, chunk_index, chunk_total,
                         title, page_text, embedding, content_hash, trust_level, last_scraped, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['source_type'],
                        row['source_library'],
                        row['source_url'],
                        row['chunk_index'],
                        row['chunk_total'],
                        row['title'],
                        row['page_text'],
                        row['embedding'],
                        row['content_hash'],
                        row['trust_level'],
                        row['last_scraped'],
                        row['created_at']
                    ))
                    count += 1
                    if count % 1000 == 0:
                        conn2.commit()
                        print(f"    Committed {count} rows...")
                except Exception as e:
                    conn2.rollback()
                    print(f"  Error: {e}")
                    continue
            conn2.commit()
            print(f"  Migrated {count} rows")

def migrate_query_audit_log():
    print("\nMigrating query_audit_log...")
    with get_connection(V1_DB_URL) as conn1, get_connection(V2_DB_URL) as conn2:
        with conn1.cursor(cursor_factory=RealDictCursor) as cur1, \
             conn2.cursor() as cur2:
            cur1.execute("""
                SELECT log_id, logged_at, question, answer_snippet, sources_used,
                       trust_levels, has_conflict, used_sql, debug_sql, source_count,
                       latency_ms, error, user_flagged, flag_reason
                FROM query_audit_log
            """)
            rows = cur1.fetchall()
            print(f"  Found {len(rows)} rows in v1")
            
            count = 0
            for row in rows:
                try:
                    cur2.execute("""
                        INSERT INTO query_audit_log
                        (question, answer_snippet, sources_used, trust_levels, has_conflict,
                         used_sql, debug_sql, source_count, latency_ms, error, user_flagged, 
                         flag_reason, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['question'],
                        row['answer_snippet'],
                        json.dumps(row['sources_used']) if row['sources_used'] else None,
                        row['trust_levels'],
                        row['has_conflict'],
                        row['used_sql'],
                        row['debug_sql'],
                        row['source_count'],
                        row['latency_ms'],
                        row['error'],
                        row['user_flagged'],
                        row['flag_reason'],
                        row['logged_at']
                    ))
                    count += 1
                except Exception as e:
                    conn2.rollback()
                    print(f"  Error: {e}")
                    continue
            conn2.commit()
            print(f"  Migrated {count} rows")

def migrate_conversation_memory():
    print("\nMigrating conversation_memory...")
    with get_connection(V1_DB_URL) as conn1, get_connection(V2_DB_URL) as conn2:
        with conn1.cursor(cursor_factory=RealDictCursor) as cur1, \
             conn2.cursor() as cur2:
            cur1.execute("""
                SELECT id, user_id, question, answer, sources_cited, query_timestamp,
                       confidence_score, was_helpful, helpful_count, log_id, is_flagged, correction
                FROM conversation_memory
            """)
            rows = cur1.fetchall()
            print(f"  Found {len(rows)} rows in v1")
            
            count = 0
            for row in rows:
                try:
                    cur2.execute("""
                        INSERT INTO conversation_memory
                        (user_id, question, answer, sources_cited, confidence_score,
                         is_flagged, correction, query_timestamp, log_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['user_id'],
                        row['question'],
                        row['answer'],
                        json.dumps(row['sources_cited']) if row['sources_cited'] else None,
                        row['confidence_score'],
                        row['is_flagged'],
                        row['correction'],
                        row['query_timestamp'],
                        row['log_id']
                    ))
                    count += 1
                except Exception as e:
                    conn2.rollback()
                    print(f"  Error: {e}")
                    continue
            conn2.commit()
            print(f"  Migrated {count} rows")

def verify_counts():
    print("\nVerifying counts...")
    with get_connection(V1_DB_URL) as conn1, get_connection(V2_DB_URL) as conn2:
        with conn1.cursor() as cur1, conn2.cursor() as cur2:
            for table in ['scraped_content', 'query_audit_log', 'conversation_memory']:
                cur1.execute(f"SELECT COUNT(*) FROM {table}")
                cur2.execute(f"SELECT COUNT(*) FROM {table}")
                v1_row = cur1.fetchone()
                v2_row = cur2.fetchone()
                v1_count = v1_row[0] if v1_row else 0
                v2_count = v2_row[0] if v2_row else 0
                print(f"  {table}: v1={v1_count}, v2={v2_count}")

if __name__ == "__main__":
    print("Starting migration from v1 to v2...\n")
    migrate_scraped_content()
    migrate_query_audit_log()
    migrate_conversation_memory()
    verify_counts()
    print("\nMigration complete!")
