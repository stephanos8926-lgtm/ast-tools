FROM python:3.13-slim AS builder

# Build deps for sentence-transformers, sqlite-vec, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install with all deps + HTTP transport extras
RUN pip install --no-cache-dir \
    uvicorn \
    starlette \
    aiohttp \
    -e .

# ── Runtime stage ─────────────────────────────────────
FROM python:3.13-slim

# Runtime deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

EXPOSE 8932

# Health check — MCP list_tools endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request, json; \
        req = urllib.request.Request('http://localhost:8932/mcp', \
            data=json.dumps({'method':'tools/list'}).encode(), \
            headers={'Content-Type':'application/json'}); \
        resp = urllib.request.urlopen(req, timeout=5); \
        assert resp.status == 200" || exit 1

CMD ["ast-tools-server", "--mode", "remote", "--host", "0.0.0.0", "--port", "8932"]
