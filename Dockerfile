FROM python:3.12-alpine

WORKDIR /app

# Install docker-cli and other dependencies
RUN apk add --no-cache docker-cli curl

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

# Create config directory
RUN mkdir -p /config

ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/config/config.json

EXPOSE 5000

CMD ["python", "-m", "app.main"]
