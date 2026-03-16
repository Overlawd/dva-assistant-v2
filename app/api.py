"""
api.py - FastAPI endpoint for system status polling
"""
import psutil
from fastapi import FastAPI
from contextlib import asynccontextmanager

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


app = FastAPI()


@app.get("/api/system-status")
async def system_status():
    """Return system status as JSON."""
    return get_system_load()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
