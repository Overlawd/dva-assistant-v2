"""
ui.py — Streamlit UI for DVA Assistant

Sidebar with tabs: Chat, System Status, Common Questions, Settings
"""

import os
import time
from datetime import datetime
from typing import List, Optional

import streamlit as st
import psutil
import requests
from dotenv import load_dotenv

import main as main_module

st.set_page_config(page_title="DVA Assistant", page_icon="🎖️", layout="wide")

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'session_history' not in st.session_state:
    st.session_state.session_history = []

if 'pending_question' not in st.session_state:
    st.session_state.pending_question = None

if 'generating' not in st.session_state:
    st.session_state.generating = False

if 'recent_questions' not in st.session_state:
    st.session_state.recent_questions = []

if 'last_response' not in st.session_state:
    st.session_state.last_response = None

if 'awaiting_repeat_confirmation' not in st.session_state:
    st.session_state.awaiting_repeat_confirmation = False


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
    try:
        resp = requests.get("http://dva-api:8502/api/system-status", timeout=1)
        return resp.json()
    except Exception:
        pass
    
    # Fallback - return minimal status
    return {
        "load": 0,
        "cpu": 0,
        "memory": 0,
        "disk": 0,
        "network": 0,
        "has_gpu": False,
        "warnings": [],
    }


def render_system_status():
    """Render system status in a panel."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**System Status**")
    with col2:
        if st.button("🔄", key="refresh_status", help="Refresh status"):
            st.rerun()
    
    sys_load = get_system_load()
    load_val = sys_load.get("load", 0)
    has_gpu = sys_load.get("has_gpu", False)
    
    if load_val <= 50:
        load_color = "#22c55e"
    elif load_val <= 70:
        load_color = "#eab308"
    elif load_val <= 90:
        load_color = "#f97316"
    else:
        load_color = "#ef4444"
    
    st.markdown("**System Load**")
    st.progress(load_val / 100, text=f"{load_val:.0f}%")
    
    if has_gpu:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("GPU", f"{sys_load.get('gpu', 0):.0f}%")
        col2.metric("VRAM", f"{sys_load.get('vram', 0):.0f}%")
        col3.metric("Temp", f"{sys_load.get('gpu_temp', 0)}°C")
        col4.metric("Net", f"{sys_load.get('network', 0):.0f}%")
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


def render_common_questions():
    """Render common questions in a tab."""
    common_questions = main_module.get_common_questions()
    if not common_questions:
        st.write("No common questions available")
        return
    
    all_questions = []
    for cat, questions in common_questions.items():
        for q in questions[:3]:
            all_questions.append(q)
    
    options = ["Select a question..."] + all_questions
    selected = st.selectbox("❓ Common Questions", options, key="faq_select")
    
    if selected and selected != "Select a question...":
        st.session_state.pending_question = selected
        st.rerun()


def render_settings():
    """Render settings and session info in a tab."""
    st.markdown("### Session Info")
    
    # Recent questions
    recent = st.session_state.get('recent_questions', [])
    st.write(f"**Recent Questions:** {len(recent)}")
    if recent:
        with st.expander(f"View recent ({len(recent)})"):
            for q in recent[-10:]:
                st.caption(f"• {q}")
    
    # Session history
    history = st.session_state.get('session_history', [])
    st.write(f"**Session Context:** {len(history)} statements")
    
    if st.button("Clear Session"):
        st.session_state.session_history = []
        st.session_state.recent_questions = []
        st.session_state.messages = []
        st.session_state.last_response = None
        st.rerun()
    
    st.markdown("---")
    st.markdown("### Knowledge Base")
    stats = main_module.get_page_stats()
    for source, count in sorted(stats.items()):
        color = COLORS.get(source, "#666")
        st.markdown(f'<span style="color:{color}">●</span> **{source}**: {count}', unsafe_allow_html=True)
    
    st.caption(f"Last updated: {main_module.get_last_updated()}")


def render_message_item(msg: dict):
    """Render a single chat message."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and (msg.get("sources") or msg.get("metadata")):
            with st.expander("📋 Details", expanded=False):
                if msg.get("sources"):
                    render_sources(msg["sources"])
                
                if msg["metadata"]:
                    st.write("---")
                    if msg["metadata"].get("model_used"):
                        st.write(f"**Model:** {msg['metadata']['model_used']}")
                    if msg["metadata"].get("latency"):
                        st.write(f"**Latency:** {msg['metadata']['latency']}")
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
    
    prompt_stripped = prompt.strip()
    
    # Check if user is confirming to repeat last answer
    if st.session_state.get('awaiting_repeat_confirmation', False):
        prompt_lower = prompt_stripped.lower()
        if prompt_lower in ["yes", "y", "yeah", "yep", "sure", "ok", "please"]:
            if st.session_state.get('last_response'):
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": st.session_state.last_response["content"],
                    "sources": st.session_state.last_response.get("sources", []),
                    "metadata": st.session_state.last_response.get("metadata", {}),
                })
            st.session_state.awaiting_repeat_confirmation = False
            st.rerun()
            return
        else:
            st.session_state.awaiting_repeat_confirmation = False
    
    # Check for exact duplicate question
    recent_qs = st.session_state.get('recent_questions', [])
    
    if prompt_stripped in recent_qs:
        duplicate_msg = "You've asked me that this session. If you'd like me to say it again, just say yes, otherwise I'll await your next question or clarification."
        
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": duplicate_msg,
            "sources": [],
            "metadata": {},
        })
        
        st.session_state.awaiting_repeat_confirmation = True
        st.rerun()
        return
    
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })
    
    # Add to recent questions
    st.session_state.recent_questions.append(prompt_stripped)
    if len(st.session_state.recent_questions) > 100:
        st.session_state.recent_questions = st.session_state.recent_questions[-100:]
    
    # Process the question
    try:
        with st.spinner("🤔 Thinking..."):
            context_statements = [m["content"] for m in st.session_state.session_history if m.get("input_type") == "statement"]
            
            prepared = main_module.prepare_rag_context(
                prompt, 
                session_history=st.session_state.session_history,
                recent_questions=st.session_state.recent_questions
            )
            
            if prepared.get("is_statement"):
                response = prepared.get("acknowledgement", "Acknowledged.")
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
                return
            
            answer, sources, latency_ms, model = main_module.generate_answer(prepared, prompt)
            metadata = {
                "model_used": model,
                "latency": f"{latency_ms}ms",
                "used_sql": prepared.get("used_sql", False),
            }
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Error processing your question: {str(e)}",
            "sources": [],
            "metadata": {"error": True},
        })
        st.rerun()
        return
    
    # Store response
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "metadata": metadata,
    })
    
    st.session_state.last_response = {
        "content": answer,
        "sources": sources,
        "metadata": metadata,
    }
    
    st.rerun()


