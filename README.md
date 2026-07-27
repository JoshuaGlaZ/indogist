---
title: Indogist
emoji: 🐨
colorFrom: indigo
colorTo: red
sdk: docker
pinned: false
---

# Indogist 🇮🇩

**Indogist** is a modern, high-performance Indonesian NLP and automatic text summarization web application built with FastAPI, SQLModel, TensorFlow/TFLite, and Jinja2.

It combines **Statistical Extractive Summarization (TF-IDF & Maximal Marginal Relevance)** with **Named Entity Recognition (NER)** and **Part-of-Speech (POS) tagging** powered by custom TensorFlow/TFLite models and Stanza.

---

## Key Features

- ⚡ **Hybrid & Traditional Extractive Summarization**: Generate concise, key-point summaries using statistical TF-IDF ranking and MMR diversity scoring.
- 🏷️ **Indonesian Named Entity Recognition (NER)**: Detect entities (Persons, Locations, Organizations) using lightweight TFLite / Keras models.
- 🗣️ **Part-of-Speech (POS) Tagging**: Integrated POS tagging pipeline via local Stanza models.
- 🌐 **Bilingual Support (i18n)**: Seamless translation in Indonesian (`id`) and English (`en`) powered by GNU gettext / Babel and Jinja2 i18n.
- 📊 **Metrics & Comparison Analytics**: Evaluate and compare model summarization performance with visualization charts.
- 🚀 **`uv` Package Management**: Fast, reproducible dependency management and CLI tooling.
- 🛡️ **Production Readiness**: CSRF protection, rate limiting (`slowapi`), security headers, and SQLite/PostgreSQL database support.

---

## Quickstart with `uv`

### 1. Installation

Clone the repository and sync dependencies using [`uv`](https://github.com/astral-sh/uv):

```bash
# Clone the repository
git clone https://github.com/JoshuaGlaZ/indogist.git
cd indogist

# Install project dependencies in editable mode
uv pip install -e .
```

### 2. Check ML Models & Pipeline Availability

Run the built-in rich CLI diagnostic tool to verify model files, vectorizers, and POS taggers:

```bash
uv run check-models
```
*Alternatively:* `uv run python -m ml.status`

### 3. Run the Development Server

Start the FastAPI application with Uvicorn:

```bash
uv run uvicorn app.main:app --reload
```

Open your browser at `http://127.0.0.1:8000` (or `http://localhost:7860`).

---

## Project Structure

```
indogist/
├── app/                  # FastAPI web application, routers, database & templating
│   ├── main.py           # Application entrypoint & middlewares
│   ├── models.py         # SQLModel database schemas (User, Summary)
│   ├── routers/          # Route handlers (accounts, summarizer)
│   └── templating.py     # Jinja2 environment & i18n filter bindings
├── ml/                   # Machine learning models & inference pipelines
│   ├── status.py         # Model availability diagnostic CLI
│   ├── ner/              # Named Entity Recognition (loader, predict, models)
│   └── summarization/    # Hybrid & Traditional summarizer algorithms
├── locale/               # Internationalization catalogs (.pot, .po, .mo)
├── tests/                # Comprehensive pytest suite (96+ test cases)
├── pyproject.toml        # uv package configuration & script definitions
└── Dockerfile            # Production Docker image configuration
```

---

## Testing

Run the automated test suite with pytest:

```bash
uv run pytest
```

---

## Docker Deployment

Build and run the Docker container locally:

```bash
# Build the Docker image
docker build -t indogist .

# Run the container
docker run -p 7860:7860 indogist
```

---

## License

MIT License
