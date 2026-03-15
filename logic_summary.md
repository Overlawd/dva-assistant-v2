# DVA Assistant - Logic Flow Summary

## High-Level Architecture

```mermaid
flowchart TD
    subgraph Client[User Interface]
        UI[Streamlit UI<br/>:8501]
    end
    
    subgraph Web_App[Web Container<br/>dva-web]
        MAIN[main.py<br/>RAG Pipeline]
        UI_PY[ui.py<br/>Request Handler]
    end
    
    subgraph Scraper_App[Scraper Container<br/>dva-scraper]
        SCRAPER[scraper.py<br/>Crawler]
    end
    
    subgraph Database[Database Container<br/>dva-db]
        PG[(PostgreSQL<br/>+ pgvector)]
    end
    
    subgraph Ollama[Ollama Container<br/>dva-ollama]
        LLM[LLM Inference]
        EMBEDD[Embeddings]
    end
    
    UI --> UI_PY
    UI_PY --> MAIN
    MAIN --> PG
    MAIN --> LLM
    MAIN --> EMBEDD
    SCRAPER --> PG
    SCRAPER --> EMBEDD
```

---

## Query Flow (User Asks Question)

```mermaid
flowchart TD
    START([User enters<br/>question]) --> CLASSIFY{Classify Input<br/>Question vs Statement}
    
    CLASSIFY -->|Statement| STMT_ACK[Build warm<br/>acknowledgement]
    STMT_ACK --> STORE_SESSION[Store in session<br/>context]
    STORE_SESSION --> RETURN_ACK[Return acknowledgement<br/>to user]
    
    CLASSIFY -->|Question| VETAN_CONTEXT[Extract veteran<br/>context from session]
    VETAN_CONTEXT --> PAST_CONV{Retrieve similar<br/>past conversations?}
    
    PAST_CONV -->|Yes| PAST_RETRIEVE[Get relevant<br/>past Q&A pairs]
    PAST_RETRIEVE --> SQL_GEN
    
    PAST_CONV -->|No| SQL_GEN[Generate SQL<br/>from question]
    
    SQL_GEN --> SQL_CHECK{Valid SELECT<br/>statement?}
    SQL_CHECK -->|Yes| EXEC_SQL[Execute SQL<br/>on database]
    SQL_CHECK -->|No| SKIP_SQL[Skip SQL<br/>execution]
    
    EXEC_SQL --> VECTOR_SEARCH
    SKIP_SQL --> VECTOR_SEARCH
    
    VECTOR_SEARCH[Vector Search<br/>Semantic retrieval] --> RERANK[Re-rank results<br/>TF-IDF + Cosine]
    
    RERANK --> BUILD_CTX[Build weighted<br/>context]
    
    BUILD_CTX --> CONFLICT{Conflict<br/>detection?}
    CONFLICT -->|Yes| MARK_CONFLICT[Flag potential<br/>conflict]
    CONFLICT -->|No| ROUTE_MODEL
    
    MARK_CONFLICT --> ROUTE_MODEL[Route to optimal<br/>model based on<br/>complexity]
    
    ROUTE_MODEL --> INVOKE_LLM[Invoke LLM with<br/>context + prompt]
    INVOKE_LLM --> CLEAN_RESP[Clean response<br/>Remove metadata]
    
    CLEAN_RESP --> DEDUP_SOURCES[Deduplicate<br/>source citations]
    DEDUP_SOURCES --> AUDIT_LOG[Log to<br/>query_audit_log]
    
    AUDIT_LOG --> STORE_MEM[Store in<br/>conversation_memory]
    STORE_MEM --> RETURN([Return answer<br/>to user])
```

---

## Input Classification Logic

