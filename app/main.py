"""
main.py — RAG pipeline for DVA Assistant v2
Enhanced with multi-model routing, improved embeddings, and summarization
"""

import json
import math
import os
import re
import time
from functools import lru_cache
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.utilities import SQLDatabase

from health import run_all_checks
from model_manager import ModelManager
from sql_generator import DVASQLGenerator
from context_summarizer import ContextSummarizer

load_dotenv()

_startup_status = run_all_checks(exit_on_fail=False)
_model_manager = ModelManager()
_sql_generator = DVASQLGenerator()
_summarizer = ContextSummarizer()

# ---------------------------------------------------------------------------
# Trust level configuration
# ---------------------------------------------------------------------------

TRUST_LEVEL_LABELS = {
    1: "Level 1 — Federal Legislation (legislation.gov.au / rma.gov.au)",
    2: "Level 2 — CLIK Official (clik.dva.gov.au — binding policy interpretation)",
    3: "Level 3 — DVA.gov.au / Government Other (.gov.au)",
    4: "Level 4 — Service Providers (non-gov support sites)",
    5: "Level 5 — Community (Reddit / advocacy — verify against official sources)",
}

MAX_SOURCE_CARDS = 6

TRUST_LEVEL_WEIGHTS = {
    1: 0.25,
    2: 0.30,
    3: 0.20,
    4: 0.15,
    5: 0.10,
}


# ---------------------------------------------------------------------------
# DVA Acts priority — MRCA, DRCA, VEA
# ---------------------------------------------------------------------------

DVA_ACT_PRIORITY_URLS: dict[str, float] = {
    "C2004A01285": 1.0,
    "C1988A00156": 0.8,
    "C2004A03268": 0.8,
}

DVA_ACT_CLIK_FRAGMENTS: dict[str, float] = {
    "military-rehabilitation-and-compensation-act": 1.0,
    "military-compensation-mrca": 1.0,
    "safety-rehabilitation-and-compensation": 0.8,
    "military-compensation-srca": 0.8,
    "veterans-entitlements-act": 0.8,
}


def _dva_act_priority(url: str) -> float:
    url_lower = url.lower()
    for fragment, weight in DVA_ACT_PRIORITY_URLS.items():
        if fragment.lower() in url_lower:
            return weight
    for fragment, weight in DVA_ACT_CLIK_FRAGMENTS.items():
        if fragment in url_lower:
            return weight
    return 0.0


# ---------------------------------------------------------------------------
# Database / engine helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(db_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_langchain_db() -> SQLDatabase:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return SQLDatabase.from_uri(
        db_url,
        include_tables=[
            "dva_acts", "service_categories",
            "v_service_standards", "v_dva_acts_simple", "v_content_summary",
        ],
        sample_rows_in_table_info=2,
    )


def get_startup_status() -> dict:
    return _startup_status


def get_hardware_info() -> dict:
    return _model_manager.get_hardware_info()


def get_available_models() -> dict:
    return _model_manager.get_available_models()


