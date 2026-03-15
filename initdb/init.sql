-- init.sql - Database schema for DVA Assistant v2
-- Includes new embedding column for mxbai-embed-large

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dva_acts (
    id SERIAL PRIMARY KEY,
    act_name TEXT NOT NULL,
    act_code VARCHAR(20),
    description TEXT,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS service_categories (
    id SERIAL PRIMARY KEY,
    category_name TEXT NOT NULL,
    act_id INTEGER REFERENCES dva_acts(id),
    standard_of_proof TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS scraped_content (
    id SERIAL PRIMARY KEY,
    title TEXT,
    source_type VARCHAR(50),
    source_library VARCHAR(100),
    source_url TEXT UNIQUE,
    page_text TEXT,
    chunk_index INTEGER DEFAULT 0,
    chunk_total INTEGER DEFAULT 1,
    embedding vector(768),
    embedding_mxbai vector(1024),
    trust_level SMALLINT DEFAULT 3,
    content_hash CHAR(64),
    last_scraped TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraped_content_trust ON scraped_content(trust_level);
CREATE INDEX IF NOT EXISTS idx_scraped_content_source ON scraped_content(source_type);
CREATE INDEX IF NOT EXISTS idx_embedding ON scraped_content USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_embedding_mxbai ON scraped_content USING hnsw (embedding_mxbai vector_cosine_ops);

CREATE TABLE IF NOT EXISTS query_audit_log (
    log_id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer_snippet TEXT,
    sources_used JSONB,
    trust_levels SMALLINT[],
    has_conflict BOOLEAN DEFAULT FALSE,
    used_sql BOOLEAN DEFAULT FALSE,
    debug_sql TEXT,
    source_count INTEGER DEFAULT 0,
    latency_ms INTEGER,
    error TEXT,
    user_flagged BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    model_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    question TEXT NOT NULL,
    answer TEXT,
    sources_cited JSONB,
    confidence_score FLOAT DEFAULT 0.5,
    is_flagged BOOLEAN DEFAULT FALSE,
    correction TEXT,
    query_timestamp TIMESTAMP DEFAULT NOW(),
    log_id INTEGER REFERENCES query_audit_log(log_id)
);

CREATE TABLE IF NOT EXISTS scrape_seeds (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    label TEXT,
    source_type VARCHAR(50),
    added_via VARCHAR(20) DEFAULT 'system',
    is_active BOOLEAN DEFAULT TRUE,
    http_status INTEGER,
    check_error TEXT,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_checked TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    pages_processed INTEGER DEFAULT 0,
    pages_new INTEGER DEFAULT 0,
    pages_updated INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    max_depth INTEGER DEFAULT 2
);

CREATE OR REPLACE VIEW v_service_standards AS
SELECT 
    a.act_code,
    a.act_name,
    c.category_name,
    c.standard_of_proof,
    c.description as category_description
FROM dva_acts a
JOIN service_categories c ON a.id = c.act_id;

CREATE OR REPLACE VIEW v_dva_acts_simple AS
SELECT 
    act_code,
    act_name,
    COUNT(c.id) as category_count
FROM dva_acts a
LEFT JOIN service_categories c ON a.id = c.act_id
GROUP BY act_code, act_name;

CREATE OR REPLACE VIEW v_content_summary AS
SELECT 
    source_type,
    trust_level,
    COUNT(DISTINCT source_url) as page_count,
    COUNT(*) as chunk_count,
    MAX(last_scraped) as latest_scraped
FROM scraped_content
GROUP BY source_type, trust_level;

INSERT INTO dva_acts (act_name, act_code, description) VALUES
    ('Military Rehabilitation and Compensation Act 2004', 'MRCA', 'Primary Act for new claims from 1 July 2026'),
    ('Safety, Rehabilitation and Compensation (Defence-related Claims) Act 1988', 'DRCA', 'Legacy claims lodged before 1 July 2026'),
    ('Veterans'' Entitlements Act 1986', 'VEA', 'Pensions and income support payments')
ON CONFLICT DO NOTHING;
