# CrewCraft Gateway Docker Image
#
# Build:
#   docker build -t crewcraft-gateway .
#
# Run:
#   docker run -p 8000:8000 -p 8765:8765 -v ./data:/data crewcraft-gateway

FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev

COPY app/ app/

ENV PYTHONPATH=/app
ENV CREWCRAFT_DATA_DIR=/data
ENV CREWCRAFT_WS_HOST=0.0.0.0

EXPOSE 8000 8765

CMD ["uv", "run", "python", "-m", "app.gateway.main"]