```mermaid
flowchart TD
    START([Input text]) --> EMPTY{Is empty?}
    EMPTY -->|Yes| RETURN_Q[Return as<br/>question]
    EMPTY -->|No| CHECK_Q_OVERRIDE{Question override<br/>patterns?}
    
    CHECK_Q_OVERRIDE -->|Match| RETURN_Q
    
    CHECK_Q_OVERRIDE -->|No Match| SCORE_Q[Score for question]
    SCORE_Q --> HAS_QUESTION_MARK{"?" present?}
    HAS_QUESTION_MARK -->|Yes| Q_PLUS3[+3 to question<br/>score]
    HAS_QUESTION_MARK -->|No| CHECK_QWORDS
    
    CHECK_QWORDS{Starts with<br/>what/how/who/etc?} -->|Yes| Q_PLUS2[+2 to question<br/>score]
    CHECK_QWORDS -->|No| CHECK_AUX
    
    CHECK_AUX{Starts with<br/>is/are/will/etc?} -->|Yes| Q_PLUS2_AUX[+2 to question<br/>score]
    CHECK_AUX -->|No| CHECK_IMP
    
    CHECK_IMP{Starts with<br/>explain/tell/etc?} -->|Yes| Q_PLUS2_IMP[+2 to question<br/>score]
    CHECK_IMP -->|No| CHECK_STMT
    
    CHECK_STMT{Starts with<br/>I have/I am/My?} -->|Yes| S_PLUS3[+3 to statement<br/>score]
    CHECK_STMT -->|No| CHECK_MEDICAL
    
    CHECK_MEDICAL{Contains medical<br/>terms + personal<br/>pronouns?} -->|Yes| S_PLUS2[+2 to statement<br/>score]
    CHECK_MEDICAL -->|No| COMPARE
    
    Q_PLUS3 --> COMPARE
    Q_PLUS2 --> COMPARE
    Q_PLUS2_AUX --> COMPARE
    Q_PLUS2_IMP --> COMPARE
    S_PLUS3 --> COMPARE
    S_PLUS2 --> COMPARE
    
    COMPARE{Compare scores} --> STATEMENT{Score ><br/>Question?}
    STATEMENT -->|Yes| RETURN_S[Return as<br/>statement]
    STATEMENT -->|No| RETURN_Q
    
    RETURN_S --> BUILD_ACK[Build acknowledgement<br/>based on content]
    RETURN_Q --> END([Return classification])
    RETURN_S --> END
    BUILD_ACK --> END
```

---

## Model Routing Logic

```mermaid
flowchart TD
    START([Question]) --> ANALYZE[Analyze question<br/>for keywords]
    
    ANALYZE --> COMPLEX_COUNT[Count complex<br/>keywords]
    ANALYZE --> TECH_COUNT[Count technical<br/>keywords]
    ANALYZE --> COND_COUNT[Count conditional<br/>keywords]
    
    COMPLEX_COUNT --> SCORE{complex >= 2<br/>OR tech >= 2<br/>OR cond >= 3?}
    SCORE -->|Yes| ROUTE_COMPLEX[Route to<br/>MODEL_COMPLEX<br/>qwen2.5:14b]
    SCORE -->|No| CHECK_TECH
    
    CHECK_TECH{tech >= 1?} -->|Yes| ROUTE_TECH[Route to<br/>SQL_MODEL<br/>codellama:7b]
    CHECK_TECH -->|No| ROUTE_SIMPLE[Route to<br/>MODEL_NAME<br/>llama3.1:8b]
    
    ROUTE_COMPLEX --> END_MODEL([Return selected<br/>model])
    ROUTE_TECH --> END_MODEL
    ROUTE_SIMPLE --> END_MODEL
```

---

## Re-Ranking Logic

