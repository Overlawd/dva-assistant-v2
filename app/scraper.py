"""
scraper.py — Web scraper for DVA Assistant

Enhanced with support for new embedding models.
"""

import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, text
from langchain_ollama import OllamaEmbeddings

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "") or ""
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

SEED_URLS = [
    {"url": "https://www.dva.gov.au/", "label": "DVA Home", "type": "DVA_GOV"},
    {"url": "https://www.dva.gov.au/health-and-wellbeing", "label": "DVA Health", "type": "DVA_GOV"},
    {"url": "https://clik.dva.gov.au/", "label": "CLIK Home", "type": "CLIK"},
    {"url": "https://www.legislation.gov.au/Browse/ByTitle/Compensation/Veterans", "label": "Veterans Legislation", "type": "LEGISLATION"},
    {"url": "https://www.rma.gov.au/", "label": "RMA Home", "type": "LEGISLATION"},
    {"url": "https://www.reddit.com/r/DVAAustralia", "label": "Reddit Community", "type": "REDDIT"},
    {"url": "https://www.openarms.gov.au/", "label": "Open Arms", "type": "SUPPORT"},
    {"url": "https://www.veteransfirstconsulting.com/", "label": "Veterans First Consulting", "type": "SUPPORT"},
]

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
FRESHNESS_DAYS = 7


def get_engine():
    db_url: str = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(db_url, pool_pre_ping=True)


def get_embedding_model():
    return OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def normalize_url(url: str) -> str:
    url = re.sub(r"/asmade$", "/latest", url)
    return url


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    
    for script in soup(["script", "style"]):
        script.decompose()
    
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end < len(text):
            period = text.rfind(".", start, end)
            if period > start + chunk_size // 2:
                end = period + 1
        
        chunks.append(text[start:end])
        start = end - overlap
    
    return chunks


def determine_source_type(url: str) -> str:
    """Determine source type from URL."""
    url_lower = url.lower()
    if "legislation.gov.au" in url_lower or "rma.gov.au" in url_lower:
        return "LEGISLATION"
    elif "clik.dva.gov.au" in url_lower:
        return "CLIK"
    elif "dva.gov.au" in url_lower:
        return "DVA_GOV"
    elif "reddit.com" in url_lower:
        return "REDDIT"
    else:
        return "SUPPORT"


def determine_trust_level(url: str) -> int:
    """Determine trust level from URL."""
    source_type = determine_source_type(url)
    trust_map = {
        "LEGISLATION": 1,
        "CLIK": 2,
        "DVA_GOV": 3,
        "SUPPORT": 4,
        "REDDIT": 5,
    }
    return trust_map.get(source_type, 3)


def embed_text(text: str) -> Optional[List[float]]:
    try:
        emb_model = get_embedding_model()
        return emb_model.embed_query(text[:8000])
    except Exception as e:
        print(f"Embedding error: {e}")
        return None


def scrape_url(url: str, max_depth: int = 2) -> Dict:
    result = {
        "url": url,
        "title": "",
        "content": "",
        "links": [],
        "error": None,
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            result["title"] = page.title()
            
            try:
                summarize_btn = page.locator('button:has-text("Summarise this page")')
                if summarize_btn.count() > 0:
                    summarize_btn.click()
                    time.sleep(2)
            except Exception:
                pass
            
            result["content"] = extract_text_from_html(page.content())
            
            links = page.locator("a[href]").all()
            for link in links[:50]:
                try:
                    href = link.get_attribute("href")
                    if href and (href.startswith("http") or href.startswith("/")):
                        result["links"].append(href)
                except Exception:
                    pass
            
            browser.close()
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def store_content(url: str, title: str, content: Optional[str] = None, source_type: Optional[str] = None, chunk_index: int = 0, chunk_total: int = 1):
    if not content:
        content = ""
    content_hash = compute_hash(content)
    source_type = source_type or determine_source_type(url)
    trust_level = determine_trust_level(url)
    
    embedding = embed_text(content)
    
    if embedding:
        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        
        if EMBEDDING_DIM == 1024:
            embed_col = "embedding_mxbai"
            embed_literal = vec_literal
        else:
            embed_col = "embedding"
            embed_literal = vec_literal
    else:
        embed_col = "embedding"
        embed_literal = "NULL"
    
    engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(text(f"""
            INSERT INTO scraped_content 
                (title, source_type, source_url, page_text, chunk_index, chunk_total, 
                 {embed_col}, trust_level, content_hash, last_scraped)
            VALUES (:title, :source_type, :source_url, :page_text, :chunk_index, :chunk_total,
                    CAST(:embed AS vector), :trust_level, :hash, NOW())
            ON CONFLICT (source_url, chunk_index) 
            DO UPDATE SET page_text = EXCLUDED.page_text,
                          content_hash = EXCLUDED.content_hash,
                          last_scraped = NOW()
        """), {
            "title": title[:500],
            "source_type": source_type,
            "source_url": normalize_url(url),
            "page_text": content[:10000],
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
            "embed": embed_literal if embedding else None,
            "trust_level": trust_level,
            "hash": content_hash,
        })
        conn.commit()


def should_scrape(url: str) -> bool:
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT last_scraped, content_hash 
            FROM scraped_content 
            WHERE source_url = :url
            ORDER BY last_scraped DESC 
            LIMIT 1
        """), {"url": normalize_url(url)}).fetchone()
        
        if not result:
            return True
        
        last_scraped = result[0]
        if last_scraped:
            age_days = (datetime.now() - last_scraped).days
            if age_days < FRESHNESS_DAYS:
                return False
        
        return True


def crawl_seeds(max_pages: int = 100, force: bool = False):
    """Main crawl function."""
    print(f"Starting crawl (max: {max_pages} pages)")
    
    visited: Set[str] = set()
    to_visit = [(s["url"], 0) for s in SEED_URLS]
    
    scraped = 0
    skipped = 0
    stored = 0
    
    while to_visit and scraped < max_pages:
        url, depth = to_visit.pop(0)
        
        if url in visited:
            continue
        
        visited.add(url)
        
        if not force and not should_scrape(url):
            skipped += 1
            continue
        
        scraped += 1
        print(f"Scraping ({scraped}/{max_pages}): {url}")
        
        result = scrape_url(url)
        
        if result.get("content"):
            chunks = chunk_text(result["content"])
            
            for i, chunk in enumerate(chunks):
                store_content(
                    url=url,
                    title=result.get("title", url),
                    content=chunk,
                    chunk_index=i,
                    chunk_total=len(chunks),
                )
                stored += 1
            
            if depth < 2:
                for link in result.get("links", [])[:10]:
                    if link not in visited:
                        to_visit.append((link, depth + 1))
        else:
            print(f"  Warning: No content retrieved")
        
        time.sleep(1)
    
    print(f"\nCrawl complete:")
    print(f"  Scraped: {scraped} pages")
    print(f"  Skipped (fresh): {skipped} pages")
    print(f"  Stored: {stored} chunks")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("max_pages", type=int, default=100)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    
    crawl_seeds(max_pages=args.max_pages, force=args.force)
