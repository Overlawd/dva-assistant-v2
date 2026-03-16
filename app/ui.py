"""
ui.py — Streamlit UI for DVA Assistant

Enhanced with multi-model routing display and hardware info.
"""

import os
import time
import subprocess
from datetime import datetime
from typing import List, Optional

import streamlit as st
import psutil
import requests
from dotenv import load_dotenv

import main as main_module

st.set_page_config(page_title="DVA Assistant", page_icon="🎖️", layout="wide")

if 'network_history' not in st.session_state:
    st.session_state.network_history = []

if 'last_warning_time' not in st.session_state:
    st.session_state.last_warning_time = {}

if 'dismissed_warnings' not in st.session_state:
    st.session_state.dismissed_warnings = set()

if 'vram_warning_dismissed' not in st.session_state:
    st.session_state.vram_warning_dismissed = False

if 'vram_warning_dismiss_time' not in st.session_state:
    st.session_state.vram_warning_dismiss_time = 0

THRESHOLDS = {
    "critical": 90,
    "warning": 70,
    "caution": 50,
}

MODEL_VRAM_REQUIREMENTS = {
    "qwen2.5:14b": 9.0,
    "llama3.1:8b": 5.0,
    "qwen2.5:7b": 4.8,
    "codellama:7b": 4.0,
    "mxbai-embed-large": 0.7,
}


def _get_model_suggestion(vram_total_gb: float, vram_free_gb: float, current_model: str = None) -> dict:
    """Suggest best model based on VRAM and current usage."""
    suggestion = {"suggested": None, "reason": "", "vram_needed": 0}
    
    embedding_vram = MODEL_VRAM_REQUIREMENTS.get("mxbai-embed-large", 0.7)
    available_for_model = vram_free_gb - embedding_vram
    
    if available_for_model >= MODEL_VRAM_REQUIREMENTS.get("qwen2.5:14b", 9.0):
        suggestion["suggested"] = "qwen2.5:14b"
        suggestion["reason"] = "Sufficient VRAM for 14b model"
        suggestion["vram_needed"] = MODEL_VRAM_REQUIREMENTS["qwen2.5:14b"]
    elif available_for_model >= MODEL_VRAM_REQUIREMENTS.get("llama3.1:8b", 5.0):
        suggestion["suggested"] = "llama3.1:8b"
        suggestion["reason"] = "Sufficient VRAM for 8b model"
        suggestion["vram_needed"] = MODEL_VRAM_REQUIREMENTS["llama3.1:8b"]
    elif available_for_model >= MODEL_VRAM_REQUIREMENTS.get("qwen2.5:7b", 4.8):
        suggestion["suggested"] = "qwen2.5:7b"
        suggestion["reason"] = "Sufficient VRAM for 7b model"
        suggestion["vram_needed"] = MODEL_VRAM_REQUIREMENTS["qwen2.5:7b"]
    elif available_for_model >= MODEL_VRAM_REQUIREMENTS.get("codellama:7b", 4.0):
        suggestion["suggested"] = "codellama:7b"
        suggestion["reason"] = "Sufficient VRAM for codellama"
        suggestion["vram_needed"] = MODEL_VRAM_REQUIREMENTS["codellama:7b"]
    else:
        suggestion["suggested"] = "llama3.1:8b"
        suggestion["reason"] = f"Need more VRAM. Current: {vram_free_gb:.1f}GB free"
        suggestion["vram_needed"] = MODEL_VRAM_REQUIREMENTS["llama3.1:8b"]
    
    if current_model and suggestion["suggested"] != current_model:
        if MODEL_VRAM_REQUIREMENTS.get(current_model, 999) > available_for_model:
            suggestion["reason"] = f"{current_model} doesn't fit. {suggestion['reason']}"
    
    return suggestion


