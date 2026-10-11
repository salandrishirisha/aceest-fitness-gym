
# Stage 1: Official lightweight Python base
FROM python:3.11-slim

# Set environment variables for Python performance & clean output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Install curl for container HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create a secure non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Optimize build caching: copy requirements first
COPY requirements.txt .

# Install dependencies without storing pip cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Set correct ownership for non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user for security
USER appuser

# Expose port
EXPOSE 5000

# Health check instruction matching assignment quality gate
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Production WSGI server command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]