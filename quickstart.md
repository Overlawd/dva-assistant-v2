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
Rename-Item "_env" ".env
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

You should see 5 containers running:
- dva-ollama
- dva-db  
- dva-web
- dva-scraper
- dva-scheduler

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

## Step 6: Test It!

Open your browser to: **http://localhost:8501**

Try asking:
> "What is MRCA?"

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
|---------|-------------|
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

Manage models, backups, diagnostics, and more!

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

**GPU not detected:**
- Install NVIDIA driver
- Restart Docker Desktop

---

## Need Help?

- Check README.md for full documentation
- Use Admin Console [5] for diagnostics
- Check container logs: `docker logs dva-web`
