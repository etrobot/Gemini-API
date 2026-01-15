# Docker Setup Guide

This guide explains how to use Docker with the Gemini WebAPI project.

## Prerequisites

- Docker Engine (20.10 or later)
- Docker Compose (2.0 or later)

## Quick Start

### 1. Setup Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini credentials:
- `SECURE_1PSID`: Your `__Secure-1PSID` cookie value from gemini.google.com
- `SECURE_1PSIDTS`: Your `__Secure-1PSIDTS` cookie value from gemini.google.com

### 2. Build the Docker Image

```bash
docker-compose build
```

### 3. Run the Container

#### Development Mode (Interactive)

Start the container in the background:

```bash
docker-compose up -d
```

Enter the container to run Python code interactively:

```bash
docker-compose exec gemini-webapi bash
```

Inside the container, you can:

```bash
# Run Python interactive shell
python

# Run a specific test
python -m pytest tests/test_client_features.py::TestGeminiClient::test_successful_request -v

# Run all tests
python -m pytest tests/ -v
```

#### Run Tests Directly

```bash
docker-compose --profile test up test
```

### 4. Stop the Container

```bash
docker-compose down
```

## Docker Commands Cheatsheet

### Build and Run

```bash
# Build the image
docker-compose build

# Start services in background
docker-compose up -d

# Start and view logs
docker-compose up

# Rebuild and start
docker-compose up --build
```

### Testing

```bash
# Run all tests
docker-compose --profile test up test

# Run tests with live logs
docker-compose --profile test up test --abort-on-container-exit

# Run specific test file
docker-compose exec gemini-webapi python -m pytest tests/test_client_features.py -v
```

### Development

```bash
# Access container shell
docker-compose exec gemini-webapi bash

# View logs
docker-compose logs -f gemini-webapi

# Restart service
docker-compose restart gemini-webapi
```

### Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Remove everything including images
docker-compose down -v --rmi all
```

## Example Python Usage in Container

After entering the container with `docker-compose exec gemini-webapi bash`:

```python
import asyncio
from gemini_webapi import GeminiClient

async def main():
    client = GeminiClient("<your_1PSID>", "<your_1PSIDTS>")
    await client.init()
    
    response = await client.generate_content("Hello, Gemini!")
    print(response.text)

asyncio.run(main())
```

## Traefik Integration

If you're using Traefik as a reverse proxy with Let's Encrypt SSL, the docker-compose.yml includes the necessary labels and network configuration.

### Prerequisites

1. Traefik must be running with:
   - External network named `traefik`
   - Let's Encrypt certificate resolver named `letsencrypt`
   - HTTP entrypoint named `web` (port 80)
   - HTTPS entrypoint named `websecure` (port 443)

2. Create the Traefik network (if not exists):
   ```bash
   docker network create traefik
   ```

### Configuration

1. Set your domain in `.env`:
   ```bash
   DOMAIN=gemini.yourdomain.com
   ```

2. Start the service:
   ```bash
   docker-compose up -d
   ```

The service will automatically:
- Get Let's Encrypt SSL certificate for your domain
- Redirect HTTP to HTTPS
- Be accessible at https://gemini.yourdomain.com

### Labels Included

The docker-compose.yml includes these Traefik labels:
- `traefik.enable=true` - Enable Traefik
- HTTPS router with Let's Encrypt cert resolver
- HTTP to HTTPS redirect
- Service port configuration (8000)

### Disable Traefik

To use without Traefik, comment out or remove:
- The `networks` section
- All `labels` starting with `traefik.`

## Troubleshooting

### Permission Issues

If you encounter permission issues, ensure the mounted volumes have correct permissions:

```bash
chmod -R 755 src/ tests/ assets/
```

### Container Won't Start

Check the logs:

```bash
docker-compose logs gemini-webapi
```

### Credential Issues

Make sure your `.env` file has valid credentials from gemini.google.com cookies.

## Volume Mounts

The following directories are mounted for live development:

- `./src` → `/app/src` - Source code
- `./tests` → `/app/tests` - Test files
- `./assets` → `/app/assets` - Asset files

Changes to these directories are immediately reflected in the container.
