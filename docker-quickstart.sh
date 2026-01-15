#!/bin/bash
# Quick start script for Docker setup

set -e

echo "======================================"
echo "Gemini WebAPI Docker Quick Start"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file. Please edit it with your credentials:"
    echo "   - SECURE_1PSID"
    echo "   - SECURE_1PSIDTS"
    echo ""
    echo "You can get these from your browser cookies when logged into gemini.google.com"
    echo ""
    read -p "Press Enter after updating .env file..."
fi

echo "Building Docker image..."
docker-compose build

echo ""
echo "✓ Build complete!"
echo ""
echo "Available commands:"
echo "  docker-compose up -d              # Start container in background"
echo "  docker-compose exec gemini-webapi bash  # Access container shell"
echo "  docker-compose --profile test up test   # Run tests"
echo "  docker-compose down               # Stop container"
echo ""
echo "Or use the Makefile:"
echo "  make up       # Start container"
echo "  make shell    # Open shell"
echo "  make test     # Run tests"
echo "  make down     # Stop container"
echo ""
