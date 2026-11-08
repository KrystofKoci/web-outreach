# web-outreach pipeline – Python 3.12 + Chromium (Playwright)
#
# Build from the REPO ROOT (the package must be importable as `pipeline`):
#   docker build -f pipeline/Dockerfile -t web-outreach-pipeline .
# Run (previews are served by Caddy from the shared volume, see infra/):
#   docker run --env-file .env -p 8077:8077 -v /srv/nahled:/srv/nahled web-outreach-pipeline
#
# The base image already contains Python 3.12, Chromium and all system
# libraries Playwright needs; the pinned playwright wheel must match the tag.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PREVIEW_DIR=/srv/nahled \
    API_PORT=8077

WORKDIR /app

COPY pipeline/requirements.txt /app/pipeline/requirements.txt
RUN pip install --no-cache-dir -r /app/pipeline/requirements.txt

# fonts with Czech glyphs for the Pillow compare/og images and for Chromium fallbacks
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

COPY pipeline /app/pipeline

RUN mkdir -p /srv/nahled && chmod 755 /srv/nahled

EXPOSE 8077
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8077/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "pipeline.cli", "serve"]
