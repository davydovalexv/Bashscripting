FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir -e ".[ui]"

ENV DV_CONFIG_PATH=/app/config/docker.yaml
ENV PYTHONUNBUFFERED=1

CMD ["dv-agent", "--help"]
