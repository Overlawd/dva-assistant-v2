"""
ui.py — Streamlit UI for DVA Assistant

Simplified version - focused on chat functionality.
"""

import os
import time
from datetime import datetime
from typing import List, Optional

import streamlit as st
import psutil
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
    hw_info = main_module.get_hardware_info()
    return hw_info


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
    
    # Handle pending questions (from dropdown if re-added later)
    if st.session_state.get('pending_question'):
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        process_question(question)
        return
    
    # Render all messages
    for msg in st.session_state.messages:
        render_message_item(msg)
    
    # Chat input
    if prompt := st.chat_input("Ask about DVA entitlements..."):
        process_question(prompt)


if __name__ == "__main__":
    main()
