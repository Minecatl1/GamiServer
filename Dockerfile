FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    tar \
    xz-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ templates/

# Expose port
EXPOSE 5000

# Create entrypoint script
RUN echo '#!/bin/bash\nset -e\npython app.py' > /entrypoint.sh && chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
