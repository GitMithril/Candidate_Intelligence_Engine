FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# Install CPU-only torch first so sentence-transformers doesn't pull a CUDA wheel (~2GB).
RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser + all system-level dependencies it needs.
RUN playwright install --with-deps chromium

# Pre-download the embedding model at build time so the first API call isn't slow.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
