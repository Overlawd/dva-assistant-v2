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

if 'session_history' not in st.session_state:
    st.session_state.session_history = []

if 'pending_question' not in st.session_state:
    st.session_state.pending_question = None


load_dotenv()


COLORS = {
    "DVA": "#1e40af",
    "NDIS": "#7c3aed",
    "Services Australia": "#059669",
    "MyGov": "#dc2626",
    "Aged Care": "#db2777",
    "Centrelink": "#0891b2",
}


def get_system_load():
    """Get current system load metrics."""
    hw_info = main_module.get_hardware_info()
    return hw_info


def get_available_models():
    """Get available Ollama models."""
    return main_module.get_available_models()


def get_page_stats():
    """Get page count by source."""
    return main_module.get_page_stats()


def get_last_updated():
    """Get last database update time."""
    return main_module.get_last_updated()


def get_common_questions():
    """Get common questions for quick access."""
    return main_module.get_common_questions()


def init_session_state():
    """Initialize session state defaults."""
    defaults = {
        "messages": [],
        "session_history": [],
        "pending_question": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_system_status():
    """Render system status."""
    import requests
    
    try:
        resp = requests.get("http://dva-api:8502/api/system-status", timeout=1)
        sys_load = resp.json()
    except:
        sys_load = get_system_load()
    
    load_val = sys_load.get("load", 0)
    has_gpu = sys_load.get("has_gpu", False)
    
    st.markdown("### System Load")
    st.progress(load_val / 100, text=f"{load_val:.0f}%")
    
    if has_gpu:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("GPU", f"{sys_load.get('gpu', 0):.0f}%")
        col2.metric("VRAM", f"{sys_load.get('vram', 0):.0f}%")
        col3.metric("Temp", f"{sys_load.get('gpu_temp', 0)}°C")
        col4.metric("Net", f"{sys_load.get('network', 0):.1f}%")
        st.caption(f"VRAM: {sys_load.get('vram_free_gb', 0):.1f}GB free")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CPU", f"{sys_load.get('cpu', 0):.0f}%")
        col2.metric("Mem", f"{sys_load.get('memory', 0):.0f}%")
        col3.metric("Disk", f"{sys_load.get('disk', 0):.0f}%")
        col4.metric("Net", f"{sys_load.get('network', 0):.1f}%")
    
    warnings = sys_load.get("warnings", [])
    if warnings:
        for w in warnings:
            st.warning(w)
    
    if st.button("🔄 Refresh", key="refresh_status"):
        st.rerun()


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
        
        st.subheader("📊 System Status")
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
            
            if msg["metadata"]:
                if msg["metadata"].get("model_used"):
                    st.write(f"**Model:** {msg['metadata']['model_used']}")
                if msg["metadata"].get("推理时间"):
                    st.write(f"**推理时间:** {msg['metadata']['推理时间']}")
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
    })
    
    context_statements = [m["content"] for m in st.session_state.session_history if m.get("input_type") == "statement"]
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            prepared = main_module.prepare_rag_context(prompt, session_history=st.session_state.session_history)
            
            if prepared.get("is_statement"):
                response = prepared.get("acknowledgement", "Acknowledged.")
                st.markdown(response)
                st.session_state.session_history.append({
                    "content": prompt,
                    "input_type": "statement",
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "sources": [],
                    "metadata": {"is_statement": True},
                })
                st.rerun()
            
            answer, sources, latency_ms, model = main_module.generate_answer(prepared, prompt)
            metadata = {
                "model_used": model,
                "推理时间": f"{latency_ms}ms",
                "used_sql": prepared.get("used_sql", False),
            }
        
        st.markdown(answer)
        
        if sources:
            st.divider()
            render_sources(sources)
        
        if metadata:
            if metadata.get("model_used"):
                st.write(f"**Model:** {metadata['model_used']}")
            if metadata.get("推理时间"):
                st.write(f"**推理时间:** {metadata['推理时间']}")
            if metadata.get("used_sql"):
                st.write("**SQL Used:** Yes")
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "metadata": metadata,
        })
    
    st.rerun()


def check_vram_warnings():
    """Check VRAM and show warnings with model suggestions."""
    hw_info = get_system_load()
    
    if not hw_info.get("has_gpu"):
        return
    
    vram_util = hw_info.get("vram", 0)
    vram_free = hw_info.get("vram_free_gb", 0)
    
    if vram_util > 85:
        warning_key = "vram_high"
        
        if warning_key in st.session_state.dismissed_warnings:
            return
        
        last_time = st.session_state.last_warning_time.get(warning_key, 0)
        if time.time() - last_time < 30:
            return
        
        suggestions = []
        if vram_free < 4:
            suggestions = ["llama3.2:3b", "phi3:3.8b", "tinyllama"]
        elif vram_free < 8:
            suggestions = ["llama3.1:8b", "qwen2.5:7b", "mistral:7b"]
        
        warning_msg = f"⚠️ **High VRAM Usage: {vram_util:.0f}%** ({vram_free:.1f}GB free)"
        if suggestions:
            suggestion_text = " • ".join([f"`{s}`" for s in suggestions[:3]])
            warning_msg += f"\n\n**Try:** {suggestion_text}"
        
        with st.sidebar:
            with st.expander("⚠️ VRAM Warning", expanded=True):
                st.markdown(warning_msg)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Dismiss", key="dismiss_vram_warning"):
                        st.session_state.dismissed_warnings.add(warning_key)
                        st.session_state.last_warning_time[warning_key] = time.time()
                        st.rerun()


def main():
    """Main application entry point."""
    init_session_state()
    
    st.title("🎖️ DVA Assistant")
    st.caption("Ask questions about Australian veteran entitlements and benefits")
    
    check_vram_warnings()
    
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        process_question(question)
    
    for msg in st.session_state.messages:
        render_message_item(msg)
    
    if prompt := st.chat_input("Ask about DVA entitlements..."):
        process_question(prompt)
    
    render_sidebar()


if __name__ == "__main__":
    main()
