# 🎖️ DVA Wizard v3.0

> **Enhanced RAG system with multi-model routing, hardware-adaptive model selection, and React-based real-time dashboard**

[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://www.python.org/)
[![React](https://img.shields.io/badge/UI-React_18-blue)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-blue)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama_0.6.1-purple)](https://ollama.com/)

**Author:** Ben Reay

---

## Overview

The **DVA Wizard v3.0** is a Retrieval-Augmented Generation (RAG) system that lets veterans query DVA legislation, policy, and support services in plain language. Every component runs locally inside Docker — no cloud APIs, no data leaving the network.

### Key Features (v3.0)

- **Real-time Dashboard** - React-based UI with System Status refreshing every 2 seconds
- **Independent Panels** - Chat and sidebar work independently without interfering
- **Multi-model routing** - Automatically selects optimal model based on query complexity
- **Hardware detection** - Auto-detects GPU and recommends optimal models
- **Improved embeddings** - Support for mxbai-embed-large (1024-dim) 
- **Context summarization** - qwen2.5:7b compresses context to fit more relevant content
- **SQL specialist** - codellama:7b generates more accurate database queries
- **Session memory** - Remembers veteran's context (service, conditions) within session
- **Duplicate question detection** - Avoids re-inference for repeated questions
- **Recent questions context** - Uses last 100 questions to improve response relevance

The system combines two retrieval strategies:
- **Text-to-SQL** for structured queries (Acts, service categories, standards of proof)
- **Semantic vector search** (pgvector) for policy and knowledge

A lexical + semantic **re-ranker** ensures the most relevant content per trust level appears first in the LLM context window.

### Source Authority Tiers

| Level | Source | Domain(s) | Notes |
| --- | --- | --- | --- |
| **L1** | Federal Legislation | legislation.gov.au, rma.gov.au | Binding law and Statements of Principles |
| **L2** | CLIK Official | clik.dva.gov.au | Binding compensation policy interpretation |
| **L3** | DVA.gov.au | dva.gov.au (non-CLIK) | Official DVA informational pages |
| **L3** | Government Other | Other .gov.au | Non-DVA government sources |
| **L4** | Service Providers | Non-gov domains | Advocacy and support organisations |
| **L5** | Community | reddit.com/r/DVAAustralia | User posts — always verify against L1–L3 |

---

## ⚖️ DVA Legislation Hierarchy — MRCA Primacy from 1 July 2026

| Act | Full Name | Relevance from 1 July 2026 |
| --- | --- | --- |
| **MRCA** | Military Rehabilitation and Compensation Act 2004 | **Primary Act** — all new compensation and rehabilitation claims |
| **DRCA** | Safety, Rehabilitation and Compensation (Defence-related Claims) Act 1988 | Legacy claims lodged before 1 July 2026 |
| **VEA** | Veterans' Entitlements Act 1986 | Legacy claims; pensions and income-support payments |

The system applies MRCA priority through re-ranker boosts and LLM prompt instructions.

---

## Architecture

```mermaid
graph TD
    subgraph Client[User Interface]
        REACT[React SPA<br/>:8501]
    end
    
    subgraph Docker_Stack [Docker Compose Stack]
        direction TB
        subgraph App_Services [Application Services]
            direction LR
            WEB[dva-web<br/>React + Nginx<br/>Real-time Dashboard]
            API[dva-api<br/>FastAPI<br/>Chat + Status API]
            SCR[dva-scraper<br/>Crawler +<br/>Embeddings]
            SCH[dva-scheduler<br/>Ofelia cron]
        end

        DB[(dva-db<br/>PostgreSQL 15<br/>+ pgvector)]
        OLL[ollama<br/>Ollama Docker<br/>GPU pass-through]

        REACT -->|HTTP/WebSocket| WEB
        WEB -->|Proxy /api| API
        API --> DB
        API --> OLL
        SCR --> DB
        SCR --> OLL
        SCH --> SCR
    end

    style Docker_Stack fill:#f9f9f9,stroke:#333,stroke-width:2px
    style DB fill:#e1f5fe,stroke:#01579b
    style OLL fill:#f3e5f5,stroke:#4a148c
    style REACT fill:#e3f2fd,stroke:#1565c0
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant React as React UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Ollama as Ollama

    Note over React: System Status polls<br/>every 2 seconds
    
    React->>API: GET /api/system-status
    API->>API: Gather metrics
    API-->>React: {gpu, vram, cpu, ...}
    
    User->>React: Send message
    React->>API: POST /api/chat
    API->>DB: SQL + Vector search
    DB-->>API: Results
    
    API->>Ollama: Generate embedding
    Ollama-->>API: Embedding
    
    API->>Ollama: Generate answer
    Ollama-->>API: Answer
    
    API-->>React: {answer, sources, model}
    React->>User: Display response
```

### Services

| Container | Image | Purpose |
| --- | --- | --- |
| `ollama` | `ollama/ollama:0.6.1` | LLM inference + embeddings (GPU-accelerated) |
| `dva-db` | `pgvector/pgvector:pg15` | PostgreSQL 15 + pgvector extension |
| `dva-web` | `dva-wizard-web` | React UI served by Nginx |
| `dva-api` | `dva-wizard-api` | FastAPI for Chat + System Status polling |
| `dva-scraper` | `dva-wizard-scraper` | Multi-source web crawler |
| `dva-scheduler` | `mcuadros/ofelia:0.3.10` | Scheduled monthly scrape jobs |

---

## Features

| Feature | Description |
| --- | --- |
| Real-time System Status | GPU/CPU/VRAM/Memory updates every 2 seconds |
| Multi-source knowledge base | CLIK, DVA.gov.au, legislation.gov.au, Support sites |
| Multi-model routing | Auto-selects optimal model by query complexity |
| Hardware detection | GPU detection with model recommendations |
| System Load thresholds | Color-coded warnings: ≤50% green, 51-70% yellow, 71-90% orange, >90% red |
| Hardware-adaptive weights | Dynamic weighting adjusts based on GPU availability and VRAM pressure |
| Task-bound detection | Detects GPU/CPU/VRAM/Disk/Network-bound tasks and applies 95% weight to bottleneck |
| Task-aware ramping | Weight emphasis ramps up over 2-3 refresh cycles for smooth transitions |
| Ollama activity detection | Shows when Ollama is processing requests |
| GPU temperature monitoring | Warning when GPU temp ≥80°C |
| Common veteran questions | Top 50 FAQ for improved semantic search |
| Statement vs. question classification | Personal context acknowledged without LLM call |
| Session context memory | Remembers veteran-provided context within session |
| Persistent Q&A memory | Stores Q&A pairs in database for retrieval |
| Lexical + semantic re-ranking | TF-IDF + cosine similarity |
| DVA Acts priority boost | MRCA, DRCA, VEA content boosted |
| Conflict detection | Authoritative vs community source disagreement |
| Full audit log | Every query logged with flag support |
| Change-detection scraping | SHA-256 hash skips unchanged pages |
| Freshness skip | 7-day check before re-scraping |
| Legislation currency | /asmade rewritten to /latest |
| **Monthly scheduled scraping** | Auto-scrapes 200 pages on 1st of each month at 2 AM |

---

## Prerequisites

### Hardware

* **GPU**: NVIDIA GTX 1060 6 GB minimum (CPU-only possible but slower)
* **RAM**: 16 GB minimum
* **Disk**: 20 GB free

### Operating System

| OS | Status |
| --- | --- |
| **Windows 11** | ✅ WSL 2 + Docker Desktop |
| **macOS** | ✅ CPU-only |
| **Linux** | ✅ Ubuntu 20.04+ |

---

## Quick Start

### 1. Clone and Setup

```powershell
git clone https://github.com/Overlawd/dva_wizard_v3.git G:\projects\dva_wizard_v3
cd G:\projects\dva_wizard_v3
```

### 2. Configure Environment

```powershell
Rename-Item "_env" ".env"
```

Edit `.env`:

```env
DATABASE_URL=postgresql://postgres:vets_secure_pw@db:5432/dva_db
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=llama3.1:8b
MODEL_COMPLEX=qwen2.5:14b
SQL_MODEL=codellama:7b
SUMMARIZER_MODEL=qwen2.5:7b
EMBEDDING_MODEL=mxbai-embed-large
EMBEDDING_DIM=1024
LLM_CTX=8192
```

### 3. Initialize Database

```powershell
New-Item -ItemType Directory -Path ".\initdb" -Force
Copy-Item ".\app\init.sql" ".\initdb\init.sql"
```

### 4. Build and Start Stack

> **Important:** The web container requires GPU access for optimal performance. The docker-compose.yml includes GPU passthrough configuration.

```bash
docker compose build
docker compose up -d
```

> **First-time setup:** After containers start, verify GPU is detected in the UI sidebar. If it shows "CPU only", check that NVIDIA drivers are installed and Docker Desktop has GPU access enabled.

### 5. Pull Models

```bash
docker exec dva-ollama ollama pull llama3.1:8b
docker exec dva-ollama ollama pull qwen2.5:14b
docker exec dva-ollama ollama pull codellama:7b
docker exec dva-ollama ollama pull qwen2.5:7b
docker exec dva-ollama ollama pull mxbai-embed-large
```

### 6. Open UI

Navigate to [http://localhost:8501](http://localhost:8501)

---

## Project Structure

```
dva_wizard_v3/
├── .env                          ← environment config
├── _env                          ← environment template
├── docker-compose.yml            ← container orchestration
├── admin_tasks.ps1               ← Admin console (Windows)
├── backups/                      ← Backup storage
├── initdb/
│   └── init.sql                  ← Database schema
├── app/
│   ├── main.py                   ← Core RAG pipeline
│   ├── api.py                    ← FastAPI endpoints (Chat + Status)
│   ├── scraper.py                ← Web crawler
│   ├── model_manager.py           ← Hardware detection
│   ├── sql_generator.py           ← SQL generation
│   ├── context_summarizer.py      ← Context compression
│   ├── reembed.py                 ← Embedding reindexing
│   ├── health.py                  ← Health checks
│   ├── veteran_faq.py             ← Common veteran questions
│   ├── migrate.py                 ← Schema verification
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── App.js                 ← Main React app
    │   ├── components/
    │   │   ├── SystemStatus.js    ← Real-time status (2s refresh)
    │   │   ├── Chat.js            ← Chat interface
    │   │   └── Sidebar.js         ← Common questions + settings
    │   └── App.css
    ├── public/
    │   └── index.html
    ├── package.json
    ├── nginx.conf
    └── Dockerfile
```

---

## Configuration Reference

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection | postgresql://postgres:...@db:5432/dva_db |
| `OLLAMA_BASE_URL` | Ollama API | http://ollama:11434 |
| `MODEL_NAME` | Chat model | llama3.1:8b |
| `MODEL_COMPLEX` | Reasoning model | qwen2.5:14b |
| `SQL_MODEL` | SQL model | codellama:7b |
| `SUMMARIZER_MODEL` | Summarizer model | qwen2.5:7b |
| `EMBEDDING_MODEL` | Embeddings | mxbai-embed-large |
| `LLM_CTX` | Context window | 8192 |

---

## Scheduled Scraping

The `dva-scheduler` container runs automatic monthly scrapes using [Ofelia](https://github.com/mcuadros/ofelia):

| Setting | Value |
| --- | --- |
| Schedule | Monthly on the 1st at 2:00 AM |
| Command | `python scraper.py 200 --force` |
| Pages | 200 (ignores 7-day freshness check) |
| Container | dva-scraper |

### Viewing Scheduler Logs

```bash
# View scheduler logs
docker logs dva-scheduler

# View when jobs last ran
docker logs dva-scheduler | grep "Job"
```

### Manual Trigger

To trigger a scrape manually:

```bash
docker exec dva-scraper python scraper.py 200 --force
```

## Hardware-Adaptive Models

| VRAM | Chat | Reasoning | SQL | Embeddings |
| --- | --- | --- | --- | --- |
| 0-4 GB | phi3:3.8b-mini | phi3:3.8b-mini | phi3:3.8b-mini | nomic-embed-text |
| 4-6 GB | llama3.1:8b | qwen2.5:14b | codellama:7b | mxbai-embed-large |
| 6-8 GB | llama3.1:8b | qwen2.5:14b | codellama:7b | mxbai-embed-large |
| 8-12 GB | llama3.1:8b | qwen2.5:14b | codellama:7b | mxbai-embed-large |
| 12+ GB | llama3.1:8b | deepseek-coder-v2:236b | codellama:7b | mxbai-embed-large |

---

## Real-Time System Status

The React dashboard includes a **System Status** panel that updates every 2 seconds without interrupting chat or other interactions:

```mermaid
flowchart TD
    START([Page Load]) --> POLL[Start 2s polling]
    POLL --> FETCH[Fetch /api/system-status]
    FETCH --> RENDER[Render metrics in sidebar]
    RENDER --> WAIT[Wait 2 seconds]
    WAIT --> FETCH
```

### System Load Display

| Load Range | Color | Hex |
| --- | --- | --- |
| ≤50% | Green | #22c55e |
| 51-70% | Canary Yellow | #eab308 |
| 71-90% | Orange | #f97316 |
| >90% | Red | #ef4444 |

### Dynamic Weighting

System load uses hardware-adaptive weights:

| Scenario | GPU | VRAM | CPU | Memory | Disk | Network |
| --- | --- | --- | --- | --- | --- | --- |
| GPU available (normal) | 40% | 15% | 20% | 10% | 10% | 5% |
| GPU available (high VRAM ≥85%) | 30% | 25% | 15% | 10% | 15% | 5% |
| CPU only | 0% | 0% | 50% | 25% | 20% | 5% |

### Task-Bound Detection

When a specific hardware resource becomes the bottleneck, the system detects it and applies 95% weight to that component:

| Detected Task | Trigger Condition | UI Display |
| --- | --- | --- |
| GPU-Bound | Ollama active + GPU ≥70% | "GPU-Bound (embedding/inference)" |
| VRAM-Bound | VRAM ≥90% | "VRAM-Bound (memory pressure)" |
| CPU-Bound | CPU ≥85% + GPU <50% | "CPU-Bound (processing)" |
| Disk I/O-Bound | Disk ≥80% + CPU <70% | "Disk I/O-Bound" |
| Network-Bound | Network ≥70% + GPU/CPU <50% | "Network-Bound" |

### Warnings

Warnings appear when thresholds are exceeded:

| Warning | Threshold | Behavior |
| --- | --- | --- |
| GPU hot | GPU Temp ≥80°C | Shows warning, dismissible for 30s |
| VRAM critical | VRAM ≥90% | Shows warning with ✕ button, dismissible for 30s |
| Memory critical | Memory ≥90% | Shows warning, dismissible for 30s |
| CPU critical | CPU ≥90% | Shows warning, dismissible for 30s |

### Model Suggestions

The System Status section includes an expandable **Model Suggestion** panel that:

- Automatically detects available VRAM
- Suggests optimal model based on VRAM (14b, 8b, 7b, or codellama)
- Recommends upgrade if current model doesn't fit
- Works with hardware upgrades (e.g., 6GB → 12GB GPU)

| Available VRAM | Suggested Model |
| --- | --- |
| ≥10 GB | qwen2.5:14b |
| ≥6 GB | llama3.1:8b |
| ≥5.5 GB | qwen2.5:7b |
| ≥5 GB | codellama:7b |
| <5 GB | llama3.1:8b (or reduce embeddings) |

---

## Admin Console (`admin_tasks.ps1`)

```powershell
.\admin_tasks.ps1
```

The admin console provides a menu-driven interface for managing the DVA Assistant stack.

### Main Menu

| Option | Description |
| --- | --- |
| [1] Start / Restart Application | Start/Stop/Restart (dynamic based on status) |
| [2] GPU Settings | View stats, test GPU, toggle GPU mode |
| [3] Model Management | List/pull/delete models, switch active model |
| [4] Data Management | Backup/restore, database utilities |
| [5] Diagnostics | Container status, API tests, view logs |

---

### Application Control (Option 1)

When application is **running**:

| Sub-Option | Description |
| --- | --- |
| [1] Restart All | Stop all, then start all |
| [2] Rolling restart | Restart without stopping |
| [3] Restart specific service | Restart one container |
| [4] Rebuild and restart | Rebuild images, then start |
| [5] Stop Application | Stop all containers |

When application is **not running**:

| Sub-Option | Description |
| --- | --- |
| [1] Start Application | Start all containers |

| Sub-Option | Description |
| --- | --- |
| [1] View GPU Statistics | Real-time GPU stats (utilization, memory, temperature, power). Press R to refresh, any key to exit. |
| [2] Test GPU in Docker | Verifies GPU is accessible from within Docker containers. Auto-pulls CUDA image on first run. |
| [3] View NVIDIA Driver | Shows installed driver version and compute capability |
| [4] Toggle GPU Mode | Enable/disable GPU acceleration in docker-compose.yml. Requires restart to take effect. |

---

### Manage Models (Option 3)

| Sub-Option | Description |
| --- | --- |
| [1] List Installed | Shows all Ollama models currently pulled |
| [2] Pull Model | Download a new model from Ollama library |
| [3] Delete Model | Remove a model to free disk space |
| [4] Switch Model | Change active model for chat/reasoning/SQL/summarization/embeddings |

#### Available Models (configured in .env)

| Model Type | Variable | Default | Purpose |
| --- | --- | --- | --- |
| Chat | MODEL_NAME | llama3.1:8b | General conversation |
| Reasoning | MODEL_COMPLEX | qwen2.5:14b | Complex queries |
| SQL | SQL_MODEL | codellama:7b | Database queries |
| Summarizer | SUMMARIZER_MODEL | qwen2.5:7b | Context compression |
| Embeddings | EMBEDDING_MODEL | mxbai-embed-large | Vector search (1024-dim) |

---

### Data Management (Option 4)

| Sub-Option | Description |
| --- | --- |
| [1] Create Backup | Saves database to `backups/` folder with timestamp |
| [2] List Backups | Shows available backup folders and dates |
| [3] Restore | Restores database from a backup folder |
| [4] Delete Old | Removes backups older than 30 days |
| [5] Database Utilities | Run tests, scraper, reembed tool |

#### Database Utilities (within Data Management)

| Sub-Option | Description |
| --- | --- |
| [1] Test Import | Verifies Python modules load correctly |
| [2] Run Scraper | Scrapes 100 pages (respects 7-day freshness) |
| [3] Force Scrape | Scrapes 3000 pages ignoring freshness |
| [4] Run Reembed | Migrates embeddings with real-time progress |
| [5] Content Stats | Shows scraped content by source type |
| [6] Verify Reembed | Check migration status (rows embedded) |
| [7] Create Index | Create HNSW index for faster vector search |

---

### Diagnostic (Option 5)

| Sub-Option | Description |
| --- | --- |
| Status | Shows all container statuses (ollama, db, web, scraper) |
| Ollama Test | Verifies API connectivity and lists models |
| Database Test | Checks connection and content count |
| Disk Space | Shows available drive space |
| [V] View Logs | Tail container logs in real-time |

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| dva-db not healthy | `docker compose down -v && docker compose up -d` |
| Ollama not responding | `docker compose restart ollama` |
| Models not found | `docker exec dva-ollama ollama pull <model>` |
| UI won't load | `docker compose restart web` |
| API not responding | `docker compose restart api` |
| GPU shows "CPU only" | 1. Install NVIDIA driver 2. Restart Docker Desktop 3. Rebuild web: `docker compose build web` |
| nvidia-smi fails in container | Install NVIDIA Container Toolkit or use Docker Desktop with WSL 2 |

### API Health Check

```bash
# Test API health
curl http://localhost:8502/api/health

# Test system status
curl http://localhost:8502/api/system-status

# Test chat endpoint
curl -X POST http://localhost:8502/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is MRCA?"}'
```

### GPU Configuration

The docker-compose.yml includes GPU passthrough for both the `ollama` and `api` containers. If GPU is not detected:

1. **Windows:** Ensure NVIDIA drivers are installed and Docker Desktop has WSL 2 integration enabled
2. **Linux:** Install NVIDIA Container Toolkit: `nvidia-ctk runtime configure --runtime=docker`

Verify GPU access:
```bash
docker exec dva-api nvidia-smi
```

---

## Database Schema

### Tables

| Table | Purpose |
| --- | --- |
| `scraped_content` | Crawled pages with embeddings |
| `dva_acts` | VEA, MRCA, DRCA reference |
| `service_categories` | Service types and standards |
| `query_audit_log` | Query history with flags |
| `conversation_memory` | Persistent Q&A pairs |
| `scrape_seeds` | Seed URLs |
| `scrape_log` | Scrape job history |

---

## Security

| Control | Status |
| --- | --- |
| All inference local | ✅ |
| Docker network isolation | ✅ |
| SQL injection prevention | ✅ |
| Query audit logging | ✅ |

---

## Future Improvements

The following enhancements are planned or under consideration for future releases:

### High Priority

| # | Improvement | Description |
| --- | --- | --- |
| 1 | **Vector Index Optimization** | Implement HNSW index for faster similarity search at scale |
| 2 | **Incremental Embedding** | Only embed new/changed content instead of full reembed |
| 3 | **Query Caching** | Cache frequent queries to reduce LLM API calls |
| 4 | **Better Error Handling** | Graceful degradation when Ollama models unavailable |

### Medium Priority

| # | Improvement | Description |
| --- | --- | --- |
| 5 | **Multi-user Support** | User authentication and personalized history |
| 6 | **Citation Verification** | Auto-verify links are still active |
| 7 | **Model Hot-swap** | Switch models without container restart |
| 8 | **Export Chat History** | Download conversation as PDF/Markdown |

### Low Priority / Experimental

| # | Improvement | Description |
| --- | --- | --- |
| 9 | **Voice Input** | Speech-to-text for accessibility |
| 10 | **RAG Fine-tuning** | Fine-tune embeddings on veteran Q&A data |
| 11 | **Agentic Scraping** | LLM-guided intelligent crawling |
| 12 | **Metrics Dashboard** | Historical system load graphs |

---

## API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/system-status` | GET | Real-time system metrics (GPU, CPU, VRAM, etc.) |
| `/api/chat` | POST | Send a chat message and get response |
| `/api/common-questions` | GET | Get common veteran questions by category |
| `/api/knowledge-stats` | GET | Get knowledge base statistics |
| `/api/health` | GET | Health check endpoint |

---

**Version:** 3.0
**Last updated:** March 2026
**Author:** Ben Reay
