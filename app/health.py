"""
health.py — Health check utilities for DVA Assistant
"""

import os
import socket
from typing import Dict, List

import requests
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def check_database() -> Dict:
    """Check PostgreSQL database connectivity."""
    result = {"status": "unknown", "message": ""}
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            result["status"] = "error"
            result["message"] = "DATABASE_URL not set"
            return result
        
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        result["status"] = "healthy"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
    return result


def check_ollama() -> Dict:
    """Check Ollama API connectivity."""
    result = {"status": "unknown", "message": "", "models": []}
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        
        if response.status_code == 200:
            result["status"] = "healthy"
            data = response.json()
            result["models"] = [m["name"] for m in data.get("models", [])]
        else:
            result["status"] = "error"
            result["message"] = f"HTTP {response.status_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
    return result


def check_streamlit() -> Dict:
    """Check Streamlit UI status."""
    result = {"status": "unknown", "message": ""}
    try:
        import streamlit as st
        result["status"] = "healthy"
    except ImportError:
        result["status"] = "error"
        result["message"] = "Streamlit not installed"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
    return result


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def run_all_checks(exit_on_fail: bool = True) -> Dict:
    """
    Run all health checks and return a summary.
    
    Args:
        exit_on_fail: If True, exit on critical failure
        
    Returns:
        Dict with overall status and individual check results
    """
    checks = {
        "database": check_database(),
        "ollama": check_ollama(),
        "streamlit": check_streamlit(),
    }
    
    overall = "healthy"
    errors = []
    
    for name, check in checks.items():
        if check["status"] != "healthy":
            overall = "error"
            errors.append(f"{name}: {check['message']}")
    
    return {
        "overall": overall,
        "checks": checks,
        "errors": errors,
    }


def get_status_summary() -> str:
    """Get a human-readable status summary."""
    status = run_all_checks(exit_on_fail=False)
    
    lines = [f"Overall: {status['overall'].upper()}"]
    
    for name, check in status["checks"].items():
        icon = "✓" if check["status"] == "healthy" else "✗"
        lines.append(f"  {icon} {name}: {check['status']}")
        
        if check.get("models"):
            lines.append(f"    Models: {', '.join(check['models'][:5])}")
    
    return "\n".join(lines)
