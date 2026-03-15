"""
sql_generator.py — Improved SQL generation using specialized models

Uses codellama for better SQL generation accuracy.
"""

import os
import re
from typing import Optional

from dotenv import load_dotenv
from langchain_ollama import OllamaLLM

load_dotenv()

_DANGEROUS = re.compile(
    r'\b(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE|GRANT|REVOKE)\b',
    re.IGNORECASE,
)


class DVASQLGenerator:
    """
    Specialized SQL generator for DVA database queries.
    Uses codellama for improved SQL accuracy.
    """
    
    def __init__(self, model: str = "codellama:7b"):
        self.model = model or os.getenv("SQL_MODEL", "codellama:7b")
        self._llm = None
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @property
    def llm(self) -> OllamaLLM:
        if self._llm is None:
            self._llm = OllamaLLM(
                model=self.model,
                base_url=self._base_url,
                num_ctx=4096,
            )
        return self._llm
    
    def generate_query(self, question: str, schema: str) -> str:
        """
        Generate a PostgreSQL SELECT query from a natural language question.
        
        Args:
            question: The user's question
            schema: Database schema information
            
        Returns:
            SQL query string
        """
        prompt = f"""You are a PostgreSQL expert. Given this database schema:

{schema}

Generate a safe PostgreSQL SELECT query for this question: {question}

Rules:
- Only generate SELECT statements - never INSERT, UPDATE, DELETE, DROP, or any other operation
- Use proper JOINs when needed
- Return ONLY the SQL query, no explanation
- Limit results to 10 rows for safety
- Use table and column names exactly as shown in the schema
- When searching text, use ILIKE for case-insensitive matching

Database tables available:
- dva_acts: id, act_name, act_code, description
- service_categories: id, category_name, act_id, standard_of_proof
- scraped_content: id, title, source_type, source_url, page_text, trust_level, last_scraped
- v_service_standards: joined view of service categories with standards of proof
- v_dva_acts_simple: summary view of DVA acts
- v_content_summary: content counts by source type

Generate the SQL query now:"""

        try:
            response = self.llm.invoke(prompt)
            return self._extract_sql(response)
        except Exception as e:
            print(f"⚠️  SQL generation error: {e}")
            return ""
    
    def _extract_sql(self, response: str) -> str:
        """
        Extract and clean SQL from LLM response.
        """
        sql = re.sub(r"```sql", "", response, flags=re.IGNORECASE)
        sql = re.sub(r"```", "", sql).strip()
        
        if ";" in sql:
            sql = sql.split(";")[0].strip() + ";"
        else:
            sql = sql.rstrip().rstrip(";") + ";"
        
        return sql
    
    def validate_and_sanitize(self, sql: str) -> str:
        """
        Validate and sanitize a SQL query.
        
        Args:
            sql: The SQL query to validate
            
        Returns:
            Sanitized SQL query
            
        Raises:
            ValueError: If the query is not safe
        """
        if not sql:
            raise ValueError("Empty SQL query")
        
        sql_check = sql.upper()
        
        if not sql_check.strip().startswith("SELECT"):
            raise ValueError(f"Only SELECT statements allowed, got: {sql[:50]}")
        
        dangerous_found = _DANGEROUS.search(sql_check)
        if dangerous_found:
            raise ValueError(f"Dangerous keyword found: {dangerous_found.group()}")
        
        if sql.count("(") != sql.count(")"):
            raise ValueError("Unbalanced parentheses in SQL")
        
        return sql
    
    def generate_with_fallback(self, question: str, schema: str, fallback_model: str = "") -> str:
        """
        Generate SQL with fallback to simpler model if primary fails.
        """
        try:
            sql = self.generate_query(question, schema)
            return self.validate_and_sanitize(sql)
        except ValueError as e:
            print(f"⚠️  Primary model failed: {e}, trying fallback")
            
            if fallback_model and fallback_model != self.model:
                original_model = self.model
                self.model = fallback_model
                self._llm = None
                try:
                    sql = self.generate_query(question, schema)
                    return self.validate_and_sanitize(sql)
                finally:
                    self.model = original_model
                    self._llm = None
            raise
    
    def get_table_info(self) -> str:
        """
        Get formatted table information for SQL generation prompts.
        """
        return """
=== DATABASE SCHEMA ===

Table: dva_acts
- id (INTEGER PRIMARY KEY)
- act_name (TEXT) - Full name of the Act (e.g., 'Military Rehabilitation and Compensation Act 2004')
- act_code (TEXT) - Short code (e.g., 'MRCA', 'DRCA', 'VEA')
- description (TEXT)

Table: service_categories
- id (INTEGER PRIMARY KEY)
- category_name (TEXT) - Name of the service category
- act_id (INTEGER FOREIGN KEY) - Links to dva_acts
- standard_of_proof (TEXT) - Required standard of proof

Table: scraped_content
- id (INTEGER PRIMARY KEY)
- title (TEXT) - Page title
- source_type (TEXT) - 'LEGISLATION', 'CLIK', 'DVA_GOV', 'SUPPORT', 'REDDIT'
- source_url (TEXT) - Full URL
- page_text (TEXT) - Full page content
- chunk_index (INTEGER) - Position in page
- chunk_total (INTEGER) - Total chunks from page
- embedding (vector(768)) - nomic-embed-text embedding
- embedding_mxbai (vector(1024)) - mxbai-embed-large embedding
- trust_level (INTEGER) - 1=Legislation, 2=CLIK, 3=DVA.gov, 4=Support, 5=Community
- content_hash (TEXT) - SHA-256 of content
- last_scraped (TIMESTAMP)

View: v_service_standards
- Joins service_categories with dva_acts
- Includes standard_of_proof for each category

View: v_content_summary
- Counts of content by source_type and trust_level
"""


# Singleton instance
_sql_generator = DVASQLGenerator()


def get_sql_generator() -> DVASQLGenerator:
    return _sql_generator
