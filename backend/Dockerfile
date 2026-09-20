FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir aiosqlite fastapi httpx itsdangerous "pydantic-settings>=2.6,<3.0" "uvicorn[standard]>=0.30,<1.0"
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
