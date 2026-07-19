# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN addgroup --system grovello && adduser --system --ingroup grovello grovello
COPY services/api/pyproject.toml ./
COPY services/api/src ./src
RUN pip install --no-cache-dir .
USER grovello
EXPOSE 8000
CMD ["uvicorn", "grovello.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
