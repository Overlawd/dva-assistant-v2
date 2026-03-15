"""
context_summarizer.py — Context compression using qwen2.5:7b

Summarizes retrieved context to fit more relevant content in the LLM context window.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_ollama import OllamaLLM

load_dotenv()


class ContextSummarizer:
    """
    Uses a lightweight model to summarize retrieved context.
    """
    
    def __init__(self, model: str = "qwen2.5:7b"):
        self.model = model or os.getenv("SUMMARIZER_MODEL", "qwen2.5:7b")
        self._llm = None
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._max_words = 400
    
    @property
    def llm(self) -> OllamaLLM:
        if self._llm is None:
            self._llm = OllamaLLM(
                model=self.model,
                base_url=self._base_url,
                num_ctx=8192,
            )
        return self._llm
    
    def summarize(self, context: str, question: str = "", max_words: int = 400) -> str:
        """
        Summarize the retrieved context.
        
        Args:
            context: The full context from retrieval
            question: The original question (for relevance)
            max_words: Maximum words in summary
            
        Returns:
            Summarized context
        """
        if len(context.split()) <= max_words:
            return context
        
        prompt = f"""Summarize the following context to approximately {max_words} words.
Focus on information most relevant to answering questions about Australian veteran DVA entitlements.

Original context:
{context}

Provide a concise summary that preserves key facts, dates, legislation references, and entitlements:"""
        
        try:
            response = self.llm.invoke(prompt)
            return response.strip() if response else context
        except Exception as e:
            print(f"⚠️  Summarization error: {e}")
            return context
    
    def summarize_for_sources(self, hits: list, question: str = "") -> str:
        """
        Summarize a list of retrieved hits.
        
        Args:
            hits: List of retrieved document chunks
            question: The original question
            
        Returns:
            Summarized content with source attribution
        """
        if not hits:
            return ""
        
        context_parts = []
        for i, h in enumerate(hits[:10], 1):
            title = h.get("title", "Unknown")
            snippet = h.get("snippet", "")
            url = h.get("url", "")
            context_parts.append(f"[{i}] {title}\n{snippet}\nSource: {url}")
        
        full_context = "\n\n---\n\n".join(context_parts)
        
        if len(full_context.split()) <= 500:
            return full_context
        
        return self.summarize(full_context, question, max_words=500)
    
    def compress_for_ctx_limit(self, context: str, question: str, ctx_limit: int = 6000) -> str:
        """
        Compress context to fit within a token limit.
        
        Args:
            context: Full context string
            question: Original question
            ctx_limit: Target token limit
            
        Returns:
            Compressed context
        """
        estimated_tokens = len(context.split()) * 1.3
        
        if estimated_tokens <= ctx_limit:
            return context
        
        target_words = int(ctx_limit / 1.3)
        
        prompt = f"""Compress the following context to approximately {target_words} words while preserving key information about Australian veteran DVA entitlements, legislation (MRCA, DRCA, VEA), and compensation claims.

Context:
{context}

Provide a compressed but comprehensive summary:"""
        
        try:
            response = self.llm.invoke(prompt)
            return response.strip() if response else context[:ctx_limit * 4]
        except Exception as e:
            print(f"⚠️  Compression error: {e}")
            return context[:ctx_limit * 4]


# Singleton instance
_summarizer = ContextSummarizer()


def get_summarizer() -> ContextSummarizer:
    return _summarizer
