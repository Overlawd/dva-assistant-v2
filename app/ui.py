"""
ui.py — Streamlit UI for DVA Assistant v2

Enhanced with multi-model routing display and hardware info.
"""

import os
import time
from datetime import datetime
from typing import List, Optional

import streamlit as st
from dotenv import load_dotenv

import main as main_module

load_dotenv()

st.set_page_config(
    page_title="DVA Assistant v2",
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar():
    """Render the sidebar with controls and info."""
    with st.sidebar:
        st.title("🎖️ DVA Assistant v2")
        st.caption("Local RAG for Veteran Entitlements")
        
        st.divider()
        
        st.subheader("📊 System Status")
        
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


def handle_input():
    """Handle user input and generate responses."""
    if prompt := st.chat_input("Ask about DVA entitlements..."):
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


def main():
    init_session_state()
    
    render_sidebar()
    
    st.title("DVA Assistant v2")
    st.caption("Ask questions about Australian veteran entitlements, compensation, and DVA services")

    for msg in st.session_state.messages:
        render_message_item(msg)
    
    handle_input()


if __name__ == "__main__":
    main()
