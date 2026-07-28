FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Layer 1: Dependencies (cached unless pyproject.toml / lock changes)
COPY pyproject.toml README.md ./
RUN uv pip install --system .

# Layer 2: Application source (invalidates cache on code changes)
COPY app ./app
COPY ml ./ml
COPY locale ./locale
COPY templates ./templates
COPY static ./static

# Download NLTK data for sentence tokenization
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860

# Use simple uvicorn entrypoint for FastAPI on Hugging Face Spaces
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
