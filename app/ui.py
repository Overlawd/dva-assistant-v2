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
from streamlit_autorefresh import st_autorefresh
import psutil
import requests
from dotenv import load_dotenv

import main as main_module

st.set_page_config(page_title="DVA Assistant", page_icon="🎖️", layout="wide")

if 'network_history' not in st.session_state:
    st.session_state.network_history = []

THRESHOLDS = {
    "critical": 90,
    "warning": 70,
    "caution": 50,
}


def _detect_hardware() -> dict:
    """Detect available hardware capabilities."""
    hw = {
        "has_gpu": False,
        "vram_total_gb": 0,
        "vram_used_gb": 0,
        "gpu_name": "CPU only",
        "gpu_temp": 0,
    }
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,name,temperature.gpu", 
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 4:
                hw["vram_total_gb"] = int(parts[0].strip()) / 1024
                hw["vram_used_gb"] = int(parts[1].strip()) / 1024
                hw["gpu_name"] = parts[2].strip()
                hw["gpu_temp"] = int(parts[3].strip())
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
        
        disk_io = psutil.disk_io_counters()
        disk_util = 0
        try:
            disk = psutil.disk_usage('/')
            disk_util = disk.percent
        except Exception:
            pass
        
        net_sent = psutil.net_io_counters().bytes_sent
        net_recv = psutil.net_io_counters().bytes_recv
        time.sleep(0.3)
        net_sent2 = psutil.net_io_counters().bytes_sent
        net_recv2 = psutil.net_io_counters().bytes_recv
        net_mb = (net_sent2 - net_sent + net_recv2 - net_recv) / 1024 / 1024
        network_util = min(net_mb * 10, 100)
        
        st.session_state.network_history.append(network_util)
        if len(st.session_state.network_history) > 5:
            st.session_state.network_history.pop(0)
        network_util = sum(st.session_state.network_history) / len(st.session_state.network_history)
        
        if hw["has_gpu"]:
            if vram_util >= 85:
                weights = {"gpu": 0.30, "vram": 0.25, "cpu": 0.15, "memory": 0.10, "disk": 0.15, "network": 0.05}
            else:
                weights = {"gpu": 0.40, "vram": 0.15, "cpu": 0.20, "memory": 0.10, "disk": 0.10, "network": 0.05}
        else:
            weights = {"gpu": 0.00, "vram": 0.00, "cpu": 0.50, "memory": 0.25, "disk": 0.20, "network": 0.05}
        
        ollama_active = _get_ollama_active()
        if ollama_active:
            weights["gpu"] = min(weights["gpu"] * 1.2, 0.50)
            total_w = sum(weights.values())
            weights = {k: v/total_w for k, v in weights.items()}
        
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
        if hw.get("gpu_temp", 0) >= 80:
            warnings.append("GPU hot")
        if vram_util >= 90:
            warnings.append("VRAM critical")
        if mem_util >= 90:
            warnings.append("Memory critical")
        if cpu_util >= 90:
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
            "ollama_active": ollama_active,
            "warnings": warnings,
            "has_gpu": hw["has_gpu"],
        }
    except Exception as e:
        return {
            "load": 0, "gpu": 0, "vram": 0, "cpu": 0, 
            "memory": 0, "disk": 0, "network": 0,
            "gpu_temp": 0, "gpu_name": "CPU only",
            "ollama_active": False, "warnings": [], "has_gpu": False
        }


load_dotenv()

