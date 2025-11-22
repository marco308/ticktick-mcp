# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ticktick_mcp/ ticktick_mcp/
COPY setup.py .
COPY README.md .

# Install the package
RUN pip install --no-cache-dir -e .

# Expose port for OAuth gateway and SSE transport
EXPOSE 8080

# Health check endpoint (gateway provides /health endpoint)
# Using Python since curl is not available in slim image
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Start script that runs both FastMCP server and OAuth gateway
COPY start-remote.sh /app/start-remote.sh
RUN chmod +x /app/start-remote.sh

# Run the start script
# Note: Users should mount their .env file or pass environment variables
CMD ["/app/start-remote.sh"]
