# DVA Assistant - Quick Start Guide

Get up and running in under 10 minutes!

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- [Git](https://git-scm.com/) installed
- NVIDIA GPU recommended (works on CPU but slower)

---

## Step 1: Get the Code

```powershell
git clone <repo-url> C:\projects\dva-assistant
cd C:\projects\dva-assistant
```

---

## Step 2: Configure

```powershell
Rename-Item "_env" ".env"
```

That's it! The default settings work for most setups.

---

## Step 3: Set Up Database

```powershell
New-Item -ItemType Directory -Path ".\initdb" -Force
Copy-Item ".\app\init.sql" ".\initdb\init.sql"
```

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
- dva-scheduler (optional - for scheduled scraping)

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
- **System Load** - Real-time system metrics (GPU, VRAM, Temp, Net)
- **Common Questions** - Click to quick-start common veteran queries

The System Status updates automatically when you interact with the page.

### Session Memory

The assistant remembers context within your session:
- **Statements** (e.g., "I served in the Army") are stored and used in future responses
- **Questions** and answers are tracked for context continuity

Try this:
1. First, tell it something: "I served in the Army as a rifleman"
2. Then ask: "What compensation am I entitled to?"

The assistant will use your service context to provide relevant answers.

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
- Restart Application
- GPU Management (stats, tests, toggle)
- Manage Models (list, pull, delete, switch)
- Data Management (backup/restore, utilities)
- Diagnostic (status, logs)

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