def main():
    """Main application entry point."""
    import streamlit.components.v1 as components
    
    # Browser refresh warning
    refresh_warning = """
    <script>
    window.onbeforeunload = function() {
        return "Warning: Refreshing this page will lose your conversation history. Continue?";
    };
    </script>
    """
    components.html(refresh_warning, height=0)
    
    st.title("🎖️ DVA Assistant")
    st.caption("Ask questions about Australian veteran entitlements and benefits")
    
    # Create column layout: main chat area + sidebar panels
    col_main, col_sidebar = st.columns([3, 1], gap="medium")
    
    # === MAIN AREA: CHAT ===
    with col_main:
        st.markdown("### 💬 Chat")
        
        # Handle pending questions
        if st.session_state.get('pending_question'):
            question = st.session_state.pending_question
            st.session_state.pending_question = None
            process_question(question)
        
        # Render messages
        for msg in st.session_state.messages:
            render_message_item(msg)
        
        # Chat input
        if prompt := st.chat_input("Ask about DVA entitlements..."):
            process_question(prompt)
    
    # === SIDEBAR PANELS: System Status, Common Questions, Settings ===
    with col_sidebar:
        # Panel 1: System Status (auto-refreshing)
        with st.expander("📊 System Status", expanded=True):
            render_system_status()
        
        # Panel 2: Common Questions
        with st.expander("❓ Common Questions"):
            render_common_questions()
        
        # Panel 3: Settings
        with st.expander("⚙️ Settings"):
            render_settings()


if __name__ == "__main__":
    main()
