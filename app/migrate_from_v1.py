"""
migrate_from_v1.py — Migrate data from DVA Assistant v1 to v2

Usage:
    # Run from host (assumes v1 and v2 databases are accessible)
    python migrate_from_v1.py --v1-url postgresql://postgres:vets_secure_pw@localhost:5432/dva_db --v2-url postgresql://postgres:vets_secure_pw@localhost:5433/dva_db
    
    # Or run via Docker (with both DBs accessible from scraper container)
    docker exec dva-scraper-v2 python migrate_from_v1.py
"""

import os
import sys
import argparse
import time
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import requests

load_dotenv()


V1_DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:vets_secure_pw@db:5432/dva_db")
V2_DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:vets_secure_pw@db:5432/dva_db")


def get_engine(db_url: str):
    return create_engine(db_url, pool_pre_ping=True)


def migrate_dva_acts(v1_engine, v2_engine, dry_run: bool = False) -> dict:
    """Migrate dva_acts table."""
    print("\n=== Migrating dva_acts ===")
    
    with v1_engine.connect() as v1_conn:
        acts = v1_conn.execute(text("SELECT * FROM dva_acts")).fetchall()
        print(f"Found {len(acts)} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": len(acts)}
    
    with v2_engine.connect() as v2_conn:
        for act in acts:
            try:
                v2_conn.execute(text("""
                    INSERT INTO dva_acts (id, act_name, act_code, description, effective_date, created_at)
                    VALUES (:id, :act_name, :act_code, :description, :effective_date, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        act_name = EXCLUDED.act_name,
                        act_code = EXCLUDED.act_code,
                        description = EXCLUDED.description,
                        effective_date = EXCLUDED.effective_date
                """), {
                    "id": act[0],
                    "act_name": act[1],
                    "act_code": act[2],
                    "description": act[3],
                    "effective_date": act[4],
                    "created_at": act[5],
                })
            except Exception as e:
                print(f"Error migrating act {act[0]}: {e}")
        v2_conn.commit()
    
    print(f"Migrated {len(acts)} dva_acts records")
    return {"migrated": len(acts)}


def migrate_service_categories(v1_engine, v2_engine, dry_run: bool = False) -> dict:
    """Migrate service_categories table."""
    print("\n=== Migrating service_categories ===")
    
    with v1_engine.connect() as v1_conn:
        categories = v1_conn.execute(text("SELECT * FROM service_categories")).fetchall()
        print(f"Found {len(categories)} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": len(categories)}
    
    with v2_engine.connect() as v2_conn:
        for cat in categories:
            try:
                v2_conn.execute(text("""
                    INSERT INTO service_categories (id, category_name, act_id, standard_of_proof, description)
                    VALUES (:id, :category_name, :act_id, :standard_of_proof, :description)
                    ON CONFLICT (id) DO UPDATE SET
                        category_name = EXCLUDED.category_name,
                        act_id = EXCLUDED.act_id,
                        standard_of_proof = EXCLUDED.standard_of_proof,
                        description = EXCLUDED.description
                """), {
                    "id": cat[0],
                    "category_name": cat[1],
                    "act_id": cat[2],
                    "standard_of_proof": cat[3],
                    "description": cat[4],
                })
            except Exception as e:
                print(f"Error migrating category {cat[0]}: {e}")
        v2_conn.commit()
    
    print(f"Migrated {len(categories)} service_categories records")
    return {"migrated": len(categories)}


def migrate_scraped_content(v1_engine, v2_engine, batch_size: int = 100, dry_run: bool = False) -> dict:
    """Migrate scraped_content table with new embedding column."""
    print("\n=== Migrating scraped_content ===")
    
    with v1_engine.connect() as v1_conn:
        v1_conn.execute(text("SELECT COUNT(*) FROM scraped_content"))
        total = v1_conn.execute(text("SELECT COUNT(*) FROM scraped_content")).scalar()
        print(f"Found {total} records in v1")
    
    if dry_run:
        print(f"DRY RUN - would migrate {total} records")
        return {"migrated": 0}
    
    migrated = 0
    errors = 0
    offset = 0
    
    while offset < total:
        with v1_engine.connect() as v1_conn:
            rows = v1_conn.execute(text("""
                SELECT id, title, source_type, source_library, source_url, 
                       page_text, chunk_index, chunk_total, embedding, 
                       trust_level, content_hash, last_scraped, created_at
                FROM scraped_content
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """), {"limit": batch_size, "offset": offset}).fetchall()
        
        if not rows:
            break
        
        with v2_engine.connect() as v2_conn:
            for row in rows:
                try:
                    v2_conn.execute(text("""
                        INSERT INTO scraped_content 
                            (id, title, source_type, source_library, source_url, 
                             page_text, chunk_index, chunk_total, embedding, 
                             embedding_mxbai, trust_level, content_hash, last_scraped, created_at)
                        VALUES 
                            (:id, :title, :source_type, :source_library, :source_url,
                             :page_text, :chunk_index, :chunk_total, :embedding,
                             NULL, :trust_level, :content_hash, :last_scraped, :created_at)
                        ON CONFLICT (source_url, chunk_index) DO UPDATE SET
                            title = EXCLUDED.title,
                            page_text = EXCLUDED.page_text,
                            content_hash = EXCLUDED.content_hash,
                            last_scraped = EXCLUDED.last_scraped
                    """), {
                        "id": row[0],
                        "title": row[1],
                        "source_type": row[2],
                        "source_library": row[3],
                        "source_url": row[4],
                        "page_text": row[5],
                        "chunk_index": row[6],
                        "chunk_total": row[7],
                        "embedding": row[8],
                        "trust_level": row[9],
                        "content_hash": row[10],
                        "last_scraped": row[11],
                        "created_at": row[12],
                    })
                    migrated += 1
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"Error migrating content {row[0]}: {e}")
            
            v2_conn.commit()
        
        offset += batch_size
        print(f"Progress: {min(offset, total)}/{total} ({100*min(offset,total)/total:.1f}%)")
    
    print(f"Migrated {migrated} scraped_content records ({errors} errors)")
    return {"migrated": migrated, "errors": errors}


