# Geoffrey Bot [![Docker Image Version (latest by date)](https://img.shields.io/docker/v/toodaniels/geoffrey_telegram?label=ghcr.io/toodaniels/geoffrey_telegram&sort=date)](https://github.com/toodaniels/geoffrey_telegram/pkgs/container/geoffrey_telegram)

A Telegram bot for downloading and managing media files.

## Features

- 📥 Download media files (videos, music, documents)
- 📂 List downloaded files by type
- 🚦 Queue system for multiple downloads
- 📊 Download progress bar with speed indicator
- 🔒 User access control via Telegram ID

## Requirements

- Python 3.7 or higher
- Telegram Developer Account
- Telegram Bot Token

## Installation

1. Clone the repository:
   ```bash
   git clone [REPOSITORY_URL]
   cd geoffrey_telegram
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 🐳 Docker Usage

You can run Geoffrey Bot using the pre-built Docker image from GitHub Container Registry:

```bash
docker run -d \
  --name geoffrey-bot \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e TELEGRAM_BOT_TOKEN=your_bot_token \
  -e ALLOWED_USERS=your_telegram_id \
  -v /path/to/downloads:/app/downloads \
  ghcr.io/toodaniels/geoffrey_telegram:main
```

### Environment Variables

- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API hash
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `ALLOWED_USERS`: Comma-separated list of Telegram user IDs that are allowed to use the bot
- `DOWNLOAD_PATH`: (Optional) Path to store downloaded files (default: `/app/downloads`)

### Volumes

- `/app/downloads`: Directory where downloaded files will be stored

## Configuration

1. Create a `.env` file in the root directory with the following variables:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   TELEGRAM_BOT_TOKEN=your_bot_token
   ALLOWED_USERS=your_telegram_id,another_id
   DOWNLOAD_PATH=/path/to/downloads
   ```

2. To get your Telegram user ID, you can use [@userinfobot](https://t.me/userinfobot)

## Usage

### Available Commands

- `/start` or `/help` - Show help menu
- `/list video` or `/l video` - List video files
- `/list music` or `/l music` - List music files
- `/list document` or `/l document` - List documents

### How to Use

1. Start the bot:
   ```bash
   python geoffrey_bot.py
   ```

2. Send any media file to the bot to download it.

3. Use commands to list downloaded files.

## File Structure

```
geoffrey_telegram/
├── geoffrey_bot.py    # Main bot code
├── requirements.txt   # Dependencies
├── .env.example      # Example configuration
└── downloads/        # Download directory (auto-created)
    ├── Video/        # Downloaded videos
    ├── Music/        # Music files
    └── Documents/    # Documents
```

## API Centralizada de Descargas (Nuevo)

Se introdujo una API REST centralizada (`api/`) para desacoplar el reporte de progreso de descargas de Telegram, eliminando los problemas de `FloodWait` y rate-limiting.

### Stack

- **FastAPI** + **SQLModel** (SQLAlchemy + Pydantic)
- Base de datos **SQLite** (`geoffrey.db`)
- Documentación interactiva en `/docs` (Swagger UI) y `/redoc` (ReDoc)

### Ejecutar la API

```bash
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/tasks` | Registrar una nueva tarea de descarga |
| `PATCH` | `/tasks/{task_id}` | Actualizar progreso/estado de una tarea |

### Diagrama de flujo de estados

```
PENDING → DOWNLOADING → COMPLETED
                        → FAILED
                        → CANCELLED
```

### `POST /tasks`

Crea una tarea con estado `PENDING`.

**Body:**
```json
{
  "user_id": 1448666148,
  "message_id": 12345,
  "file_name": "video.mp4",
  "file_size_bytes": 1048576
}
```

**Response (201):**
```json
{
  "task_id": "uuid-string",
  "status": "PENDING",
  "message": "Task registered successfully"
}
```

### `PATCH /tasks/{task_id}`

Actualiza parcialmente una tarea (todos los campos son opcionales).

**Body:**
```json
{
  "status": "DOWNLOADING",
  "progress": 0.45,
  "downloaded_bytes": 471859
}
```

**Response (200):** Objeto `DownloadTask` completo.

### Modelo `DownloadTask`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `task_id` | UUID (PK) | Identificador único |
| `user_id` | int | ID del usuario de Telegram |
| `message_id` | int | ID del mensaje en Telegram |
| `file_name` | string | Nombre del archivo |
| `file_size_bytes` | int? | Tamaño en bytes |
| `status` | enum | `PENDING` / `DOWNLOADING` / `COMPLETED` / `FAILED` / `CANCELLED` |
| `progress` | float (0.0-1.0) | Progreso de la descarga |
| `downloaded_bytes` | int | Bytes descargados |
| `error_message` | string? | Mensaje de error si falló |
| `created_at` | datetime | Fecha de creación |
| `updated_at` | datetime | Fecha de última actualización |

### Tests

```bash
poetry run python -m unittest api.test_main
```

### Ejecutar en Desarrollo

Para correr ambos servicios localmente, necesitas dos terminales:

**Terminal 1 — API:**
```bash
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
El flag `--reload` reinicia el servidor automáticamente al detectar cambios en el código.

**Terminal 2 — Bot:**
```bash
DEVELOPMENT=1 poetry run python geoffrey_bot.py
```
La variable `DEVELOPMENT=1` hace que el bot cargue automáticamente el archivo `.env` (ver `AGENTS.md` para más detalles).

El bot se conecta a la API en `http://localhost:8000` por defecto. Asegúrate de que la API esté corriendo antes de iniciar el bot.

---



## Cambios Recientes en el Bot

### Refactor: Desacoplamiento del reporte de progreso (`43f9ca2`)

El bot solía editar los mensajes de Telegram en cada actualización de progreso, lo que provocaba bloqueos por `FloodWait`. Ahora:

1. **Registro centralizado:** Al iniciar una descarga, el bot hace `POST /tasks` para registrar la tarea en la API y recibe un `task_id`.
2. **Reporte throttleado:** El progreso se envía vía `PATCH /tasks/{task_id}` cada **3 segundos** como máximo, usando `aiohttp` de forma asíncrona.
3. **Estados finales:** Al completarse, envía `COMPLETED` con `progress=1.0`; si falla o expira el timeout (6h), envía `FAILED`.
4. **Mensajes de Telegram:** Ahora son secondarios (best-effort); si fallan por `FloodWait`, se registran en log sin afectar la descarga.

### Dependencias añadidas

- `aiohttp` — Cliente HTTP asíncrono para comunicarse con la API
- `fastapi` + `sqlmodel` + `uvicorn` — Servidor y ORM para la API centralizada

### Variables de entorno

Además de las existentes, la API se configura por defecto en `http://localhost:8000` (constante `API_BASE_URL` en `geoffrey_bot.py`). Para producción, se puede modificar o leer de variable de entorno.

## Troubleshooting

If you encounter any issues:
1. Verify all environment variables are set correctly
2. Ensure you have write permissions in the download directory
3. Check the bot logs for error messages

## License

[MIT License](LICENSE)