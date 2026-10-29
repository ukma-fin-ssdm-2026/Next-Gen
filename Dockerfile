FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app
RUN mkdir -p /var/lib/baraholka/uploads && chown -R app:app /var/lib/baraholka/uploads

COPY requirements.txt requirements.lock ./
RUN python -m pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    --require-hashes \
    --only-binary=:all: \
    -r requirements.lock

COPY --chown=app:app src ./src

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
