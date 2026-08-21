# Nischen Explorer – Deployment

## GHCR image

```text
ghcr.io/z3uss3l/nischen-explorer:latest
```

## Start with Docker Compose

1. Copy `.env.example` to `.env` and add the API credentials you actually use.
2. Start the published image:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

3. Open:

```text
http://localhost:8501
```

The SQLite database is persisted in the `app_data` Docker volume.

## Private GHCR package

If the package is private, authenticate before pulling:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Direct Docker start

```bash
docker run -d \
  --name nischen-explorer \
  -p 8501:8501 \
  --env-file .env \
  -v nischen_explorer_data:/data \
  -e DATABASE_URL=sqlite:////data/nischen_explorer.db \
  --restart unless-stopped \
  ghcr.io/z3uss3l/nischen-explorer:latest
```
