# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN addgroup --system grovello && adduser --system --ingroup grovello grovello
COPY services/api /app/services/api
COPY services/workers /app/services/workers
RUN pip install --no-cache-dir /app/services/api /app/services/workers
USER grovello
CMD ["grovello-worker"]
