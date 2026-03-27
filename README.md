# YT Download API

Application composed of a FastAPI REST API and a static HTML frontend for downloading YouTube videos.

## Structure

```text
.
├── .github
│   └── workflows
├── api
│   ├── app
│   │   ├── core
│   │   ├── routers
│   │   ├── schemas
│   │   ├── services
│   │   └── utils
│   └── requirements.txt
├── deploy
│   └── portainer-stack.yml
└── frontend
    └── index.html
```

## Setup

### 1. Install system dependencies

`ffmpeg` is strongly recommended because many YouTube videos expose video and audio as separate streams. Without it, the API will only be able to download progressive formats that already include audio.

Example on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

### 2. Create a virtual environment and install Python dependencies

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Start the API

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you want to restrict CORS to specific origins:

```bash
export ALLOWED_ORIGINS="http://localhost:5500,https://your-frontend.com"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Serve the frontend

The frontend is already served by the API itself. Open `http://localhost:8000`.

## Documentation

- Swagger UI: `http://localhost:8000/api-docs`
- OpenAPI JSON: `http://localhost:8000/api-docs/openapi.json`
- Postman Collection: [yt-download-api.postman_collection.json](/workspace/yt-download-api/docs/postman/yt-download-api.postman_collection.json)

## Main endpoint

`POST /api/v1/downloads`

Payload:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Response:

- `200 OK` with the file streamed back and `Content-Disposition: attachment`
- `422` for an invalid URL
- `400` for download or processing failures

## Docker

Build local:

```bash
docker build -t yt-download-api:local .
docker run --rm -p 8000:8000 yt-download-api:local
```

## CI/CD

### CI

The workflow [ci.yml](/workspace/yt-download-api/.github/workflows/ci.yml) runs:

- lint with `ruff`
- syntax validation with `py_compile`
- Docker image build

### Image and deployment

The workflow [deploy-image.yml](/workspace/yt-download-api/.github/workflows/deploy-image.yml):

- builds the Docker image
- publishes it to GHCR
- triggers the Portainer webhook when `PORTAINER_WEBHOOK_URL` is configured

Expected GitHub secrets:

- `PORTAINER_WEBHOOK_URL`: Portainer stack update webhook

The built-in `GITHUB_TOKEN` from GitHub Actions is used to publish the image to GHCR.

## Portainer

The file [portainer-stack.yml](/workspace/yt-download-api/deploy/portainer-stack.yml) can be used as the base stack in Portainer.

Example stack environment variable:

- `GHCR_IMAGE=ghcr.io/josecldjr/yt-download-api:latest`
