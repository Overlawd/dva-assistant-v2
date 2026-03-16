#!/bin/bash
# Run API on two ports - one for chat, one for status (independent connection pool)
cd /app
python -c "import uvicorn; from api import app; uvicorn.run(app, host='0.0.0.0', port=8502)" &
python -c "import uvicorn; from api import app; uvicorn.run(app, host='0.0.0.0', port=8503)" &
wait
