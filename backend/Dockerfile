FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright needs its own browser binary + a pile of OS-level libs
# (font rendering, GTK, audio stubs, etc) that aren't in the slim image
# by default. `playwright install --with-deps` handles both in one go.
# This is the single biggest reason the image is heavier than before —
# worth it, it's the only way to actually drive a real Chromium instance
# to fill out a Google Form.
RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/uploads

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# --reload is for local dev only (docker-compose overrides nothing, but the
# bind mount there makes it useful). In production it wastes memory watching
# files that never change. docker-compose keeps hot reload via its own
# command override below if you ever want it back locally.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
