# YT Download API

Aplicação composta por uma API REST em FastAPI e um frontend estático em HTML puro para baixar vídeos do YouTube.

## Estrutura

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

### 1. Instalar dependências do sistema

`ffmpeg` é fortemente recomendado porque muitos vídeos do YouTube expõem vídeo e áudio em streams separados. Sem ele, a API só conseguirá baixar formatos progressivos que já venham com áudio embutido.

Exemplo em Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

### 2. Criar ambiente virtual e instalar dependências Python

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Subir a API

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Se quiser restringir CORS para origens específicas:

```bash
export ALLOWED_ORIGINS="http://localhost:5500,https://seu-frontend.com"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Servir o frontend estático

O frontend já é servido pela própria API. Abra `http://localhost:8000`.

## Documentação

- Swagger UI: `http://localhost:8000/api-docs`
- OpenAPI JSON: `http://localhost:8000/api-docs/openapi.json`
- Postman Collection: [yt-download-api.postman_collection.json](/workspace/yt-download-api/docs/postman/yt-download-api.postman_collection.json)

## Endpoint principal

`POST /api/v1/downloads`

Payload:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Resposta:

- `200 OK` com o arquivo em stream e `Content-Disposition: attachment`
- `422` para URL inválida
- `400` para falhas de download/processamento

## Docker

Build local:

```bash
docker build -t yt-download-api:local .
docker run --rm -p 8000:8000 yt-download-api:local
```

## CI/CD

### CI

O workflow [ci.yml](/workspace/yt-download-api/.github/workflows/ci.yml) executa:

- lint com `ruff`
- validação sintática com `py_compile`
- build da imagem Docker

### Imagem e deploy

O workflow [deploy-image.yml](/workspace/yt-download-api/.github/workflows/deploy-image.yml):

- builda a imagem Docker
- publica no GHCR
- dispara o webhook do Portainer se `PORTAINER_WEBHOOK_URL` estiver configurado

Secrets esperadas no GitHub:

- `PORTAINER_WEBHOOK_URL`: webhook de atualização do stack no Portainer

O `GITHUB_TOKEN` do próprio Actions é usado para publicar a imagem no GHCR.

## Portainer

O arquivo [portainer-stack.yml](/workspace/yt-download-api/deploy/portainer-stack.yml) pode ser usado como stack base no Portainer.

Exemplo de variável de ambiente do stack:

- `GHCR_IMAGE=ghcr.io/josecldjr/yt-download-api:latest`
