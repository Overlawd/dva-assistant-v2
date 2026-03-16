# DVA Wizard v3.0 - Quick Start Guide

Get up and running in under 10 minutes!

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- [Git](https://git-scm.com/) installed
- NVIDIA GPU recommended (works on CPU but slower)

---

## Step 1: Get the Code

```powershell
git clone https://github.com/Overlawd/dva_wizard_v3.git G:\projects\dva_wizard_v3
cd G:\projects\dva_wizard_v3
```

---

## Step 2: Configure

```powershell
Rename-Item "_env" ".env"
```

That's it! The default settings work for most setups.

---

## Step 3: Set Up Database

> **Note:** The database initialization script is already in place. If this is a fresh setup, ensure the initdb folder exists:

```powershell
New-Item -ItemType Directory -Path ".\initdb" -Force -ItemType Directory
# The init.sql file should already be present from the repository
dir .\initdb
```

If `initdb/init.sql` is missing, copy it from a backup or the original source.

---

## Step 4: Start Docker Stack

```powershell
docker compose build
docker compose up -d
```

Wait ~30 seconds for containers to start, then check status:

```powershell
docker ps
```

You should see 5-6 containers running:

- dva-ollama
- dva-db  
- dva-web
- dva-api (for System Status polling)
- dva-scraper
- dva-scheduler (automatic monthly scraping)

---

## Step 5: Pull AI Models

This takes 5-15 minutes depending on your internet:

```powershell
docker exec dva-ollama ollama pull llama3.1:8b
docker exec dva-ollama ollama pull qwen2.5:14b
docker exec dva-ollama ollama pull codellama:7b
docker exec dva-ollama ollama pull qwen2.5:7b
docker exec dva-ollama ollama pull mxbai-embed-large
```

---

## Step 6: Test It

Open your browser to: **http://localhost:8501**

In the sidebar, you should see:
- **📊 System Status** - Real-time system metrics (GPU, VRAM, Temp)
- **❓ Common Questions** - Expandable panel with common veteran queries
- **⚙️ Settings** - Session info and knowledge base stats

The v3.0 UI has a single-page dashboard layout:
- Main area: Chat interface
- Sidebar: Collapsible panels for System Status, Questions, Settings

### Session Memory

The assistant remembers context within your session:
- **Statements** (e.g., "I served in the Army") are stored and used in future responses
- **Questions** and answers are tracked for context continuity
- Last 100 questions are used to improve response relevance

Try this:
1. First, tell it something: "I served in the Army as a rifleman"
2. Then ask: "What compensation am I entitled to?"

The assistant will use your service context to provide relevant answers.

### Duplicate Question Detection

If you ask the same question twice:
1. The question displays in chat
2. System asks: "You just asked me that. If you'd like me to say it again, just say yes..."
3. Say "yes" to repeat the answer without re-inference

This saves time and GPU resources.

### Browser Refresh Warning

A warning appears when refreshing the browser to prevent accidental data loss.

---

## Optional: Populate Knowledge Base

```powershell
# Quick test (50 pages)
docker exec dva-scraper python scraper.py 50

# Full crawl (takes hours)
docker exec dva-scraper python scraper.py 300 --force
```

---

## Common Commands

| Command | Description |
| --------- | ------------- |
| `docker compose restart` | Restart all services |
| `docker compose logs -f` | View live logs |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop and delete data |

---

## Admin Tasks

On Windows, run the admin console:

```powershell
.\admin_tasks.ps1
```

The admin console provides menu-driven access to:
- Start / Restart Application (adapts based on status)
- GPU Settings
- Model Management
- Data Management
- Diagnostics

---

## Troubleshooting

**Container won't start:**

```powershell
docker compose logs <service-name>
```

**Database issues:**

```powershell
docker compose down -v
docker compose up -d
```

**GPU not detected / shows CPU only:**

1. Install NVIDIA driver and restart computer
2. Restart Docker Desktop  
3. Rebuild web container: `docker compose build web`

Verify GPU access:
```powershell
docker exec dva-web nvidia-smi
```

If GPU is working, you'll see your graphics card in the output.

---

## Need Help?

- Check README.md for full documentation
- Use Admin Console [5] for diagnostics
- Check container logs: `docker logs dva-web`
