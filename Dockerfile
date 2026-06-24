# CrewCraft Gateway Docker Image
#
# Build:
#   docker build -t crewcraft-gateway .
#
# Run:
#   docker run -p 8000:8000 -p 8765:8765 -v ./data:/data crewcraft-gateway

FROM python:3.13-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.30.0 \
    typer>=0.12.0 \
    httpx>=0.27.0 \
    websockets>=12.0 \
    deepagents>=0.6.0 \
    python-dotenv>=1.0.0 \
    docker>=7.0

# Copy application code
COPY app/ app/
COPY pyproject.toml .

ENV PYTHONPATH=/app
ENV CREWCRAFT_DATA_DIR=/data
ENV CREWCRAFT_WS_HOST=0.0.0.0

EXPOSE 8000 8765

CMD ["python", "-m", "app.gateway.main"]
