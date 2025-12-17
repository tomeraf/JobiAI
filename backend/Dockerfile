FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create linkedin_data directory for credentials storage
RUN mkdir -p linkedin_data

# Expose port
EXPOSE 8000

# Note: Browser login requires running locally (not in Docker)
# because Playwright needs a display to show the login window.
# Run: cd backend && pip install -r requirements.txt && playwright install chromium
# Then: uvicorn app.main:app --reload

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