def get_last_updated() -> str:
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT source_type, COUNT(*) AS cnt, MAX(last_scraped) AS latest
                FROM scraped_content
                GROUP BY source_type
                ORDER BY source_type
            """)).fetchall()
            if not rows:
                return "No data indexed yet — run the scraper first."
            lines = []
            for row in rows:
                ts = row[2].strftime("%d %b %Y %H:%M") if row[2] else "unknown"
                lines.append(f"**{row[0]}**: {row[1]} records (last: {ts})")
            return " | ".join(lines)
    except Exception as e:
        return f"Database offline ({e})"


def get_content_stats() -> dict:
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT source_type, COUNT(*) FROM scraped_content GROUP BY source_type"
            )).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def get_page_stats() -> dict:
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT source_type, COUNT(DISTINCT source_url) "
                "FROM scraped_content GROUP BY source_type"
            )).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Query complexity classification
# ---------------------------------------------------------------------------

def classify_query_complexity(question: str) -> str:
    """
    Classify query as 'simple', 'complex', or 'technical' for model routing.
    """
    q_lower = question.lower()
    
    complex_keywords = [
        "compare", "vs", "versus", "difference between", "if then",
        "eligible if", "qualify for", "entitled to", "can i claim",
        "what happens if", "how does", "interact", "combined",
    ]
    
    technical_keywords = [
        "section", "act", "legislation", "regulation", " subclause",
        "statement of principles", " SOP ", "MRCA", "DRCA", "VEA",
        "rehabilitation", "compensation", "liability", "permanent",
    ]
    
    condition_keywords = [
        "and", "or", "if", "when", "with", "also", "plus",
    ]
    
    complex_score = sum(1 for kw in complex_keywords if kw in q_lower)
    technical_score = sum(1 for kw in technical_keywords if kw in q_lower)
    condition_count = sum(1 for kw in condition_keywords if kw in q_lower)
    
    if complex_score >= 2 or technical_score >= 2 or condition_count >= 3:
        return "complex"
    elif technical_score >= 1:
        return "technical"
    else:
        return "simple"


def get_routed_model(question: str) -> str:
    """
    Route question to appropriate model based on complexity.
    """
    complexity = classify_query_complexity(question)
    
    if complexity == "complex":
        return os.getenv("MODEL_COMPLEX", "qwen2.5:14b")
    elif complexity == "technical":
        return os.getenv("SQL_MODEL", "codellama:7b")
    else:
        return os.getenv("MODEL_NAME", "llama3.1:8b")


# ---------------------------------------------------------------------------
# SQL safety
# ---------------------------------------------------------------------------

_DANGEROUS = re.compile(
    r'\b(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE|GRANT|REVOKE)\b',
    re.IGNORECASE,
)


def clean_sql(raw: str) -> str:
    sql = re.sub(r"```sql", "", raw, flags=re.IGNORECASE)
    sql = re.sub(r"```", "", sql).strip()
    if ";" in sql:
        sql = sql.split(";")[0].strip() + ";"
    else:
        sql = sql.rstrip() + ";"
    if not re.match(r'^\s*SELECT\b', sql, re.IGNORECASE):
        raise ValueError(f"Generated SQL is not a SELECT statement: {sql[:80]}")
    return sql


# ---------------------------------------------------------------------------
# Text post-processing
# ---------------------------------------------------------------------------

def remove_repeated_words(text: str) -> str:
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text, flags=re.IGNORECASE)
    for _ in range(3):
        new_text = re.sub(
            r'(\b\w+(?:\s+\w+){1,4}\b)(\s+\1\b)+', r'\1', text,
            flags=re.IGNORECASE,
        )
        if new_text == text:
            break
        text = new_text
    return text


_METADATA_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\(?(?:Trust\s+)?Level\s+\d(?:[–\-]\d)?(?:\s+(?:source|sources|authoritative|and|or))?\)?',
                re.IGNORECASE), ''),
    (re.compile(r'\(authoritative(?:,\s*Level\s*\d)?\)', re.IGNORECASE), ''),
    (re.compile(r'[Aa]ccording\s+to\s+(?:highly\s+)?authoritative\s+sources?(?:\s*\([^)]*\))?',
                re.IGNORECASE), 'According to official legislation'),
    (re.compile(r'VETERAN[- ]PROVIDED\s+CONTEXT[:\s]*', re.IGNORECASE), ''),
    (re.compile(r'the information provided earlier in (?:the|our|this) conversation',
                re.IGNORECASE), 'what you told me earlier'),
    (re.compile(r'(?:the veteran|the user) (?:mentioned|stated|provided|indicated|noted)',
                re.IGNORECASE), 'you mentioned'),
    (re.compile(
        r"^(?:[^\n.!?]*[.!?]\s*)*?(?=[^\n.!?]*(?:I'm|I am)\s+here\s+to\s+(?:help|assist))"
        r"[^\n.!?]*(?:I'm|I am)\s+here\s+to\s+(?:help|assist)[^.!?]*[.!?]\s*",
        re.IGNORECASE), ''),
    (re.compile(r'^(?:Certainly|Of\s+course|Absolutely|Sure|Great(?:\s+question)?)[!.,]?\s+',
                re.IGNORECASE | re.MULTILINE), ''),
    (re.compile(
        r"^(?:I(?:'d|'ll|'m|\s+am|\s+would|\s+will|\s+can)\s+)?(?:be\s+)?"
        r"(?:happy|glad|pleased|delighted|more\s+than\s+happy)\s+to\s+"
        r"(?:help|assist|answer|address|explain|discuss|provide)[^.!?]*[.!?]\s*",
        re.IGNORECASE,
    ), ''),
    (re.compile(
        r"^(?:Happy|Glad|Pleased)\s+to\s+(?:help|assist|answer)[^.!?]*[.!?]\s*",
        re.IGNORECASE,
    ), ''),
]


def clean_response(text: str) -> str:
    for pattern, replacement in _METADATA_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return remove_repeated_words(text)


# ---------------------------------------------------------------------------
# Conversation Memory — Persistent Learning
# ---------------------------------------------------------------------------

def store_conversation(question: str, answer: str, sources: list,
                       confidence: float = 0.8, user_id: str = "anonymous",
                       log_id: Optional[int] = None) -> None:
    try:
        sources_json = json.dumps([
            {
                "url":         s.get("url", ""),
                "trust_level": s.get("trust_level", 5),
                "source_type": s.get("source_type", ""),
                "title":       s.get("title", ""),
            }
            for s in (sources or [])
        ])
        with get_engine().connect() as conn:
            conn.execute(text("""
                INSERT INTO conversation_memory
                    (user_id, question, answer, sources_cited, confidence_score, log_id)
                VALUES (:user_id, :q, :ans, CAST(:src AS jsonb), :conf, :log_id)
            """), {
                "user_id": user_id[:100],
                "q":       question,
                "ans":     answer[:3000],
                "src":     sources_json,
                "conf":    confidence,
                "log_id":  log_id,
            })
            conn.commit()
    except Exception as e:
        print(f"⚠️  Conversation memory write failed (non-fatal): {e}")


def retrieve_past_conversations(question: str, limit: int = 3) -> str:
    try:
        with get_engine().connect() as conn:
            keywords  = question.split()[:6]
            where_clauses = []
            params    = {}
            for i, kw in enumerate(keywords):
                if len(kw) > 2:
                    where_clauses.append(f"question ILIKE :kw{i}")
                    params[f"kw{i}"] = f"%{kw}%"
            if not where_clauses:
                return ""
            where_sql = " OR ".join(where_clauses)
            params["lim"] = limit
            rows = conn.execute(text(f"""
                SELECT question, answer, confidence_score, query_timestamp
                FROM conversation_memory
                WHERE ({where_sql})
                  AND COALESCE(is_flagged, FALSE) = FALSE
                ORDER BY query_timestamp DESC
                LIMIT :lim
            """), params).fetchall()
            if not rows:
                return ""
            context = "📚 SIMILAR QUESTIONS FROM PAST CONVERSATIONS:\n"
            for q, ans, conf, ts in rows:
                ts_str = ts.strftime("%d %b %Y") if ts else "unknown"
                context += f"\n  Q: {q[:80]}\n  A: {ans[:200]}...\n  (confidence: {conf:.2f}, {ts_str})\n"
            return context
    except Exception as e:
        print(f"⚠️  Conversation memory retrieval failed (non-fatal): {e}")
        return ""


def get_conversation_stats() -> dict:
    try:
        with get_engine().connect() as conn:
            total      = conn.execute(text("SELECT COUNT(*) FROM conversation_memory")).scalar() or 0
            avg_conf   = conn.execute(text("SELECT AVG(confidence_score) FROM conversation_memory")).scalar() or 0
            unique_users = conn.execute(text("SELECT COUNT(DISTINCT user_id) FROM conversation_memory")).scalar() or 0
            return {
                "total_conversations": total,
                "avg_confidence":      float(avg_conf) if avg_conf else 0,
                "unique_users":        unique_users,
            }
    except Exception:
        return {"total_conversations": 0, "avg_confidence": 0, "unique_users": 0}


# ---------------------------------------------------------------------------
# Input classification — question vs. statement
# ---------------------------------------------------------------------------

def classify_input(text: str) -> dict:
    t = text.strip()
    if not t:
        return {"type": "question", "confidence": 0.5, "signals": ["empty_input"]}

    t_lower = t.lower()
    signals: list = []
    q_score: float = 0.0
    s_score: float = 0.0

    _q_overrides = [
        r"\bi\s+(?:want|need|would like|'d like)\s+to\s+(?:know|understand|learn|find out|ask)\b",
        r"\bi\s+have\s+(?:a\s+)?(?:question|questions|concern|query|inquiry)\b",
        r"\bi(?:'m|\s+(?:am|was))\s+wondering\b",
        r"\bi(?:'m|\s+am)\s+looking\s+for\b",
        r"\bi(?:'m|\s+am)\s+trying\s+to\b",
        r"\bi\s+need\s+(?:help|information|info|advice|clarification|to know|to find|to understand)\b",
        r"\b(?:can|could)\s+you\s+(?:tell|explain|describe|help|show|list|clarify|outline)\b",
        r"\bwould\s+you\s+(?:be\s+able|know)\b",
        r"\bhelp\s+me\s+(?:understand|find|know|with|figure)\b",
        r"\bwould\s+like\s+to\s+(?:know|understand|find out|ask|learn)\b",
    ]
    for pattern in _q_overrides:
        if re.search(pattern, t_lower):
            signals.append(f"q_override:{pattern[:40]}")
            return {"type": "question", "confidence": 0.92, "signals": signals}

    if "?" in t:
        q_score += 3.0
        signals.append("question_mark")

    _q_words = ("what ", "how ", "why ", "when ", "where ", "who ", "which ", "whose ", "whom ")
    for prefix in _q_words:
        if t_lower.startswith(prefix):
            q_score += 2.0
            signals.append(f"q_word:{prefix.strip()}")
            break

    _aux = ("is ", "are ", "was ", "were ", "will ", "would ", "could ", "should ", "can ", "do ", "does ", "did ", "has ", "have ", "had ", "am ", "shall ", "might ", "may ")
    for prefix in _aux:
        if t_lower.startswith(prefix):
            q_score += 2.0
            signals.append(f"aux_invert:{prefix.strip()}")
            break

    _imperatives = ("explain ", "tell ", "describe ", "list ", "show ", "define ", "clarify ", "elaborate ", "compare ", "summarise ", "summarize ", "outline ", "help ", "please ", "give me")
    for prefix in _imperatives:
        if t_lower.startswith(prefix):
            q_score += 2.0
            signals.append(f"imperative:{prefix.strip()}")
            break

    _stmt_prefixes = ("i have ", "i've ", "i am ", "i'm ", "i was ", "i've been ", "i served ", "i suffer ", "i experience ", "i take ", "i use ", "i receive ", "i received ", "i got ", "i recently ", "i currently ", "i previously ", "i've had ", "i had ")
    for prefix in _stmt_prefixes:
        if t_lower.startswith(prefix):
            s_score += 3.0
            signals.append(f"stmt_prefix:{prefix.strip()}")
            break

    if t_lower.startswith("my ") and len(t.split()) >= 3:
        s_score += 3.0
        signals.append("possessive_my")

    _context_phrases = ("for future reference", "just so you know", "just letting you know", "just to let you know", "for your reference", "for your information", "just to mention", "just wanted to mention", "just wanted to let you know", "please note", "note that", "fyi", "btw", "by the way", "heads up", "in case it helps", "in case you need to know", "in case that's relevant", "in case it's relevant", "worth noting")
    for phrase in _context_phrases:
        if phrase in t_lower:
            s_score += 3.0
            signals.append(f"context_phrase:{phrase.strip()}")
            break

    _medical_terms = ("ptsd", "post-traumatic", "post traumatic", "anxiety", "depression", "tbi", "traumatic brain", "hearing loss", "tinnitus", "chronic pain", "back injury", "back pain", "knee injury", "shoulder injury", "cancer", "diabetes", "fibromyalgia", "sleep disorder", "sleep apnea", "sleep apnoea", "condition", "disability", "disorder", "syndrome", "diagnosed", "diagnosis", "on medication", "on a pension")
    _has_medical = any(m in t_lower for m in _medical_terms)
    _has_1p = bool(re.search(r"\b(i|my|me|i've|i'm|i am|i was)\b", t_lower))
    if _has_medical and _has_1p and q_score == 0:
        s_score += 2.0
        signals.append("personal_medical_context")

    if t.rstrip().endswith(".") and not t.rstrip().endswith("...") and q_score == 0:
        s_score += 0.5
        signals.append("ends_period")

    total = q_score + s_score

    if total == 0:
        return {"type": "question", "confidence": 0.5, "signals": ["default_question"]}

    if s_score > q_score:
        conf = round(s_score / total, 2)
        return {"type": "statement", "confidence": conf, "signals": signals}
    else:
        conf = round(q_score / total, 2) if total > 0 else 0.5
        return {"type": "question", "confidence": conf, "signals": signals}


def _build_statement_acknowledgement(text: str) -> str:
    t_lower = text.lower().strip()

    _conditions = {
        "ptsd": "PTSD",
        "post-traumatic stress": "PTSD",
        "post traumatic stress": "PTSD",
        "anxiety": "anxiety",
        "depression": "depression",
        "tbi": "traumatic brain injury (TBI)",
        "traumatic brain": "traumatic brain injury (TBI)",
        "hearing loss": "hearing loss",
        "tinnitus": "tinnitus",
        "chronic pain": "chronic pain",
        "back injury": "a back injury",
        "back pain": "back pain",
        "knee injury": "a knee condition",
        "shoulder injury": "a shoulder condition",
        "cancer": "cancer",
        "diabetes": "diabetes",
        "fibromyalgia": "fibromyalgia",
        "sleep apnea": "sleep apnoea",
        "sleep apnoea": "sleep apnoea",
        "sleep disorder": "a sleep disorder",
    }
    noted_condition = None
    for term, label in _conditions.items():
        if term in t_lower:
            noted_condition = label
            break

    _service_kw = ("served", "deployed", "enlisted", "discharged", "posting", "afghanistan", "iraq", "east timor", "timor-leste", "solomon islands", "korea", "vietnam", "gulf", "bougainville", "somalia", "navy", "army", "air force", "raaf", "ran", "adf", "warlike service", "non-warlike", "peacetime service")
    is_service = any(k in t_lower for k in _service_kw)

    _entitlement_kw = ("tpi", "white card", "gold card", "dva card", "pension", "compensation", "claim", "benefit", "mrca", "drca", "vea", "srca")
    is_entitlement = any(k in t_lower for k in _entitlement_kw)

    if noted_condition:
        return f"Got it — I've noted that you have {noted_condition}. I'll keep that in mind as we go. What would you like to know?"
    elif is_service:
        return "Got it, I've noted that. What would you like to find out?"
    elif is_entitlement:
        return "Noted — I'll factor that in. What would you like to know?"
    else:
        return "Got it — I'll keep that in mind. Feel free to ask anything about DVA entitlements, legislation, or support."


# ---------------------------------------------------------------------------
# Weighted source selection
# ---------------------------------------------------------------------------

def deduplicate_sources(sources: list) -> list:
    seen_urls = set()
    seen_titles = set()
    deduped = []
    for s in sorted(sources, key=lambda x: x.get("trust_level", 5)):
        url = s.get("url", "")
        norm_title = s.get("title", "").strip().lower()[:80]
        title_key = (norm_title, s.get("source_type", ""))

        if not url:
            continue
        if url in seen_urls:
            continue
        if norm_title and title_key in seen_titles:
            continue

        seen_urls.add(url)
        if norm_title:
            seen_titles.add(title_key)
        deduped.append(s)
    return deduped


def select_weighted_sources(sources: list, max_cards: int = MAX_SOURCE_CARDS) -> list:
    sources = deduplicate_sources(sources)
    if len(sources) <= max_cards:
        return sources

    buckets: dict = {lvl: [] for lvl in range(1, 6)}
    for s in sources:
        lvl = max(1, min(5, int(s.get("trust_level", 5))))
        buckets[lvl].append(s)

    raw_alloc = {lvl: TRUST_LEVEL_WEIGHTS[lvl] * max_cards for lvl in range(1, 6)}
    alloc = {lvl: min(len(buckets[lvl]), max(0, round(raw_alloc[lvl]))) for lvl in range(1, 6)}

    for _ in range(10):
        total_alloc = sum(alloc.values())
        spare = max_cards - total_alloc
        if spare <= 0:
            break
        for lvl in range(1, 6):
            remaining = len(buckets[lvl]) - alloc[lvl]
            if remaining > 0 and spare > 0:
                give = min(remaining, spare)
                alloc[lvl] += give
                spare -= give

    selected = []
    already_urls = set()
    for lvl in range(1, 6):
        for s in buckets[lvl][:alloc[lvl]]:
            selected.append(s)
            already_urls.add(s["url"])

    for s in sources:
        if len(selected) >= max_cards:
            break
        if s["url"] not in already_urls:
            selected.append(s)
            already_urls.add(s["url"])

    return selected[:max_cards]


# ---------------------------------------------------------------------------
# Re-ranker — lexical + semantic combined scoring
# ---------------------------------------------------------------------------

def rerank_chunks(question: str, hits: list) -> list:
    if not hits:
        return hits

    _STOP = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can", "to", "of", "in", "for", "on", "with", "at", "by", "from", "and", "or", "but", "if", "as", "not", "this", "that", "it", "its", "i", "me", "my", "you", "your", "what", "how", "why", "when", "where", "who", "which"}
    q_terms = [t.lower().strip("?.,!:;\"'()") for t in question.split() if len(t) > 2 and t.lower().strip("?.,!:;\"'()") not in _STOP]

    if not q_terms:
        for h in hits:
            act_boost = _dva_act_priority(h.get("url", "")) * 0.20
            h["combined_score"] = round(float(h.get("similarity", 0.0)) + act_boost, 4)
            h["act_boost"] = round(act_boost, 4)
        hits.sort(key=lambda h: (int(h.get("trust_level", 5)), -h["combined_score"]))
        return hits

    n_docs = len(hits)
    df: dict = {}
    for h in hits:
        text_lower = (h.get("snippet") or "").lower()
        for term in set(q_terms):
            if term in text_lower:
                df[term] = df.get(term, 0) + 1

    raw_kw: list = []
    for h in hits:
        text_lower = (h.get("snippet") or "").lower()
        n_words = max(len(text_lower.split()), 1)
        score = 0.0
        for term in q_terms:
            if term in text_lower:
                tf = text_lower.count(term) / n_words
                idf = math.log(1 + n_docs / (1 + df.get(term, 0)))
                score += tf * idf
        raw_kw.append(score)

    sem_scores = [float(h.get("similarity", 0.0)) for h in hits]
    max_sem = max(sem_scores) if max(sem_scores) > 0 else 1.0
    max_kw = max(raw_kw) if max(raw_kw) > 0 else 1.0

    for i, h in enumerate(hits):
        base_score = round(0.65 * (sem_scores[i] / max_sem) + 0.35 * (raw_kw[i] / max_kw), 4)
        act_boost = _dva_act_priority(h.get("url", "")) * 0.20
        h["combined_score"] = round(base_score + act_boost, 4)
        h["act_boost"] = round(act_boost, 4)

    hits.sort(key=lambda h: (int(h.get("trust_level", 5)), -h["combined_score"]))
    return hits


# ---------------------------------------------------------------------------
# Semantic search — with embedding model routing
# ---------------------------------------------------------------------------

def semantic_search(question: str, top_k: int = 10, embed_model: str = "mxbai-embed-large") -> list:
    if embed_model is None:
        embed_model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
    
    embed_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
    
    try:
        emb_model = OllamaEmbeddings(
            model=embed_model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        vector = emb_model.embed_query(question)
        vec_literal = "[" + ",".join(str(v) for v in vector) + "]"
        fetch_limit = top_k * 6

        with get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    title,
                    source_type,
                    source_library,
                    source_url,
                    LEFT(page_text, 1200) AS snippet,
                    1 - (embedding_mxbai <=> CAST(:vec AS vector)) AS similarity,
                    trust_level,
                    last_scraped
                FROM scraped_content
                WHERE embedding_mxbai IS NOT NULL
                ORDER BY embedding_mxbai <=> CAST(:vec AS vector)
                LIMIT :lim
            """), {"vec": vec_literal, "lim": fetch_limit}).fetchall()

            if not rows:
                rows = conn.execute(text("""
                    SELECT
                        title,
                        source_type,
                        source_library,
                        source_url,
                        LEFT(page_text, 1200) AS snippet,
                        1 - (embedding <=> CAST(:vec AS vector)) AS similarity,
                        trust_level,
                        last_scraped
                    FROM scraped_content
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:vec AS vector)
                    LIMIT :lim
                """), {"vec": vec_literal, "lim": fetch_limit}).fetchall()

        if not rows:
            return []

        buckets: dict = {lvl: [] for lvl in range(1, 6)}
        for r in rows:
            lvl = max(1, min(5, int(r[6])))
            buckets[lvl].append(r)

        guaranteed_per_level = max(1, top_k // 5)
        selected = []
        used_set = set()

        for lvl in range(1, 6):
            for r in buckets[lvl][:guaranteed_per_level]:
                if r[3] not in used_set:
                    selected.append(r)
                    used_set.add(r[3])

        remaining_candidates = sorted([r for r in rows if r[3] not in used_set], key=lambda r: -float(r[5]))
        for r in remaining_candidates:
            if len(selected) >= top_k:
                break
            if r[3] not in used_set:
                selected.append(r)
                used_set.add(r[3])

        selected.sort(key=lambda r: (int(r[6]), -float(r[5])))

        return [
            {
                "title": r[0],
                "source_type": r[1],
                "library": r[2],
                "url": r[3],
                "snippet": r[4],
                "similarity": float(r[5]),
                "trust_level": int(r[6]),
                "last_scraped": r[7],
            }
            for r in selected[:top_k]
        ]
    except Exception as e:
        print(f"⚠️  Semantic search error: {e}")
        return []


# ---------------------------------------------------------------------------
# Context assembly — with summarization
# ---------------------------------------------------------------------------

def build_weighted_context(vector_hits: list, structured_data=None, use_summarization: bool = True) -> tuple:
    seen_urls = set()
    deduped_hits = []
    for h in vector_hits:
        if h["url"] not in seen_urls:
            seen_urls.add(h["url"])
            deduped_hits.append(h)

    TARGET_CONTEXT = 12

    buckets: dict = {lvl: [] for lvl in range(1, 6)}
    for h in deduped_hits:
        lvl = max(1, min(5, h.get("trust_level", 5)))
        buckets[lvl].append(h)

    alloc: dict = {lvl: min(len(buckets[lvl]), max(0, round(TRUST_LEVEL_WEIGHTS[lvl] * TARGET_CONTEXT))) for lvl in range(1, 6)}

    for _ in range(10):
        total = sum(alloc.values())
        spare = TARGET_CONTEXT - total
        if spare <= 0:
            break
        for lvl in range(1, 6):
            remaining = len(buckets[lvl]) - alloc[lvl]
            if remaining > 0 and spare > 0:
                give = min(remaining, spare)
                alloc[lvl] += give
                spare -= give

    context_parts = []
    hits_used = []
    idx = 1

    if structured_data:
        context_parts.append("STRUCTURED DATABASE RESULTS (authoritative):\n" + str(structured_data))

    for lvl in range(1, 6):
        for h in buckets[lvl][:alloc[lvl]]:
            label = TRUST_LEVEL_LABELS.get(lvl, f"Level {lvl}")
            scraped = ""
            if h.get("last_scraped"):
                scraped = f" | scraped: {h['last_scraped'].strftime('%d %b %Y')}"
            context_parts.append(
                f"[{idx}] SOURCE: {h['source_type']} | {label}{scraped}\n"
                f"TITLE: {h['title']}\n"
                f"URL: {h['url']}\n"
                f"CONTENT: {h['snippet']}"
            )
            hits_used.append(h)
            idx += 1

    full_context = "\n\n---\n\n".join(context_parts)
    
    if use_summarization and len(full_context) > 2000:
        try:
            summarized = _summarizer.summarize(full_context, question="")
            if summarized and len(summarized) < len(full_context):
                full_context = summarized + "\n\n---\n\n[Full context available above]"
        except Exception as e:
            print(f"⚠️  Summarization failed: {e}")

    return full_context, hits_used


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _log_audit(question: str, answer: str, sources: list, has_conflict: bool, used_sql: bool, debug_sql: Optional[str], latency_ms: int, error: Optional[str] = None, model_used: str = "") -> Optional[int]:
    try:
        trust_levels = [s.get("trust_level", 5) for s in sources]
        if not trust_levels:
            trust_levels = [5]
        sources_json = json.dumps([{"url": s.get("url", ""), "trust_level": s.get("trust_level", 5), "source_type": s.get("source_type", "")} for s in sources])
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                INSERT INTO query_audit_log
                    (question, answer_snippet, sources_used, trust_levels,
                     has_conflict, used_sql, debug_sql, source_count, latency_ms, error, model_used)
                VALUES (:q, :ans, CAST(:src AS jsonb), :levels,
                        :conflict, :sql_used, :dsql, :cnt, :lat, :err, :model)
                RETURNING log_id
            """), {
                "q": question,
                "ans": answer[:500],
                "src": sources_json,
                "levels": trust_levels,
                "conflict": has_conflict,
                "sql_used": used_sql,
                "dsql": debug_sql,
                "cnt": len(sources),
                "lat": latency_ms,
                "err": error,
                "model": model_used,
            })
            log_id = result.scalar()
            conn.commit()
            return log_id
    except Exception as e:
        print(f"⚠️  Audit log write failed (non-fatal): {e}")
        return None


def flag_response(log_id: int, reason: str = "") -> bool:
    reason = (reason or "").strip()
    correction_text: Optional[str] = None
    prefix = "correction:"
    if reason.lower().startswith(prefix):
        correction_text = reason[len(prefix):].strip()

    try:
        with get_engine().connect() as conn:
            conn.execute(text("""
                UPDATE query_audit_log
                SET user_flagged = TRUE,
                    flag_reason  = :reason
                WHERE log_id = :log_id
            """), {"log_id": log_id, "reason": reason or None})

            conn.execute(text("""
                UPDATE conversation_memory
                SET is_flagged = TRUE,
                    correction = :correction
                WHERE log_id = :log_id
                  AND COALESCE(is_flagged, FALSE) = FALSE
            """), {"log_id": log_id, "correction": correction_text})

            original_question: Optional[str] = None
            if correction_text:
                row = conn.execute(text("SELECT question FROM query_audit_log WHERE log_id = :log_id"), {"log_id": log_id}).fetchone()
                if row:
                    original_question = row[0]

            conn.commit()

        if correction_text and original_question:
            try:
                store_conversation(question=original_question, answer=correction_text, sources=[], confidence=0.95, user_id="correction", log_id=None)
            except Exception as e:
                print(f"⚠️  Correction memory write failed (non-fatal): {e}")

        return True

    except Exception as e:
        print(f"⚠️  flag_response failed (non-fatal): {e}")
        return False


# ---------------------------------------------------------------------------
# RAG context preparation
# ---------------------------------------------------------------------------

def prepare_rag_context(question: str, user_id: str = "anonymous", session_history: Optional[list] = None) -> dict:
    classification = classify_input(question)

    if classification["type"] == "statement":
        return {
            "is_statement": True,
            "input_type": "statement",
            "classification": classification,
            "acknowledgement": _build_statement_acknowledgement(question),
        }

    veteran_context = ""
    if session_history:
        statements = [m["content"] for m in session_history if m.get("input_type") == "statement"]
        if statements:
            veteran_context = "VETERAN-PROVIDED CONTEXT:\n" + "\n".join(f"- {s}" for s in statements[-3:])

    past_context = retrieve_past_conversations(question)

    structured_data = None
    used_sql = False
    debug_sql = None

    try:
        schema = get_langchain_db().get_table_info()
        sql_question = f"Generate SQL for: {question}"
        raw_sql = _sql_generator.generate_query(sql_question, schema)
        debug_sql = raw_sql
        safe_sql = clean_sql(raw_sql)

        if safe_sql:
            with get_engine().connect() as conn:
                result = conn.execute(text(safe_sql))
                rows = result.fetchall()
                if rows:
                    structured_data = "\n".join(str(r) for r in rows[:5])
                    used_sql = True
    except Exception as e:
        print(f"⚠️  SQL generation/execution failed: {e}")

    vector_hits = semantic_search(question, top_k=10)

    if vector_hits:
        vector_hits = rerank_chunks(question, vector_hits)

    context, hits_used = build_weighted_context(vector_hits, structured_data)

    has_conflict = False
    if len(hits_used) >= 2:
        authoritative = [h for h in hits_used if h.get("trust_level", 5) <= 2]
        community = [h for h in hits_used if h.get("trust_level", 5) >= 4]
        if authoritative and community:
            has_conflict = True

    model_to_use = get_routed_model(question)

    system_prompt = f"""You are a helpful AI assistant providing information about Australian veteran entitlements under the DVA (Department of Veterans' Affairs) system.

IMPORTANT - MRCA PRIMACY FROM 1 JULY 2026:
From 1 July 2026, ALL new compensation and rehabilitation claims are determined under the MRCA (Military Rehabilitation and Compensation Act 2004), regardless of when the veteran served. DRCA and VEA remain for existing/lodged-before-1-July-2026 claims only.

When answering:
1. Lead with MRCA for any new claim questions
2. Only mention DRCA/VEA if directly relevant to the veteran's service period or existing grants
3. Always cite your sources using the provided context numbers

{veteran_context}

{past_context}

{context}

Based only on the provided context, answer the veteran's question. Cite sources as [1], [2], etc. at the end of your response. If you're unsure, say so honestly."""

    return {
        "is_statement": False,
        "input_type": "question",
        "classification": classification,
        "veteran_context": veteran_context,
        "past_context": past_context,
        "structured_data": structured_data,
        "used_sql": used_sql,
        "debug_sql": debug_sql,
        "vector_hits": hits_used,
        "context": context,
        "model_to_use": model_to_use,
        "system_prompt": system_prompt,
        "has_conflict": has_conflict,
    }


# ---------------------------------------------------------------------------
# LLM invocation with model routing
# ---------------------------------------------------------------------------

def generate_answer(prepared: dict, question: str) -> tuple:
    start = time.time()
    model = prepared.get("model_to_use", os.getenv("MODEL_NAME", "llama3.1:8b"))
    
    try:
        llm = OllamaLLM(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            num_ctx=int(os.getenv("LLM_CTX", "8192")),
        )
        
        full_prompt = prepared["system_prompt"] + f"\n\nQUESTION: {question}\n\nANSWER:"
        response = llm.invoke(full_prompt)
        answer = clean_response(response)
        
        latency_ms = int((time.time() - start) * 1000)
        
        sources = select_weighted_sources(prepared.get("vector_hits", []))
        
        log_id = _log_audit(
            question=question,
            answer=answer,
            sources=sources,
            has_conflict=prepared.get("has_conflict", False),
            used_sql=prepared.get("used_sql", False),
            debug_sql=prepared.get("debug_sql"),
            latency_ms=latency_ms,
            model_used=model,
        )
        
        return answer, sources, latency_ms, model
        
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        log_id = _log_audit(
            question=question,
            answer=f"Error: {str(e)}",
            sources=[],
            has_conflict=False,
            used_sql=prepared.get("used_sql", False),
            debug_sql=prepared.get("debug_sql"),
            latency_ms=latency_ms,
            error=str(e),
            model_used=model,
        )
        return f"I encountered an error: {str(e)}", [], latency_ms, model
