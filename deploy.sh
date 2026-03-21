#!/bin/bash
set -e
echo "Pulling latest code..."
git pull origin master
echo "Building and starting services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
echo "Running migrations..."
docker-compose exec web python manage.py migrate --noinput
echo "Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput
echo "Deployment complete!"
