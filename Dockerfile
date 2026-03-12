FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-docker.txt

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000 9000

CMD ["python", "swarm/mcp_server.py"]
