FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install core deps (skip heavy ML — using remote engine)
RUN pip install --no-cache-dir \
        mcp anyio pyyaml lsprotocol uvicorn starlette aiohttp httpx \
        libcst jedi watchdog tree-sitter sqlite-vec sqlparse jsonschema \
        tiktoken numpy rich \
        && pip install --no-cache-dir --no-deps .

ENV AST_TOOLS_EMBEDDING_BACKEND=remote
ENV AST_TOOLS_REMOTE_INFERENCE_URL=http://localhost:8300
EXPOSE 8932

CMD ["ast-tools-server", "--mode", "remote", "--host", "0.0.0.0", "--port", "8932"]