FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Create app directory
WORKDIR /app
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy requirements first for better caching
COPY requirements.txt /app/backend/requirements.txt

# Install Python dependencies and browser binaries
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m playwright install chromium

# Copy application code into a package directory
COPY . /app/backend

# Create necessary directories for app runtime
RUN mkdir -p /app/uploads /app/logs

# Expose port
EXPOSE 8000

# Run the application as a package to support relative imports
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