def _detect_hardware() -> dict:
    """Detect available hardware capabilities."""
    hw = {
        "has_gpu": False,
        "vram_total_gb": 0,
        "vram_used_gb": 0,
        "vram_free_gb": 0,
        "gpu_name": "CPU only",
        "gpu_temp": 0,
    }
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,name,temperature.gpu", 
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 5:
                hw["vram_total_gb"] = int(parts[0].strip()) / 1024
                hw["vram_used_gb"] = int(parts[1].strip()) / 1024
                hw["vram_free_gb"] = int(parts[2].strip()) / 1024
                hw["gpu_name"] = parts[3].strip()
                hw["gpu_temp"] = int(parts[4].strip())
                hw["has_gpu"] = True
    except Exception:
        pass
    
    return hw


def _get_ollama_active() -> bool:
    """Check if Ollama is currently processing a request."""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _get_container_network() -> float:
    """Get network I/O for the dva-web container only."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.NetIO}}", "dva-web"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("/")
            if len(parts) >= 2:
                recv = parts[0].strip()
                sent = parts[1].strip()
                
                def parse_size(s: str) -> float:
                    s = s.upper()
                    mult = 1
                    if "GB" in s:
                        mult = 1024
                        s = s.replace("GB", "")
                    elif "MB" in s:
                        s = s.replace("MB", "")
                    elif "KB" in s:
                        mult = 1/1024
                        s = s.replace("KB", "")
                    elif "B" in s:
                        mult = 1/1024/1024
                        s = s.replace("B", "")
                    try:
                        return float(s.strip()) * mult
                    except:
                        return 0.0
                
                total_mb = parse_size(recv) + parse_size(sent)
                return min(total_mb * 10, 100)
    except Exception:
        pass
    return 0.0


def _detect_active_task(ollama_active: bool, gpu_util: float, vram_util: float, 
                        cpu_util: float, disk_util: float, network_util: float) -> str:
    """Detect which hardware is currently bottlenecking based on Ollama API + thresholds."""
    
    if ollama_active and gpu_util >= 70:
        return "gpu"
    if vram_util >= 90:
        return "vram"
    if cpu_util >= 85 and gpu_util < 50:
        return "cpu"
    if disk_util >= 80 and cpu_util < 70:
        return "disk"
    if network_util >= 70 and gpu_util < 50 and cpu_util < 50:
        return "network"
    return "none"


def _get_task_weights(active_task: str, ramp_factor: float = 1.0) -> dict:
    """Return weights with 95% emphasis on active task, ramping over 2-3 cycles."""
    
    base = {
        "gpu": 0.40, "vram": 0.15, "cpu": 0.20, 
        "memory": 0.10, "disk": 0.10, "network": 0.05
    }
    
    task_emphasis = {
        "gpu":    {"gpu": 0.95, "vram": 0.02, "cpu": 0.015, "memory": 0.005, "disk": 0.005, "network": 0.005},
        "vram":   {"gpu": 0.02, "vram": 0.95, "cpu": 0.015, "memory": 0.005, "disk": 0.005, "network": 0.005},
        "cpu":    {"gpu": 0.01, "vram": 0.01, "cpu": 0.95, "memory": 0.01, "disk": 0.005, "network": 0.005},
        "disk":   {"gpu": 0.01, "vram": 0.01, "cpu": 0.02, "memory": 0.01, "disk": 0.93, "network": 0.01},
        "network": {"gpu": 0.01, "vram": 0.01, "cpu": 0.02, "memory": 0.01, "disk": 0.01, "network": 0.93},
    }
    
    if active_task == "none" or ramp_factor <= 0:
        return base
    
    emphasis = task_emphasis.get(active_task, base)
    
    blended = {}
    for k in base:
        blended[k] = base[k] * (1 - ramp_factor * 0.95) + emphasis[k] * (ramp_factor * 0.95)
    
    return blended


def get_system_load() -> dict:
    """Calculate weighted system load percentage with dynamic weights."""
    try:
        hw = _detect_hardware()
        
        gpu_util = 0
        vram_util = 0
        if hw["has_gpu"]:
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    gpu_util = float(result.stdout.strip().split('\n')[0])
                    if hw["vram_total_gb"] > 0:
                        vram_util = (hw["vram_used_gb"] / hw["vram_total_gb"]) * 100
            except Exception:
                pass
        
        cpu_util = psutil.cpu_percent(interval=0.3)
        mem_util = psutil.virtual_memory().percent
        
        disk_util = 0
        try:
            disk = psutil.disk_usage('/')
            disk_util = disk.percent
        except Exception:
            pass
        
        network_util = _get_container_network()
        
        ollama_active = _get_ollama_active()
        
        active_task = _detect_active_task(ollama_active, gpu_util, vram_util, cpu_util, disk_util, network_util)
        
        if 'task_history' not in st.session_state:
            st.session_state.task_history = []
        
        if active_task != "none":
            st.session_state.task_history.append(active_task)
            if len(st.session_state.task_history) > 3:
                st.session_state.task_history.pop(0)
        else:
            if len(st.session_state.task_history) > 0:
                st.session_state.task_history.pop(0) if len(st.session_state.task_history) == 1 else None
        
        ramp_factor = min(len(st.session_state.task_history) / 3.0, 1.0) if st.session_state.task_history else 0.0
        
        if active_task != "none" and ramp_factor > 0:
            weights = _get_task_weights(active_task, ramp_factor)
        else:
            if hw["has_gpu"]:
                if vram_util >= 85:
                    weights = {"gpu": 0.30, "vram": 0.25, "cpu": 0.15, "memory": 0.10, "disk": 0.15, "network": 0.05}
                else:
                    weights = {"gpu": 0.40, "vram": 0.15, "cpu": 0.20, "memory": 0.10, "disk": 0.10, "network": 0.05}
            else:
                weights = {"gpu": 0.00, "vram": 0.00, "cpu": 0.50, "memory": 0.25, "disk": 0.20, "network": 0.05}
        
        weighted_load = (
            gpu_util * weights.get("gpu", 0) +
            vram_util * weights.get("vram", 0) +
            cpu_util * weights.get("cpu", 0) +
            mem_util * weights.get("memory", 0) +
            disk_util * weights.get("disk", 0) +
            network_util * weights.get("network", 0)
        )
        
        critical_count = 0
        if gpu_util >= THRESHOLDS["critical"]: critical_count += 1
        if vram_util >= THRESHOLDS["critical"]: critical_count += 1
        if cpu_util >= THRESHOLDS["critical"]: critical_count += 1
        if mem_util >= THRESHOLDS["critical"]: critical_count += 1
        if hw.get("gpu_temp", 0) >= 85: critical_count += 1
        
        if critical_count >= 2:
            final_load = 100.0
        elif gpu_util >= 92 or vram_util >= 92 or cpu_util >= 92:
            final_load = min(weighted_load * 1.1, 100.0)
        else:
            final_load = min(weighted_load, 100.0)
        
        warnings = []
        current_time = time.time()
        
        if hw.get("gpu_temp", 0) >= 80:
            if "gpu_temp" not in st.session_state.dismissed_warnings:
                last_time = st.session_state.last_warning_time.get("gpu_temp", 0)
                if current_time - last_time > 30:
                    warnings.append("GPU hot")
        
        if vram_util >= 90:
            if not st.session_state.get("vram_warning_dismissed"):
                last_time = st.session_state.get("vram_warning_dismiss_time", 0)
                if current_time - last_time > 30:
                    warnings.append("VRAM critical")
        
        if mem_util >= 90:
            if "memory" not in st.session_state.dismissed_warnings:
                last_time = st.session_state.last_warning_time.get("memory", 0)
                if current_time - last_time > 30:
                    warnings.append("Memory critical")
        
        if cpu_util >= 90:
            if "cpu" not in st.session_state.dismissed_warnings:
                last_time = st.session_state.last_warning_time.get("cpu", 0)
                if current_time - last_time > 30:
                    warnings.append("CPU critical")
        
        return {
            "load": final_load,
            "gpu": gpu_util,
            "vram": vram_util,
            "cpu": cpu_util,
            "memory": mem_util,
            "disk": disk_util,
            "network": network_util,
            "gpu_temp": hw.get("gpu_temp", 0),
            "gpu_name": hw.get("gpu_name", "CPU only"),
            "vram_total_gb": hw.get("vram_total_gb", 0),
            "vram_free_gb": hw.get("vram_free_gb", 0),
            "ollama_active": ollama_active,
            "active_task": active_task,
            "ramp_factor": ramp_factor,
            "warnings": warnings,
            "has_gpu": hw["has_gpu"],
        }
    except Exception as e:
        return {
            "load": 0, "gpu": 0, "vram": 0, "cpu": 0, 
            "memory": 0, "disk": 0, "network": 0,
            "gpu_temp": 0, "gpu_name": "CPU only",
            "vram_total_gb": 0, "vram_free_gb": 0,
            "ollama_active": False, "active_task": "none", "ramp_factor": 0,
            "warnings": [], "has_gpu": False
        }


load_dotenv()

COLORS = {
    "LEGISLATION": "#1982c4",
    "CLIK": "#2a9d8f",
    "DVA_GOV": "#457b9d",
    "SUPPORT": "#9b5de5",
    "REDDIT": "#f15bb5",
}


def init_session_state():
    """Initialize Streamlit session state variables."""
    defaults = {
        "messages": [],
        "session_history": [],
        "conversation_id": None,
        "conversation_name": "",
        "last_update": "",
        "pending_question": None,
        "refresh_counter": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_system_status():
    """Render system status section - uses fragment for auto-refresh."""
    # Use a fragment to enable partial rerendering
    render_status_fragment()


def _render_system_status_widget():
    """Render a self-updating HTML/JS widget for system status."""
    import time
    
    sys_load = get_system_load()
    load_val = sys_load.get("load", 0)
    
    if load_val <= 50:
        load_color = "#22c55e"
    elif load_val <= 70:
        load_color = "#ffef00"
    elif load_val <= 90:
        load_color = "#f97316"
    else:
        load_color = "#ef4444"
    
    vram_info = ""
    if sys_load.get("has_gpu"):
        vram_total = sys_load.get("vram_total_gb", 0)
        vram_free = sys_load.get("vram_free_gb", 0)
        vram_util = sys_load.get("vram", 0)
        gpu_util = sys_load.get("gpu", 0)
        gpu_temp = sys_load.get("gpu_temp", 0)
        vram_info = f"""
        <div class="status-row">
            <span>VRAM:</span> <span>{vram_util:.0f}% ({vram_free:.1f}GB free)</span>
        </div>
        <div class="status-row">
            <span>GPU:</span> <span>{gpu_util:.0f}%</span>
        </div>
        <div class="status-row">
            <span>Temp:</span> <span>{gpu_temp}°C</span>
        </div>
        """
    else:
        cpu_util = sys_load.get("cpu", 0)
        mem_util = sys_load.get("memory", 0)
        disk_util = sys_load.get("disk", 0)
        vram_info = f"""
        <div class="status-row">
            <span>CPU:</span> <span>{cpu_util:.0f}%</span>
        </div>
        <div class="status-row">
            <span>Memory:</span> <span>{mem_util:.0f}%</span>
        </div>
        <div class="status-row">
            <span>Disk:</span> <span>{disk_util:.0f}%</span>
        </div>
        """
    
    warnings_html = ""
    for warn in sys_load.get("warnings", []):
        warnings_html += f'<div class="warning-badge">⚠️ {warn}</div>'
    
    ollama_status = "🤖 Ollama: Processing..." if sys_load.get("ollama_active") else ""
    
    task_html = ""
    active_task = sys_load.get("active_task")
    if active_task and active_task not in ("none", "None", None, ""):
        task_labels = {
            "gpu": "GPU-Bound",
            "vram": "VRAM-Bound",
            "cpu": "CPU-Bound",
            "disk": "Disk I/O-Bound",
            "network": "Network-Bound"
        }
        task_label = task_labels.get(active_task, active_task)
        task_html = f'<div class="task-badge">⚡ {task_label}</div>'
    
    widget_html = f"""
    <div class="system-status-widget">
        <style>
            .system-status-widget {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            .load-bar-container {{
                background-color: #1e1e1e;
                border-radius: 8px;
                height: 24px;
                width: 100%;
                margin: 8px 0;
            }}
            .load-bar {{
                background-color: {load_color};
                border-radius: 8px;
                height: 100%;
                width: {load_val}%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 12px;
                font-weight: bold;
                transition: width 0.3s ease;
            }}
            .status-row {{
                display: flex;
                justify-content: space-between;
                font-size: 0.75rem;
                padding: 2px 0;
                color: #9ca3af;
            }}
            .status-row span:last-child {{
                color: #e5e7eb;
                font-weight: 500;
            }}
            .warning-badge {{
                background-color: #fef3c7;
                border: 1px solid #f59e0b;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 0.75rem;
                color: #92400e;
                margin: 4px 0;
                display: inline-block;
            }}
            .task-badge {{
                background-color: #dbeafe;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 0.75rem;
                color: #1e40af;
                margin-top: 4px;
                display: inline-block;
            }}
            .section-title {{
                font-size: 0.85rem;
                font-weight: 600;
                color: #e5e7eb;
                margin-top: 8px;
            }}
        </style>
        
        <div class="section-title">System Load</div>
        <div class="load-bar-container">
            <div class="load-bar">{load_val:.0f}%</div>
        </div>
        
        {warnings_html}
        {ollama_status}
        {task_html}
        
        <div class="section-title">Component Details</div>
        {vram_info}
    </div>
    """
    
    st.markdown(widget_html, unsafe_allow_html=True)


def render_system_status():
    """Render system status section."""
    _render_system_status_widget()
    
    st.write("**System Load (%)**")
    
    st.markdown(f"""
        <div style="background-color: #1e1e1e; border-radius: 8px; height: 24px; width: 100%;">
            <div style="background-color: {load_color}; border-radius: 8px; height: 100%; width: {load_val}%; 
                 display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">
                {load_val:.0f}%
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if sys_load.get("warnings"):
        for warn in sys_load.get("warnings", []):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"""
                    <div style="background-color: #fef3c7; border: 1px solid #f59e0b; 
                                border-radius: 4px; padding: 4px 8px; font-size: 0.75rem; color: #92400e;">
                        ⚠️ {warn}
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("✕", key=f"dismiss_{warn}"):
                    if warn == "VRAM critical":
                        st.session_state.vram_warning_dismissed = True
                        st.session_state.vram_warning_dismiss_time = time.time()
                    else:
                        st.session_state.dismissed_warnings.add(warn)
                        st.session_state.last_warning_time[warn] = time.time()
                    st.rerun()
    
    if sys_load.get("ollama_active"):
        st.caption("🤖 Ollama: Processing request...")
    
    active_task = sys_load.get("active_task")
    if active_task and active_task not in ("none", "None", None, ""):
        task_labels = {
            "gpu": "GPU-Bound (embedding/inference)",
            "vram": "VRAM-Bound (memory pressure)",
            "cpu": "CPU-Bound (processing)",
            "disk": "Disk I/O-Bound",
            "network": "Network-Bound"
        }
        task_label = task_labels.get(active_task, active_task)
        ramp = sys_load.get("ramp_factor", 0) * 100
        st.caption(f"⚡ Task: {task_label} ({ramp:.0f}% emphasis)")
    
    with st.expander("📊 Component Details"):
        if sys_load.get("has_gpu"):
            cols = st.columns(3)
            cols[0].markdown(f"<div style='font-size:0.75rem; text-align:center;'>GPU<br/><b>{sys_load.get('gpu', 0):.0f}%</b></div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div style='font-size:0.75rem; text-align:center;'>VRAM<br/><b>{sys_load.get('vram', 0):.0f}%</b></div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Temp<br/><b>{sys_load.get('gpu_temp', 0)}°C</b></div>", unsafe_allow_html=True)
        else:
            cols = st.columns(3)
            cols[0].markdown(f"<div style='font-size:0.75rem; text-align:center;'>CPU<br/><b>{sys_load.get('cpu', 0):.0f}%</b></div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Memory<br/><b>{sys_load.get('memory', 0):.0f}%</b></div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Disk<br/><b>{sys_load.get('disk', 0):.0f}%</b></div>", unsafe_allow_html=True)
        
        cols2 = st.columns(2)
        if sys_load.get("has_gpu"):
            cols2[0].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Network<br/><b>{sys_load.get('network', 0):.1f}%</b></div>", unsafe_allow_html=True)
            cols2[1].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Memory<br/><b>{sys_load.get('memory', 0):.0f}%</b></div>", unsafe_allow_html=True)
        else:
            cols2[0].markdown(f"<div style='font-size:0.75rem; text-align:center;'>Network<br/><b>{sys_load.get('network', 0):.1f}%</b></div>", unsafe_allow_html=True)
    
    if sys_load.get("has_gpu"):
        st.markdown("---")
        vram_total = sys_load.get("vram_total_gb", 0)
        vram_free = sys_load.get("vram_free_gb", 0)
        
        model_suggestion = _get_model_suggestion(vram_total, vram_free)
        
        st.markdown(f"**GPU:** {sys_load.get('gpu_name', 'Unknown')}")
        st.markdown(f"**VRAM:** {vram_total:.0f} GB ({vram_free:.1f} GB free)")
        
        if model_suggestion["suggested"]:
            with st.expander("💡 Model Suggestion"):
                st.markdown(f"**Recommended:** `{model_suggestion['suggested']}`")
                st.caption(model_suggestion["reason"])
                if model_suggestion["vram_needed"] > 0:
                    st.caption(f"Needs: ~{model_suggestion['vram_needed']:.1f} GB")


def render_sidebar():
    """Render the sidebar with controls and info."""
    with st.sidebar:
        st.title("🎖️ DVA Assistant")
        st.caption("Local RAG for Veteran Entitlements")
        
        st.markdown("---")
        
        session_context = [m["content"] for m in st.session_state.session_history if m.get("input_type") == "statement"]
        if session_context:
            with st.expander(f"📝 Your Context ({len(session_context)} items)"):
                for i, ctx in enumerate(session_context, 1):
                    st.caption(f"{i}. {ctx[:100]}{'...' if len(ctx) > 100 else ''}")
                if st.button("Clear Context", key="clear_context"):
                    st.session_state.session_history = []
                    st.rerun()
        
        st.markdown("---")
        
        render_system_status()
        
        st.markdown("---")
        
        models_info = main_module.get_available_models()
        if models_info.get("status") == "connected":
            installed = models_info.get("installed", [])
            with st.expander(f"🔌 Models ({len(installed)} installed)"):
                for m in installed:
                    st.caption(f"• {m}")
        
        common_questions = main_module.get_common_questions()
        if common_questions:
            with st.expander("❓ Common Questions"):
                for cat_idx, (cat, questions) in enumerate(common_questions.items()):
                    st.markdown(f"**{cat}**")
                    for q_idx, q in enumerate(questions[:3]):
                        btn_key = f"faq_{cat_idx}_{q_idx}"
                        display_text = q[:47] + "..." if len(q) > 47 else q
                        if st.button(display_text, key=btn_key):
                            st.session_state.pending_question = q
                            st.rerun()
                    st.markdown("---")
        
        st.markdown("---")
        
        st.subheader("📚 Knowledge Base")
        stats = main_module.get_page_stats()
        
        for source, count in sorted(stats.items()):
            color = COLORS.get(source, "#666")
            st.markdown(
                f'<span style="color:{color}">●</span> **{source}**: {count}',
                unsafe_allow_html=True,
            )
        
        st.write("")
        
        st.caption(f"Last updated: {main_module.get_last_updated()}")


def render_message_item(msg: dict):
    """Render a single chat message."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and msg.get("sources"):
            st.divider()
            render_sources(msg["sources"])
        
        if msg.get("metadata"):
            with st.expander("Details"):
                if msg["metadata"].get("model"):
                    st.write(f"**Model:** {msg['metadata']['model']}")
                if msg["metadata"].get("latency_ms"):
                    st.write(f"**Latency:** {msg['metadata']['latency_ms']}ms")
                if msg["metadata"].get("used_sql"):
                    st.write("**SQL Used:** Yes")


def render_sources(sources: List[dict]):
    """Render source citations."""
    for i, src in enumerate(sources, 1):
        color = COLORS.get(src.get("source_type", ""), "#666")
        
        st.markdown(
            f'<sup style="color:{color}">[{i}]</sup> '
            f'<a href="{src.get("url", "#")}" target="_blank">{src.get("title", "Unknown")}</a>',
            unsafe_allow_html=True,
        )


def process_question(prompt: str):
    """Process a question and store in session history."""
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now(),
    })
    
    prepared = main_module.prepare_rag_context(
        question=prompt,
        session_history=st.session_state.session_history,
    )
    
    if prepared.get("is_statement"):
        response = prepared.get("acknowledgement", "")
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(),
            "input_type": "statement",
        })
        
        st.session_state.session_history.append({
            "role": "user",
            "content": prompt,
            "input_type": "statement",
        })
    else:
        try:
            thinking_html = """
            <style>
                @keyframes pulse-1 { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.1); } }
                @keyframes pulse-2 { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.1); } }
                @keyframes pulse-3 { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.1); } }
                .thinking-container { display: flex; gap: 8px; align-items: center; padding: 10px 15px; background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%); border-radius: 8px; margin: 10px 0; width: fit-content; }
                .thinking-dot { width: 12px; height: 12px; border-radius: 50%; }
                .dot-1 { background: linear-gradient(135deg, #22c55e, #16a34a); animation: pulse-1 1.2s ease-in-out infinite; }
                .dot-2 { background: linear-gradient(135deg, #3b82f6, #2563eb); animation: pulse-2 1.2s ease-in-out infinite 0.2s; }
                .dot-3 { background: linear-gradient(135deg, #eab308, #ca8a04); animation: pulse-3 1.2s ease-in-out infinite 0.4s; }
                .thinking-text { color: #9ca3af; font-size: 14px; font-weight: 500; }
                .thinking-icon { font-size: 20px; }
            </style>
            <div class="thinking-container">
                <span class="thinking-icon">🎖️</span>
                <div class="thinking-dot dot-1"></div>
                <div class="thinking-dot dot-2"></div>
                <div class="thinking-dot dot-3"></div>
                <span class="thinking-text">Veteran Services at work...</span>
            </div>
            """
            
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown(thinking_html, unsafe_allow_html=True)
            
            answer, sources, latency, model = main_module.generate_answer(prepared, prompt)
            
            thinking_placeholder.empty()
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "timestamp": datetime.now(),
                "metadata": {
                    "model": model,
                    "latency_ms": latency,
                    "used_sql": prepared.get("used_sql", False),
                },
            })
            
            st.session_state.session_history.extend([
                {"role": "user", "content": prompt, "input_type": "question"},
                {"role": "assistant", "content": answer, "input_type": "answer"},
            ])
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Error: {str(e)}",
                "timestamp": datetime.now(),
            })


def handle_input():
    """Handle user input and generate responses."""
    if st.session_state.get("pending_question"):
        prompt = st.session_state.pending_question
        st.session_state.pending_question = None
        process_question(prompt)
        st.rerun()
        return
    
    if prompt := st.chat_input("Ask about DVA entitlements..."):
        process_question(prompt)
        st.rerun()


def main():
    try:
        init_session_state()
        
        render_sidebar()
        
        st.title("DVA Assistant")
        st.caption("Ask questions about Australian veteran entitlements, compensation, and DVA services")

        for msg in st.session_state.get("messages", []):
            render_message_item(msg)
        
        handle_input()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
