# YT Download API

Aplicação composta por uma API REST em FastAPI e um frontend estático em HTML puro para baixar vídeos do YouTube.

## Estrutura

```text
.
├── api
│   ├── app
│   │   ├── core
│   │   ├── routers
│   │   ├── schemas
│   │   ├── services
│   │   └── utils
│   └── requirements.txt
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

```bash
cd frontend
python3 -m http.server 5500
```

Abra `http://localhost:5500`.

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