```mermaid
flowchart TD
    START([Question +<br/>Retrieved hits]) --> EXTRACT[Extract question<br/>terms]
    
    EXTRACT --> TFIDF[Calculate TF-IDF<br/>for each hit]
    TFIDF --> COSINE[Get cosine<br/>similarity scores]
    
    COSINE --> COMBINE[Combine scores<br/>0.65 x cosine<br/>+ 0.35 x TF-IDF]
    
    COMBINE --> DVA_BOOST{Is DVA Act<br/>content?}
    DVA_BOOST -->|MRCA| ADD_20[+0.20 boost]
    DVA_BOOST -->|DRCA/VEA| ADD_16[+0.16 boost]
    DVA_BOOST -->|Other| NO_BOOST[No boost]
    
    ADD_20 --> SORT[Sort by trust level<br/>then score]
    ADD_16 --> SORT
    NO_BOOST --> SORT
    
    SORT --> RETURN_RANKED([Return re-ranked<br/>hits])
```

---

## Source Selection Logic

```mermaid
flowchart TD
    START([Retrieved sources]) --> DEDUP_URL[Remove duplicate<br/>URLs]
    
    DEDUP_URL --> DEDUP_TITLE[Remove duplicate<br/>titles + source_type]
    DEDUP_TITLE --> BUCKET[Bucket by<br/>trust level]
    
    BUCKET --> WEIGHT[Apply trust level<br/>weights]
    WEIGHT --> ALLOC[Allocate slots<br/>per level]
    
    ALLOC --> FILL[Fill slots from<br/>each bucket]
    FILL --> SPARE[Add spare slots<br/>from remaining]
    SPARE --> MAX_CARDS{Max cards<br/>reached?}
    MAX_CARDS -->|Yes| RETURN_SOURCES
    MAX_CARDS -->|No| SPARE
    
    RETURN_SOURCES([Return weighted<br/>source citations])
```

---

## Scraper Flow

```mermaid
flowchart TD
    START([crawler.py<br/>max_pages]) --> SEEDS[Load seed URLs]
    
    SEEDS --> QUEUE[Add seeds to<br/>BFS queue]
    QUEUE --> POP{Pop URL<br/>from queue}
    
    POP --> VISITED{Already<br/>visited?}
    VISITED -->|Yes| CHECK_FRESH
    VISITED -->|No| CHECK_SCRAPE{Should scrape?<br/>7-day freshness}
    
    CHECK_SCRAPE -->|No| SKIP[Skip URL]
    CHECK_SCRAPE -->|Yes| SCRAPE_URL[Fetch with<br/>Playwright]
    
    CHECK_FRESH{Within 7 days?} -->|Yes| SKIP
    CHECK_FRESH -->|No| SCRAPE_URL
    
    SKIP --> CHECK_LIMIT{Max pages<br/>reached?}
    SCRAPE_URL --> EXTRACT[Extract text<br/>+ links]
    
    EXTRACT --> CHUNK[Chunk text<br/>2000 chars]
    CHUNK --> EMBED[Generate<br/>embeddings]
    
    EMBED --> DETECT_TYPE[Detect source type<br/>and trust level]
    DETECT_TYPE --> STORE[Store in database]
    
    STORE --> ADD_LINKS[Add extracted links<br/>to queue]
    ADD_LINKS --> CHECK_LIMIT
    
    CHECK_LIMIT -->|No| POP
    CHECK_LIMIT -->|Yes| DONE([Crawl complete])
```

---

## Data Storage Schema

```mermaid
erDiagram
    scraped_content {
        int id PK
        text title
        varchar source_type
        text source_url
        text page_text
        int chunk_index
        int chunk_total
        vector embedding
        vector embedding_mxbai
        smallint trust_level
        char content_hash
        timestamp last_scraped
    }
    
    query_audit_log {
        int log_id PK
        text question
        text answer_snippet
        jsonb sources_used
        smallintArray trust_levels
        boolean has_conflict
        boolean used_sql
        text debug_sql
        int source_count
        int latency_ms
        text error
        boolean user_flagged
        text flag_reason
        varchar model_used
        timestamp created_at
    }
    
    conversation_memory {
        int id PK
        varchar user_id
        text question
        text answer
        jsonb sources_cited
        float confidence_score
        boolean is_flagged
        text correction
        timestamp query_timestamp
        int log_id FK
    }
    
    scrape_seeds {
        int id PK
        text url UK
        text label
        varchar source_type
        varchar added_via
        boolean is_active
        int http_status
        text check_error
        int fail_count
        timestamp created_at
        timestamp last_checked
    }
    
    dva_acts {
        int id PK
        text act_name
        varchar act_code
        text description
        date effective_date
    }
    
    service_categories {
        int id PK
        text category_name
        int act_id FK
        text standard_of_proof
        text description
    }
    
    query_audit_log ||--o{ conversation_memory : "log_id"
    dva_acts ||--o{ service_categories : "act_id"
```

