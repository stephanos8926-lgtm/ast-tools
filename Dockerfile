FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .

RUN pip install uv && \
    uv sync --only-group dev --no-dev && \
    uv build

FROM python:3.12-slim

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        git \
        tree-sitter-cli \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl

EXPOSE 8000

ENTRYPOINT ["python3", "-m", "ast_tools_server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
