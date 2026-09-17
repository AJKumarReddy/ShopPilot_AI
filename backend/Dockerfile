FROM python:3.13-slim AS builder
WORKDIR /build
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
RUN pip install --no-cache-dir --prefix=/install .
FROM python:3.13-slim
RUN useradd --create-home --uid 10001 app
COPY --from=builder /install /usr/local
WORKDIR /workspace
COPY --chown=app:app backend ./backend
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app configs ./configs
COPY --chown=app:app data/samples ./data/samples
ENV PYTHONPATH=/workspace/backend PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
