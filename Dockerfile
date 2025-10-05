FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash mcp-user

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install -e .

# Copy application code
COPY src/ ./src/
COPY .env.example ./

# Create data directory
RUN mkdir -p /app/data && chown -R mcp-user:mcp-user /app

# Switch to application user
USER mcp-user

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import asyncio; from mcp_ai_commit.database import get_database; asyncio.run(get_database())" || exit 1

# Run the MCP server
CMD ["python", "-m", "mcp_ai_commit.server"]