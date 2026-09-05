FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy entrypoint and healthcheck scripts, make executable
COPY entrypoint.sh /entrypoint.sh
COPY healthcheck.sh /healthcheck.sh
RUN chmod +x /entrypoint.sh /healthcheck.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Health check — dispatches on PROCESS_TYPE since the worker process (see
# entrypoint.sh) has no HTTP server for curl to check.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD /healthcheck.sh

# Run the entrypoint which runs migrations then starts the app
CMD ["/entrypoint.sh"]