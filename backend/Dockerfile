# Pinned to bookworm on purpose — the unqualified python:3.11-slim tag has
# rolled forward to trixie, and playwright's --with-deps package list does
# not know trixie's renamed font packages yet (ttf-unifont became
# fonts-unifont), which makes apt-get fail mid-build.
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright needs its own browser binary + a pile of OS-level libs
# (font rendering, GTK, audio stubs, etc) that aren't in the slim image
# by default. `playwright install --with-deps` handles both in one go
# (the --with-deps apt step needs root, so it runs before the USER switch
# below). Browsers go to a shared path, not /root, so the non-root runtime
# user can still find them.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/uploads

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Drop root: run as an unprivileged user so a process compromise cannot
# trivially write the image or escalate. It needs read of the browsers and
# write of the uploads cache directory.
RUN useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app /ms-playwright
USER appuser

EXPOSE 8000

# --reload is for local dev only (docker-compose overrides nothing, but the
# bind mount there makes it useful). In production it wastes memory watching
# files that never change. docker-compose keeps hot reload via its own
# command override below if you ever want it back locally.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
