FROM mcr.microsoft.com/playwright/python:v1.49-jammy

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files for dependency resolution
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY mcp_container/ mcp_container/
COPY adapters/ adapters/

# Install dependencies (frozen = no re-resolve)
RUN uv sync --frozen

# Install playwright browsers
RUN uv run playwright install chromium --with-deps

# Expose HTTP (stdio/non-streaming) and SSE (streamable) ports
EXPOSE 8080 8081 8082 8083 8084 8085
EXPOSE 9100 9101 9102 9103 9104 9105

# Start the supervisor
CMD ["uv", "run", "python", "-m", "mcp_container.supervisor"]
