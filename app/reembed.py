"""
reembed.py — Re-embedding tool for migrating to new embedding models

Migrates from nomic-embed-text (768-dim) to mxbai-embed-large (1024-dim).
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_ollama import OllamaEmbeddings

load_dotenv()

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
EMBED_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(db_url, pool_pre_ping=True)


def check_ollama_health() -> bool:
    """Check if Ollama is accessible."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_model_available(model: str) -> bool:
    """Check if a model is available in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return any(m["name"].startswith(model) for m in models)
        return False
    except Exception:
        return False


def run_migration(batch_size: int = 50, dry_run: bool = False):
    """
    Run the embedding migration.
    
    Args:
        batch_size: Number of rows to process at a time
        dry_run: If True, don't actually write to DB
    """
    print(f"=== Embedding Migration ===")
    print(f"Source model: nomic-embed-text (768-dim)")
    print(f"Target model: {EMBED_MODEL} ({EMBED_DIM}-dim)")
    print(f"Batch size: {batch_size}")
    print(f"Dry run: {dry_run}")
    print()
    
    if not check_ollama_health():
        print("ERROR: Ollama is not accessible!")
        return False
    
    if not check_model_available(EMBED_MODEL):
        print(f"WARNING: Model {EMBED_MODEL} not found in Ollama!")
        print(f"Pulling model...")
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": EMBED_MODEL},
                timeout=600,
                stream=True,
            )
            if response.status_code not in (200, 201):
                print(f"ERROR: Failed to pull model")
                return False
            print(f"Model {EMBED_MODEL} pulled successfully")
        except Exception as e:
            print(f"ERROR: Failed to pull model: {e}")
            return False
    
    emb_model = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'scraped_content' 
            AND column_name = 'embedding_mxbai'
        """))
        has_column = result.fetchone() is not None
        
        if not has_column:
            print("Creating embedding_mxbai column...")
            if not dry_run:
                conn.execute(text("""
                    ALTER TABLE scraped_content 
                    ADD COLUMN IF NOT EXISTS embedding_mxbai vector(1024)
                """))
                conn.commit()
            print("Column created.")
        
        result = conn.execute(text("SELECT COUNT(*) FROM scraped_content WHERE embedding_mxbai IS NULL"))
        total_to_process = result.scalar() or 0
        
        print(f"Total rows to process: {total_to_process}")
        
        if total_to_process == 0:
            print("No rows need re-embedding.")
            return True
        
        offset = 0
        processed = 0
        errors = 0
        
        print(f"Starting migration (press Ctrl+C to stop)...")
        start_time = time.time()
        
        while offset < total_to_process:
            try:
                result = conn.execute(text("""
                    SELECT id, page_text 
                    FROM scraped_content 
                    WHERE embedding_mxbai IS NULL
                    ORDER BY id
                    LIMIT :limit
                """), {"limit": batch_size})
                rows = result.fetchall()
                
                if not rows:
                    break
                
                for row_id, text_content in rows:
                    if not text_content or len(text_content.strip()) < 10:
                        continue
                    
                    try:
                        chunk_text = text_content[:8000]
                        embedding = emb_model.embed_query(chunk_text)
                        
                        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
                        
                        if not dry_run:
                            conn.execute(text("""
                                UPDATE scraped_content 
                                SET embedding_mxbai = CAST(:vec AS vector)
                                WHERE id = :id
                            """), {"vec": vec_literal, "id": row_id})
                        
                        processed += 1
                        
                    except Exception as e:
                        errors += 1
                        print(f"Error processing row {row_id}: {e}")
                
                if not dry_run:
                    conn.commit()
                
                offset += len(rows)
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (total_to_process - offset) / rate if rate > 0 else 0
                
                print(f"Progress: {offset}/{total_to_process} ({100*offset/total_to_process:.1f}%) - "
                      f"Rate: {rate:.1f}/s - ETA: {remaining/60:.1f}min")
                
            except KeyboardInterrupt:
                print("\nMigration interrupted by user.")
                break
            except Exception as e:
                print(f"Batch error: {e}")
                errors += 1
                time.sleep(5)
        
        print()
        print(f"=== Migration Complete ===")
        print(f"Processed: {processed}")
        print(f"Errors: {errors}")
        print(f"Time: {(time.time() - start_time)/60:.1f} minutes")
        
        return True


def create_index():
    """Create HNSW index on the new embedding column."""
    engine = get_engine()
    
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_embedding_mxbai 
                ON scraped_content 
                USING hnsw (embedding_mxbai vector_cosine_ops)
            """))
            conn.commit()
            print("Index created successfully.")
        except Exception as e:
            print(f"Index creation note: {e}")


def verify_migration():
    """Verify the migration was successful."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN embedding_mxbai IS NOT NULL THEN 1 ELSE 0 END) as embedded,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as old_embedded
            FROM scraped_content
        """))
        row = result.fetchone()
        
        if row is None:
            print("No data found in scraped_content table")
            return False
        
        total = row[0] or 0
        embedded = row[1] or 0
        old_embedded = row[2] or 0
        
        print(f"Total rows: {total}")
        print(f"New embeddings (mxbai): {embedded}")
        print(f"Old embeddings (nomic): {old_embedded}")
        
        if embedded and embedded == total:
            print("Migration verified - all rows have new embeddings!")
            return True
        else:
            print(f"Warning: {total - embedded} rows missing new embeddings")
            return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Re-embed scraped content")
    parser.add_argument("--batch", type=int, default=50, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--create-index", action="store_true", help="Create HNSW index")
    parser.add_argument("--verify", action="store_true", help="Verify migration")
    
    args = parser.parse_args()
    
    if args.verify:
        verify_migration()
    elif args.create_index:
        create_index()
    else:
        run_migration(batch_size=args.batch, dry_run=args.dry_run)
