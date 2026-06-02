FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_DEBUG=False
ENV DJANGO_ALLOWED_HOSTS=.hf.space,.huggingface.co
ENV DJANGO_SSL_REDIRECT=False
ENV DJANGO_HSTS_SECONDS=31536000
ENV DJANGO_SESSION_COOKIE_SECURE=True
ENV DJANGO_CSRF_COOKIE_SECURE=True

WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader punkt punkt_tab

COPY --chown=user:user . .

RUN DB_PASSWORD="dummy" \
    DB_USER="dummy" \
    DB_HOST="localhost" \
    DB_PORT="5432" \
    DB_NAME="dummy" \
    python manage.py collectstatic --noinput

EXPOSE 7860

COPY --chown=user:user docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]