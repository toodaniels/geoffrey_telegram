# Use an official Python runtime as a parent image
FROM python:3.10-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.2

# Set working directory
WORKDIR /app

# Copy only necessary files for dependency installation
COPY pyproject.toml ./

# Install dependencies and generate lock file if it doesn't exist
RUN poetry config virtualenvs.create false \
    && (test -f poetry.lock || poetry lock --no-update) \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Final stage
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_ENV=true \
    PYTHONPATH=/app

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy only the necessary files
COPY geoffrey_bot.py .

# Run the bot when the container launches
CMD ["python", "geoffrey_bot.py"]
