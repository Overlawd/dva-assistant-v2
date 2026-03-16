"""
api.py - FastAPI endpoint for system status polling and chat
Enhanced for React frontend integration
"""
import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

import main as main_module

load_dotenv()

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVML = True
except:
    HAS_NVML = False


def get_system_load():
    """Get current system load metrics."""
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net_io = psutil.net_io_counters()
    
    load = cpu
    warnings = []
    
    data = {
        "load": load,
        "cpu": cpu,
        "memory": memory.percent,
        "disk": disk.percent,
        "network": 0,
        "has_gpu": False,
    }
    
    if net_io.bytes_sent > 0:
        data["network"] = 50
    
    if HAS_NVML:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            vram_total_gb = mem_info.total / (1024**3)
            vram_free_gb = mem_info.free / (1024**3)
            vram_used_gb = mem_info.used / (1024**3)
            vram_util = (mem_info.used / mem_info.total) * 100
            
            data["has_gpu"] = True
            data["gpu"] = util.gpu
            data["vram"] = vram_util
            data["vram_total_gb"] = vram_total_gb
            data["vram_free_gb"] = vram_free_gb
            data["gpu_temp"] = temp
            
            if vram_util > 90:
                warnings.append("VRAM > 90%")
            if temp > 85:
                warnings.append(f"GPU {temp}°C")
                
        except Exception as e:
            pass
    
    if memory.percent > 90:
        warnings.append("Memory > 90%")
    
    data["warnings"] = warnings
    
    return data


class ChatRequest(BaseModel):
    message: str
    session_history: Optional[List[Dict[str, Any]]] = []
    recent_questions: Optional[List[str]] = []
    user_id: Optional[str] = "anonymous"


class ChatResponse(BaseModel):
    is_statement: bool
    acknowledgement: Optional[str] = None
    answer: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = []
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    used_sql: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = {}
    system_status: Optional[Dict[str, Any]] = None


app = FastAPI(title="DVA Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/system-status")
async def system_status():
    """Return system status as JSON."""
    return get_system_load()


@app.get("/api/system-status-stream")
async def system_status_stream():
    """Server-Sent Events stream for real-time system status."""
    from fastapi.responses import StreamingResponse
    import json
    
    async def event_generator():
        while True:
            data = get_system_load()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(2)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/common-questions")
async def common_questions():
    """Return common veteran questions grouped by category."""
    try:
        questions = main_module.get_common_questions()
        return questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge-stats")
async def knowledge_stats():
    """Return knowledge base statistics."""
    try:
        stats = main_module.get_page_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return the response."""
    try:
        # Get current system status to return with response
        current_status = get_system_load()
        
        prepared = main_module.prepare_rag_context(
            request.message,
            user_id=request.user_id or "anonymous",
            session_history=request.session_history,
            recent_questions=request.recent_questions or []
        )
        
        if prepared.get("is_statement"):
            return ChatResponse(
                is_statement=True,
                acknowledgement=prepared.get("acknowledgement", "Acknowledged."),
                system_status=current_status,
            )
        
        answer, sources, latency_ms, model = main_module.generate_answer(prepared, request.message)
        
        return ChatResponse(
            is_statement=False,
            answer=answer,
            sources=sources,
            model_used=model,
            latency_ms=latency_ms,
            used_sql=prepared.get("used_sql", False),
            metadata={
                "model_used": model,
                "latency_ms": latency_ms,
                "used_sql": prepared.get("used_sql", False),
            },
            system_status=current_status,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
