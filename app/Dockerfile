FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    playwright \
    beautifulsoup4 \
    lxml \
    html5lib \
    sqlalchemy \
    psycopg2-binary \
    pgvector \
    langchain-core \
    langchain-community \
    langchain-ollama \
    ollama \
    streamlit \
    streamlit-autorefresh \
    streamlit-javascript \
    python-dotenv \
    requests \
    pyyaml \
    pandas \
    psutil \
    fastapi \
    uvicorn \
    nvidia-ml-py3

RUN playwright install chromium --with-deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "ui.py", "--server.port=8501", "--server.address=0.0.0.0"]
