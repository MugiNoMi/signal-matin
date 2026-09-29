# Image autonome : Python, Chromium et ses dépendances système sont fournis
# par l'image Playwright officielle (version alignée sur uv.lock).
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV TZ=Europe/Paris \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --extra google --extra ai

COPY . .
RUN uv sync --frozen --extra google --extra ai

# config.yaml, .env et output/ sont montés depuis l'hôte : aucun secret dans l'image.
ENTRYPOINT ["signal-matin"]
CMD ["generate"]