def migrate_conversation_memory(v1_engine, v2_engine, dry_run: bool = False) -> dict:
    """Migrate conversation_memory table."""
    print("\n=== Migrating conversation_memory ===")
    
    with v1_engine.connect() as v1_conn:
        memories = v1_conn.execute(text("SELECT * FROM conversation_memory")).fetchall()
        print(f"Found {len(memories)} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": len(memories)}
    
    with v2_engine.connect() as v2_conn:
        for mem in memories:
            try:
                v2_conn.execute(text("""
                    INSERT INTO conversation_memory 
                        (id, user_id, question, answer, sources_cited, 
                         confidence_score, is_flagged, correction, query_timestamp, log_id)
                    VALUES (:id, :user_id, :question, :answer, :sources_cited,
                            :confidence_score, :is_flagged, :correction, :query_timestamp, :log_id)
                    ON CONFLICT (id) DO UPDATE SET
                        question = EXCLUDED.question,
                        answer = EXCLUDED.answer,
                        is_flagged = EXCLUDED.is_flagged,
                        correction = EXCLUDED.correction
                """), {
                    "id": mem[0],
                    "user_id": mem[1],
                    "question": mem[2],
                    "answer": mem[3],
                    "sources_cited": mem[4],
                    "confidence_score": mem[5],
                    "is_flagged": mem[6],
                    "correction": mem[7],
                    "query_timestamp": mem[8],
                    "log_id": mem[9],
                })
            except Exception as e:
                print(f"Error migrating memory {mem[0]}: {e}")
        v2_conn.commit()
    
    print(f"Migrated {len(memories)} conversation_memory records")
    return {"migrated": len(memories)}


def migrate_query_audit_log(v1_engine, v2_engine, batch_size: int = 100, dry_run: bool = False) -> dict:
    """Migrate query_audit_log table."""
    print("\n=== Migrating query_audit_log ===")
    
    with v1_engine.connect() as v1_conn:
        total = v1_conn.execute(text("SELECT COUNT(*) FROM query_audit_log")).scalar()
        print(f"Found {total} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": 0}
    
    migrated = 0
    offset = 0
    
    while offset < total:
        with v1_engine.connect() as v1_conn:
            rows = v1_conn.execute(text("""
                SELECT log_id, question, answer_snippet, sources_used, trust_levels,
                       has_conflict, used_sql, debug_sql, source_count, latency_ms,
                       error, user_flagged, flag_reason, created_at
                FROM query_audit_log
                ORDER BY log_id
                LIMIT :limit OFFSET :offset
            """), {"limit": batch_size, "offset": offset}).fetchall()
        
        if not rows:
            break
        
        with v2_engine.connect() as v2_conn:
            for row in rows:
                try:
                    v2_conn.execute(text("""
                        INSERT INTO query_audit_log 
                            (log_id, question, answer_snippet, sources_used, trust_levels,
                             has_conflict, used_sql, debug_sql, source_count, latency_ms,
                             error, user_flagged, flag_reason, model_used, created_at)
                        VALUES 
                            (:log_id, :question, :answer_snippet, :sources_used, :trust_levels,
                             :has_conflict, :used_sql, :debug_sql, :source_count, :latency_ms,
                             :error, :user_flagged, :flag_reason, NULL, :created_at)
                        ON CONFLICT (log_id) DO UPDATE SET
                            question = EXCLUDED.question,
                            answer_snippet = EXCLUDED.answer_snippet,
                            user_flagged = EXCLUDED.user_flagged,
                            flag_reason = EXCLUDED.flag_reason
                    """), {
                        "log_id": row[0],
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
                        "created_at": row[13],
                    })
                    migrated += 1
                except Exception as e:
                    print(f"Error migrating audit log {row[0]}: {e}")
            
            v2_conn.commit()
        
        offset += batch_size
        print(f"Progress: {min(offset, total)}/{total}")
    
    print(f"Migrated {migrated} query_audit_log records")
    return {"migrated": migrated}


