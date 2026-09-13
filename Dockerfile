# One container = the whole product: the API, the LiteLLM gateway (roles
# small/mid/strong), the full parser ladder (text layer -> OCR -> layout), and
# the built web UI served from "/". Postgres and the object store are managed
# services outside the container; see infra/deploy/README.md.
#
# Any Docker host runs this — Hugging Face Spaces, Render, Koyeb, a VM. It
# listens on $PORT (7860 by default, which is what Spaces route to).

# ---- web: the Vite build -----------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
# Same-origin: the API serves this build, so the client uses relative URLs.
ENV VITE_API_BASE=""
RUN npm run build

# ---- api ----------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# OpenCV (behind the OCR engine) needs these two shared libraries even when
# no window is ever opened. Spaces run the container as uid 1000 with a
# writable $HOME; do the same everywhere so behaviour does not depend on the host.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

# The API and the packages it depends on by path (agents/, adapters/).
COPY --chown=app:app agents/ agents/
COPY --chown=app:app adapters/ adapters/
COPY --chown=app:app apps/api/ apps/api/
COPY --chown=app:app infra/ infra/
# The gold set is read at runtime by the Evaluation screen and the Model Lab.
COPY --chown=app:app tests/gold/ tests/gold/

# Base dependencies exactly as locked.
RUN cd apps/api && uv sync --frozen --no-dev

# The ML extra, on CPU. The lockfile resolves torch against PyPI, which on
# Linux means the CUDA build plus several gigabytes of driver libraries a
# CPU host never loads. Take the CPU wheel from the official index instead,
# then the rest of the extra on top of it.
ARG WITH_ML=1
RUN if [ "$WITH_ML" = "1" ]; then \
      cd apps/api && \
      uv pip install --python .venv --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.13.0" torchvision && \
      uv pip install --python .venv "docling>=2.15" "rapidocr>=3.0" "onnxruntime>=1.17" && \
      mkdir -p /app/models && \
      .venv/bin/python -m docling.cli.tools models download -o /app/models \
        layout tableformer rapidocr && \
      chown -R app:app /app/models; \
    fi
# Docling reads its models from here instead of downloading on first use —
# a restart must not cost a download, and the first parse must not be slow.
ENV DOCLING_ARTIFACTS_PATH=/app/models

# The gateway, in its own environment so its pins never fight the API's.
# The Langfuse callback needs the langfuse client on the gateway's path.
RUN uv venv /opt/litellm && \
    uv pip install --python /opt/litellm "litellm[proxy]>=1.75,<2" "langfuse>=2.50,<3"

# The web build, served by the API from "/".
COPY --from=web --chown=app:app /web/dist /app/web
ENV WEB_DIST=/app/web

# No recursive chown here: on a layered filesystem it rewrites every file it
# touches into a new layer, and that alone was 2 GB. Everything the process
# needs to read is world-readable; nothing under /app is written at runtime.
COPY --chown=app:app --chmod=755 infra/deploy/start.sh /app/start.sh

USER app
ENV HOME=/home/app \
    PATH=/app/apps/api/.venv/bin:$PATH \
    PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=10s --start-period=180s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/health')" || exit 1

CMD ["/app/start.sh"]
