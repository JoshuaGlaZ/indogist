FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader punkt punkt_tab

COPY --chown=user:user . .

EXPOSE 7860

COPY --chown=user:user docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]