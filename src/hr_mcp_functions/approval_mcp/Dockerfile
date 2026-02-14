FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY approval_mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

# Copy shared modules first
COPY shared/ /app/shared/

# Copy application code
COPY approval_mcp/ /app/approval_mcp/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8080

WORKDIR /app/approval_mcp
CMD ["python", "server.py"]
