# DVA Wizard v3.0 - Logic Flow Summary

## High-Level Architecture

```mermaid
flowchart TD
    subgraph Client[User Interface]
        REACT[React SPA<br/>:8501]
    end
    
    subgraph Nginx[Reverse Proxy]
        NGINX[dva-web<br/>Nginx]
    end
    
    subgraph API_Service[API Container<br/>dva-api]
        FASTAPI[FastAPI<br/>Endpoints]
    end
    
    subgraph Web_App[Web Container<br/>dva-web]
        MAIN[main.py<br/>RAG Pipeline]
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
    
    REACT -->|HTTP| NGINX
    NGINX -->|Proxy /api| FASTAPI
    FASTAPI --> MAIN
    MAIN --> PG
    MAIN --> LLM
    MAIN --> EMBEDD
    SCRAPER --> PG
    SCRAPER --> EMBEDD
```

---

## Frontend-Backend Communication

```mermaid
sequenceDiagram
    participant React as React UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Ollama as Ollama

    Note over React: System Status polls<br/>every 2 seconds
    
    React->>API: GET /api/system-status
    API->>API: Gather GPU/CPU/VRAM metrics
    API-->>React: {gpu: 45, vram: 62, cpu: 23, ...}
    React->>React: Update status panel
    
    loop Every 2 seconds
        React->>API: GET /api/system-status
        API-->>React: Updated metrics
    end
    
    Note over React: User sends message
    
    React->>API: POST /api/chat {message: "..."}
    API->>API: prepare_rag_context()
    API->>DB: Execute SQL query
    API->>DB: Vector search (pgvector)
    API->>Ollama: Generate embedding
    Ollama-->>API: Embedding vector
    
    API->>Ollama: Generate answer
    Ollama-->>API: Answer text
    
    API-->>React: {answer: "...", sources: [...], model: "..."}
    React->>React: Display message + sources
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

## Real-Time Status Polling

```mermaid
flowchart TD
    START([Page Load]) --> INIT[Initialize polling<br/>timer]
    
    INIT --> WAIT{Wait 2 seconds}
    WAIT --> FETCH[Fetch /api/system-status]
    FETCH --> PARSE[Parse JSON<br/>GPU/VRAM/CPU/Mem]
    PARSE --> RENDER[Render metrics<br/>in sidebar]
    
    RENDER --> WAIT
    
    style START fill:#e3f2fd,stroke:#1565c0
    style FETCH fill:#e8f5e9,stroke:#2e7d32
    style RENDER fill:#fff3e0,stroke:#ef6c00
```

---

## System Load Calculation

```mermaid
flowchart TD
    START([Metrics]) --> CHECK_HARDWARE{Has GPU?}
    
    CHECK_HARDWARE -->|Yes| GPU_WEIGHTS[Apply GPU weights<br/>GPU:40% VRAM:15%<br/>CPU:20% Mem:10%]
    CHECK_HARDWARE -->|No| CPU_WEIGHTS[Apply CPU weights<br/>CPU:50% Mem:25%<br/>Disk:20% Net:5%]
    
    GPU_WEIGHTS --> CHECK_TASK{Detect task<br/>bottleneck?}
    CPU_WEIGHTS --> CHECK_TASK
    
    CHECK_TASK -->|GPU-Bound| EMPHASIS_GPU[95% GPU<br/>weight]
    CHECK_TASK -->|VRAM-Bound| EMPHASIS_VRAM[95% VRAM<br/>weight]
    CHECK_TASK -->|CPU-Bound| EMPHASIS_CPU[95% CPU<br/>weight]
    CHECK_TASK -->|None| NO_EMPHASIS[No<br/>emphasis]
    
    EMPHASIS_GPU --> CALC_LOAD
    EMPHASIS_VRAM --> CALC_LOAD
    EMPHASIS_CPU --> CALC_LOAD
    NO_EMPHASIS --> CALC_LOAD
    
    CALC_LOAD[Calculate<br/>weighted load] --> COLOR[Determine<br/>color code]
    
    COLOR -->|≤50%| GREEN[Green #22c55e]
    COLOR -->|51-70%| YELLOW[Yellow #eab308]
    COLOR -->|71-90%| ORANGE[Orange #f97316]
    COLOR -->|>90%| RED[Red #ef4444]
    
    GREEN --> RETURN([Return to UI])
    YELLOW --> RETURN
    ORANGE --> RETURN
    RED --> RETURN
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
| --- | --- | --- | --- |
| L1 | Federal Legislation | 0.25 | legislation.gov.au, rma.gov.au |
| L2 | CLIK Official | 0.30 | clik.dva.gov.au |
| L3 | DVA.gov.au / Gov | 0.20 | dva.gov.au, other .gov.au |
| L4 | Service Providers | 0.15 | Non-gov support sites |
| L5 | Community | 0.10 | Reddit, forums |

---

## API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/system-status` | GET | Real-time system metrics (GPU, CPU, VRAM) |
| `/api/chat` | POST | Send chat message, receive answer |
| `/api/common-questions` | GET | Get FAQ questions by category |
| `/api/knowledge-stats` | Get | Get knowledge base statistics |
| `/api/health` | GET | Health check |

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

## File Purposes

| File | Purpose |
| --- | --- |
| `main.py` | Core RAG pipeline, query processing, LLM invocation |
| `api.py` | FastAPI endpoints for React frontend integration |
| `scraper.py` | Web crawling, content extraction, embedding generation |
| `model_manager.py` | Hardware detection, model recommendations |
| `sql_generator.py` | Natural language to SQL conversion |
| `context_summarizer.py` | Context compression for large contexts |
| `health.py` | System health checks |
| `reembed.py` | Re-embedding existing content with new models |
| `init.sql` | Database schema initialization |

### Frontend Files

| File | Purpose |
| --- | --- |
| `frontend/src/App.js` | Main React application |
| `frontend/src/components/SystemStatus.js` | Real-time status panel (2s refresh) |
| `frontend/src/components/Chat.js` | Chat interface |
| `frontend/src/components/Sidebar.js` | Common questions + settings |
| `frontend/nginx.conf` | Reverse proxy configuration |