st.set_page_config(
    page_title="DVA Assistant",
    page_icon="🎖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar():
    """Render the sidebar with controls and info."""
    with st.sidebar:
        st.title("🎖️ DVA Assistant")
        st.caption("Local RAG for Veteran Entitlements")
        
        st.divider()
        
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
        
        session_context = [m["content"] for m in st.session_state.session_history if m.get("input_type") == "statement"]
        if session_context:
            with st.expander(f"📝 Your Context ({len(session_context)} items)"):
                for i, ctx in enumerate(session_context, 1):
                    st.caption(f"{i}. {ctx[:100]}{'...' if len(ctx) > 100 else ''}")
                if st.button("Clear Context", key="clear_context"):
                    st.session_state.session_history = []
                    st.rerun()
        
        st.divider()
        
        st_autorefresh(interval=2000, key="system_load_refresh")
        
        st.subheader("📊 System Status")
        
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
            warning_text = " | ".join(sys_load["warnings"])
            st.warning(f"⚠️ {warning_text}")
        
        if sys_load.get("ollama_active"):
            st.caption("🤖 Ollama: Processing request...")
        
        with st.expander("📊 Component Details"):
            cols = st.columns(3)
            if sys_load.get("has_gpu"):
                cols[0].metric("GPU", f"{sys_load.get('gpu', 0):.0f}%")
                cols[1].metric("VRAM", f"{sys_load.get('vram', 0):.0f}%")
                cols[2].metric("GPU Temp", f"{sys_load.get('gpu_temp', 0)}°C")
            else:
                cols[0].metric("CPU", f"{sys_load.get('cpu', 0):.0f}%")
                cols[1].metric("Memory", f"{sys_load.get('memory', 0):.0f}%")
                cols[2].metric("Disk", f"{sys_load.get('disk', 0):.0f}%")
            
            cols2 = st.columns(2)
            cols2[0].metric("Network", f"{sys_load.get('network', 0):.1f}%")
            cols2[1].metric("Memory", f"{sys_load.get('memory', 0):.0f}%")
        
        hw_info = main_module.get_hardware_info()
        st.write(f"**GPU:** {hw_info.get('gpu_name', 'Unknown')}")
        st.write(f"**VRAM:** {hw_info.get('vram_gb', 0)} GB")
        
        models_info = main_module.get_available_models()
        if models_info.get("status") == "connected":
            st.write(f"**Models Installed:** {len(models_info.get('installed', []))}")
        
        st.divider()
        
        st.subheader("🔧 Model Routing")
        st.caption("Questions are automatically routed to optimal models")
        
        with st.expander("View Recommendations"):
            rec = hw_info.get("recommendation", {})
            st.write(f"**Chat:** {rec.get('chat', 'N/A')}")
            st.write(f"**Reasoning:** {rec.get('reasoning', 'N/A')}")
            st.write(f"**SQL:** {rec.get('sql', 'N/A')}")
            st.write(f"**Embeddings:** {rec.get('embeddings', 'N/A')}")
        
        st.divider()
        
        st.subheader("📚 Knowledge Base")
        stats = main_module.get_page_stats()
        
        for source, count in sorted(stats.items()):
            color = COLORS.get(source, "#666")
            st.markdown(
                f'<span style="color:{color}">●</span> **{source}**: {count}',
                unsafe_allow_html=True,
            )
        
        st.divider()
        
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
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant", avatar="🎖️"):
        with st.spinner("Thinking..."):
            prepared = main_module.prepare_rag_context(
                question=prompt,
                session_history=st.session_state.session_history,
            )
            
            if prepared.get("is_statement"):
                response = prepared.get("acknowledgement", "")
                st.markdown(response)
                
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
                answer, sources, latency, model = main_module.generate_answer(prepared, prompt)
                
                st.markdown(answer)
                render_sources(sources)
                
                st.caption(f"Model: {model} | Latency: {latency}ms")
                
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


def handle_input():
    """Handle user input and generate responses."""
    if st.session_state.get("pending_question"):
        prompt = st.session_state.pending_question
        st.session_state.pending_question = None
        process_question(prompt)
        return
    
    if prompt := st.chat_input("Ask about DVA entitlements..."):
        process_question(prompt)


def main():
    init_session_state()
    
    render_sidebar()
    
    st.title("DVA Assistant")
    st.caption("Ask questions about Australian veteran entitlements, compensation, and DVA services")

    for msg in st.session_state.messages:
        render_message_item(msg)
    
    handle_input()


if __name__ == "__main__":
    main()