---

## Trust Level Hierarchy

| Level | Source | Weight | Description |
| ------- | -------- | -------- | ------------- |
| L1 | Federal Legislation | 0.25 | legislation.gov.au, rma.gov.au |
| L2 | CLIK Official | 0.30 | clik.dva.gov.au |
| L3 | DVA.gov.au / Gov | 0.20 | dva.gov.au, other .gov.au |
| L4 | Service Providers | 0.15 | Non-gov support sites |
| L5 | Community | 0.10 | Reddit, forums |

---

## Key Configuration

```yaml
# Environment Variables
MODEL_NAME: llama3.1:8b        # Primary chat model
MODEL_COMPLEX: qwen2.5:14b     # Complex reasoning
SQL_MODEL: codellama:7b         # SQL generation
SUMMARIZER_MODEL: qwen2.5:7b   # Context summarization
EMBEDDING_MODEL: mxbai-embed-large
LLM_CTX: 8192                   # Context window tokens
```

---

## System Load Monitoring

```mermaid
flowchart TD
    START([UI refresh<br/>every 2s]) --> DETECT_HW[Detect Hardware<br/>GPU/VRAM]
    
    DETECT_HW --> GPU_PRESENT{Has GPU?}
    
    GPU_PRESENT -->|Yes| GET_GPU[Get GPU util<br/>VRAM util<br/>Temperature]
    GPU_PRESENT -->|No| GET_CPU[Get CPU util<br/>Memory<br/>Disk]
    
    GET_GPU --> CHECK_VRAM{VRAM ≥85%?}
    GET_CPU --> WEIGHT_CPU[Set CPU weights<br/>50% CPU, 25% Mem<br/>20% Disk, 5% Net]
    
    CHECK_VRAM -->|Yes| WEIGHT_HIGH[High VRAM weights<br/>30% GPU, 25% VRAM<br/>15% CPU, 15% Disk]
    CHECK_VRAM -->|No| WEIGHT_NORMAL[Normal weights<br/>40% GPU, 15% VRAM<br/>20% CPU, 10% Disk]
    
    WEIGHT_CPU --> CALC_LOAD
    WEIGHT_HIGH --> CALC_LOAD
    WEIGHT_NORMAL --> CALC_LOAD
    
    CALC_LOAD[Calculate<br/>Weighted Load] --> OLLAMA_CHECK{Ollama<br/>Active?}
    
    OLLAMA_CHECK -->|Yes| BOOST_GPU[Boost GPU<br/>weight 20%]
    OLLAMA_CHECK -->|No| CHECK_THRESH
    
    BOOST_GPU --> CHECK_THRESH{Check<br/>Thresholds}
    
    CHECK_THRESH -->|2+ ≥90%| CAP_100[Cap at 100%]
    CHECK_THRESH -->|1 ≥92%| BOOST_LOAD[Boost 10%]
    CHECK_THRESH -->|Normal| RETURN_LOAD
    
    CAP_100 --> RETURN_LOAD([Return<br/>System Load])
    BOOST_LOAD --> RETURN_LOAD
    
    RETURN_LOAD --> COLOR[Apply Color<br/>Green/Yellow<br/>Orange/Red]
    COLOR --> RENDER([Render bar chart<br/>in UI])
```

### Weight Schemas

