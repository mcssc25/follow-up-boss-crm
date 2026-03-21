FROM python:3.12-slim

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Collect static files (may fail before migrations, that's OK)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