def migrate_scrape_seeds(v1_engine, v2_engine, dry_run: bool = False) -> dict:
    """Migrate scrape_seeds table."""
    print("\n=== Migrating scrape_seeds ===")
    
    with v1_engine.connect() as v1_conn:
        seeds = v1_conn.execute(text("SELECT * FROM scrape_seeds")).fetchall()
        print(f"Found {len(seeds)} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": len(seeds)}
    
    with v2_engine.connect() as v2_conn:
        for seed in seeds:
            try:
                v2_conn.execute(text("""
                    INSERT INTO scrape_seeds 
                        (id, url, label, source_type, added_via, is_active,
                         http_status, check_error, fail_count, created_at, last_checked)
                    VALUES 
                        (:id, :url, :label, :source_type, :added_via, :is_active,
                         :http_status, :check_error, :fail_count, :created_at, :last_checked)
                    ON CONFLICT (url) DO UPDATE SET
                        label = EXCLUDED.label,
                        source_type = EXCLUDED.source_type,
                        is_active = EXCLUDED.is_active,
                        http_status = EXCLUDED.http_status,
                        fail_count = EXCLUDED.fail_count,
                        last_checked = EXCLUDED.last_checked
                """), {
                    "id": seed[0],
                    "url": seed[1],
                    "label": seed[2],
                    "source_type": seed[3],
                    "added_via": seed[4],
                    "is_active": seed[5],
                    "http_status": seed[6],
                    "check_error": seed[7],
                    "fail_count": seed[8],
                    "created_at": seed[9],
                    "last_checked": seed[10],
                })
            except Exception as e:
                print(f"Error migrating seed {seed[0]}: {e}")
        v2_conn.commit()
    
    print(f"Migrated {len(seeds)} scrape_seeds records")
    return {"migrated": len(seeds)}


def migrate_scrape_log(v1_engine, v2_engine, dry_run: bool = False) -> dict:
    """Migrate scrape_log table."""
    print("\n=== Migrating scrape_log ===")
    
    with v1_engine.connect() as v1_conn:
        logs = v1_conn.execute(text("SELECT * FROM scrape_log")).fetchall()
        print(f"Found {len(logs)} records in v1")
    
    if dry_run:
        print("DRY RUN - would migrate these records")
        return {"migrated": len(logs)}
    
    with v2_engine.connect() as v2_conn:
        for log in logs:
            try:
                v2_conn.execute(text("""
                    INSERT INTO scrape_log 
                        (id, started_at, completed_at, pages_processed, pages_new,
                         pages_updated, errors, max_depth)
                    VALUES 
                        (:id, :started_at, :completed_at, :pages_processed, :pages_new,
                         :pages_updated, :errors, :max_depth)
                    ON CONFLICT (id) DO UPDATE SET
                        pages_processed = EXCLUDED.pages_processed,
                        pages_new = EXCLUDED.pages_new,
                        pages_updated = EXCLUDED.pages_updated,
                        completed_at = EXCLUDED.completed_at
                """), {
                    "id": log[0],
                    "started_at": log[1],
                    "completed_at": log[2],
                    "pages_processed": log[3],
                    "pages_new": log[4],
                    "pages_updated": log[5],
                    "errors": log[6],
                    "max_depth": log[7],
                })
            except Exception as e:
                print(f"Error migrating log {log[0]}: {e}")
        v2_conn.commit()
    
    print(f"Migrated {len(logs)} scrape_log records")
    return {"migrated": len(logs)}


def run_full_migration(v1_url: str, v2_url: str, dry_run: bool = False, batch_size: int = 100) -> dict:
    """Run complete migration from v1 to v2."""
    print("=" * 60)
    print("DVA ASSISTANT v1 → v2 MIGRATION")
    print("=" * 60)
    print(f"V1 Database: {v1_url}")
    print(f"V2 Database: {v2_url}")
    print(f"Dry Run: {dry_run}")
    print("=" * 60)
    
    v1_engine = get_engine(v1_url)
    v2_engine = get_engine(v2_url)
    
    results = {}
    
    results["dva_acts"] = migrate_dva_acts(v1_engine, v2_engine, dry_run)
    results["service_categories"] = migrate_service_categories(v1_engine, v2_engine, dry_run)
    results["scrape_seeds"] = migrate_scrape_seeds(v1_engine, v2_engine, dry_run)
    results["scrape_log"] = migrate_scrape_log(v1_engine, v2_engine, dry_run)
    results["scraped_content"] = migrate_scraped_content(v1_engine, v2_engine, batch_size, dry_run)
    results["conversation_memory"] = migrate_conversation_memory(v1_engine, v2_engine, dry_run)
    results["query_audit_log"] = migrate_query_audit_log(v1_engine, v2_engine, batch_size, dry_run)
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    
    total_migrated = sum(r.get("migrated", 0) for r in results.values())
    print(f"Total records migrated: {total_migrated}")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate DVA Assistant v1 to v2")
    parser.add_argument("--v1-url", default=V1_DB_URL, help="V1 database URL")
    parser.add_argument("--v2-url", default=V2_DB_URL, help="V2 database URL")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without writing")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for large tables")
    
    args = parser.parse_args()
    
    results = run_full_migration(args.v1_url, args.v2_url, args.dry_run, args.batch_size)