| Scenario | GPU | VRAM | CPU | Memory | Disk | Network |
|----------|-----|------|-----|--------|------|---------|
| GPU Normal | 40% | 15% | 20% | 10% | 10% | 5% |
| GPU High VRAM | 30% | 25% | 15% | 10% | 15% | 5% |
| CPU Only | 0% | 0% | 50% | 25% | 20% | 5% |

### Thresholds

| Level | Threshold | Color | Warning |
|-------|-----------|-------|---------|
| Safe | ≤50% | Green (#22c55e) | None |
| Caution | 51-70% | Yellow (#ffef00) | None |
| Warning | 71-90% | Orange (#f97316) | None |
| Critical | >90% | Red (#ef4444) | GPU hot, VRAM/Mem/CPU critical |

### Task-Bound Detection

When a specific hardware resource becomes the bottleneck, the system detects it and applies 95% weight to that component via ramping:

```mermaid
flowchart TD
    START([Metrics]) --> CHECK_OLLAMA{Ollama<br/>Active?}
    
    CHECK_OLLAMA -->|Yes| CHECK_GPU70{GPU ≥70%?}
    CHECK_OLLAMA -->|No| CHECK_VRAM90
    
    CHECK_GPU70 -->|Yes| TASK_GPU[Task: GPU-Bound]
    CHECK_GPU70 -->|No| CHECK_VRAM90
    
    CHECK_VRAM90{VRAM ≥90%} -->|Yes| TASK_VRAM[Task: VRAM-Bound]
    CHECK_VRAM90 -->|No| CHECK_CPU85
    
    CHECK_CPU85{CPU ≥85%<br/>GPU <50%} -->|Yes| TASK_CPU[Task: CPU-Bound]
    CHECK_CPU85 -->|No| CHECK_DISK80
    
    CHECK_DISK80{Disk ≥80%<br/>CPU <70%} -->|Yes| TASK_DISK[Task: Disk-Bound]
    CHECK_DISK80 -->|No| CHECK_NET70
    
    CHECK_NET70{Net ≥70%<br/>GPU/CPU <50%} -->|Yes| TASK_NET[Task: Network-Bound]
    CHECK_NET70 -->|No| TASK_NONE[Task: None]
    
    TASK_GPU --> RAMP[Add to<br/>task_history]
    TASK_VRAM --> RAMP
    TASK_CPU --> RAMP
    TASK_DISK --> RAMP
    TASK_NET --> RAMP
    TASK_NONE --> RAMP
    
    RAMP --> RAMP_CALC{Count ≥3?<br/>3 refreshes}
    RAMP_CALC -->|Yes| FACTOR_95[95% emphasis]
    RAMP_CALC -->|No| FACTOR_RAMP[Proportional<br/>ramping]
    
    FACTOR_95 --> BLEND[Blend weights<br/>base → task]
    FACTOR_RAMP --> BLEND
    
    BLEND --> APPLY[Apply to<br/>System Load]
```

### Task Detection Triggers

| Detected Task | Trigger Condition |
|---------------|------------------|
| GPU-Bound | Ollama active + GPU ≥70% |
| VRAM-Bound | VRAM ≥90% |
| CPU-Bound | CPU ≥85% + GPU <50% |
| Disk I/O-Bound | Disk ≥80% + CPU <70% |
| Network-Bound | Network ≥70% + GPU/CPU <50% |

**Ramping:** Weight emphasis ramps from 0% → 95% over 3 refresh cycles (6 seconds).

---

## File Purposes

| File | Purpose |
| ------ | --------- |
| `main.py` | Core RAG pipeline, query processing, LLM invocation |
| `ui.py` | Streamlit UI, user interaction handling |
| `scraper.py` | Web crawling, content extraction, embedding generation |
| `model_manager.py` | Hardware detection, model recommendations |
| `sql_generator.py` | Natural language to SQL conversion |
| `context_summarizer.py` | Context compression for large contexts |
| `health.py` | System health checks |
| `reembed.py` | Re-embedding existing content with new models |
| `init.sql` | Database schema initialization |
