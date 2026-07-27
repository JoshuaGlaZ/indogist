FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY ml ./ml
COPY docker-entrypoint.sh ./

RUN uv pip install --system --no-cache .
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
