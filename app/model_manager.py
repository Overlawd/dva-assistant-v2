"""
model_manager.py — Hardware-adaptive model selection for DVA Assistant v2

Automatically detects GPU capabilities and recommends optimal models.
"""

import os
import subprocess
import json
from typing import Optional
from functools import lru_cache

import requests
from dotenv import load_dotenv

load_dotenv()


class ModelManager:
    """
    Manages model selection based on hardware capabilities.
    """
    
    VRAM_TIERS = {
        (0, 4): {"chat": "phi3:3.8b-mini", "reasoning": "phi3:3.8b-mini", "embeddings": "nomic-embed-text", "sql": "phi3:3.8b-mini"},
        (4, 6): {"chat": "llama3.1:8b", "reasoning": "qwen2.5:14b", "embeddings": "mxbai-embed-large", "sql": "codellama:7b"},
        (6, 8): {"chat": "llama3.1:8b", "reasoning": "qwen2.5:14b", "embeddings": "mxbai-embed-large", "sql": "codellama:7b"},
        (8, 12): {"chat": "llama3.1:8b", "reasoning": "qwen2.5:14b", "embeddings": "mxbai-embed-large", "sql": "codellama:7b"},
        (12, 999): {"chat": "llama3.1:8b", "reasoning": "deepseek-coder-v2:236b", "embeddings": "mxbai-embed-large", "sql": "codellama:7b"},
    }
    
    def __init__(self):
        self._hardware_info = None
        self._available_models = None
    
    @lru_cache(maxsize=1)
    def get_hardware_info(self) -> dict:
        """
        Detect GPU VRAM and return hardware capabilities.
        """
        info = {
            "vram_gb": 0,
            "gpu_name": "CPU only",
            "cuda_available": False,
            "recommendation": self._get_recommendation(0),
        }
        
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,name", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                if lines:
                    parts = lines[0].split(",")
                    if len(parts) >= 2:
                        info["vram_gb"] = int(parts[0].strip())
                        info["gpu_name"] = parts[1].strip()
                        info["cuda_available"] = True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        
        info["recommendation"] = self._get_recommendation(info["vram_gb"])
        self._hardware_info = info
        return info
    
    def _get_recommendation(self, vram_gb: int) -> dict:
        """
        Get model recommendations based on VRAM.
        """
        for (min_vram, max_vram), models in self.VRAM_TIERS.items():
            if min_vram <= vram_gb < max_vram:
                return models
        return self.VRAM_TIERS[(0, 4)]
    
    def get_recommended_model(self, use_case: str) -> str:
        """
        Get recommended model for a specific use case.
        
        Args:
            use_case: One of "chat", "reasoning", "embeddings", "sql"
        """
        info = self.get_hardware_info()
        return info["recommendation"].get(use_case, "llama3.1:8b")
    
    def get_available_models(self) -> dict:
        """
        Check which models are available in Ollama.
        """
        if self._available_models:
            return self._available_models
        
        available = {
            "installed": [],
            "recommended": {},
            "status": "unknown",
        }
        
        try:
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                available["installed"] = [m["name"] for m in data.get("models", [])]
                available["status"] = "connected"
            else:
                available["status"] = f"error_{response.status_code}"
        except Exception as e:
            available["status"] = f"error: {str(e)}"
        
        hw = self.get_hardware_info()
        available["recommended"] = hw["recommendation"]
        
        self._available_models = available
        return available
    
    def is_model_available(self, model_name: str) -> bool:
        """
        Check if a specific model is installed.
        """
        available = self.get_available_models()
        return model_name in available.get("installed", [])
    
    def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.
        
        Returns True if successful.
        """
        try:
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            response = requests.post(
                f"{base_url}/api/pull",
                json={"name": model_name},
                timeout=300,
                stream=True,
            )
            return response.status_code in (200, 201)
        except Exception:
            return False
    
    def get_model_for_query(self, question: str) -> str:
        """
        Intelligent model routing based on query complexity.
        
        This is called from main.py to select the best model.
        """
        complexity = self._analyze_complexity(question)
        use_case_map = {
            "simple": "chat",
            "technical": "sql",
            "complex": "reasoning",
        }
        return self.get_recommended_model(use_case_map.get(complexity, "chat"))
    
    def _analyze_complexity(self, question: str) -> str:
        """
        Analyze query complexity for model routing.
        """
        q_lower = question.lower()
        
        complex_keywords = ["compare", "vs", "versus", "difference", "if then", "eligible", "qualify", "entitled", "can i claim"]
        technical_keywords = ["section", "act", "legislation", "regulation", " subclause", "statement of principles", " SOP ", "MRCA", "DRCA", "VEA", "rehabilitation", "compensation"]
        
        complex_score = sum(1 for kw in complex_keywords if kw in q_lower)
        technical_score = sum(1 for kw in technical_keywords if kw in q_lower)
        
        if complex_score >= 2 or technical_score >= 3:
            return "complex"
        elif technical_score >= 1:
            return "technical"
        else:
            return "simple"


# Singleton instance
_model_manager = ModelManager()


def get_model_manager() -> ModelManager:
    return _model_manager
