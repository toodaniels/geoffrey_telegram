import os
import re
import sys 
import asyncio
import logging
from guessit import guessit
import time
from dataclasses import dataclass
from typing import Optional
from functools import partial
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# Download queue and worker setup
download_queue = asyncio.Queue()
download_lock = asyncio.Lock()
active_downloads = {}

@dataclass
class DownloadTask:
    message: any
    filename: str
    download_path: str
    event: events.NewMessage.Event
    msg: any = None
    queue_msg: any = None  # Store the queue message
    progress_callback: callable = None
    retry_count: int = 0
    task_id: Optional[str] = None  # Store the API task UUID


if os.getenv('DEVELOPMENT'):
    from dotenv import load_dotenv
    load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', []).split(',')
DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

client = TelegramClient(
    'geoffrey', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def report_progress(received_bytes, total, task_id, http_session, last_update_info):
    """
    Sends throttled download progress updates to the centralized API.
    Only sends requests if at least 3 seconds have elapsed since the last update,
    or if the download is complete.
    """
    if not task_id:
        return
    current_time = time.time()
    last_update = last_update_info.get("last_update", 0)
    is_finished = received_bytes >= total
    progress = float(received_bytes) / total if total > 0 else 0.0

    if current_time - last_update >= 3.0 or is_finished:
        last_update_info["last_update"] = current_time
        payload = {
            "status": "DOWNLOADING",
            "progress": progress,
            "downloaded_bytes": received_bytes
        }
        try:
            async with http_session.patch(f"{API_BASE_URL}/tasks/{task_id}", json=payload) as response:
                if response.status != 200:
                    logging.error(f"Failed to update progress for task {task_id}. Status: {response.status}")
        except Exception as e:
            logging.error(f"Error reporting progress for task {task_id}: {str(e)}")


def get_file_type(mime_type):
    print(f"File type {mime_type}")
    video_mime_types = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska']
    audio_mime_types = ['audio/mpeg', 'audio/vnd.wav', 'audio/x-flac']
    document_mime_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']

    if mime_type in video_mime_types:
        return 'Video'
    elif mime_type in audio_mime_types:
        return 'Music'
    elif mime_type in document_mime_types:
        return 'Documents'
    else:
        return None
    
def check_filename_type(filename):
    # Detectar tipo de archivo
    file_type = get_file_type(filename)

    return file_type is not None

def check_filename_exists(download_filename):
    return os.path.exists(download_filename)

def get_mp3_metadata(file_path):
    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.mp3 import MP3

        audio = MP3(file_path, ID3=EasyID3)
        title = audio.get('title', ['Unknown Title'])[0]
        artist = audio.get('artist', ['Unknown Artist'])[0]
        album = audio.get('album', ['Unknown Album'])[0]

        return {
            'title': title,
            'artist': artist,
            'album': album
        }
    except ImportError:
        logging.warning("mutagen library is not installed. Metadata extraction will be skipped.")
        return None
    except Exception as e:
        logging.error(f"Error extracting metadata: {str(e)}")
        return None

async def show_help(event):
    """Show available commands and their descriptions."""
    help_text = """
    🤖 *Comandos disponibles:*

    📥 *Descargar archivos:*
    - Simplemente envía cualquier archivo (video, música o documento) para descargarlo.

    📂 *Listar archivos:*
    `/listar video` o `/list video` - Muestra archivos de video
    `/listar music` o `/list music` - Muestra archivos de música
    `/listar document` o `/list document` - Muestra documentos

    ❓ *Ayuda:*
    `/help` o `/ayuda` - Muestra este mensaje de ayuda
    """
    await event.reply(help_text, parse_mode='markdown')


async def list_files_by_type(event, file_type):
    """List files in the specified folder by type."""
    try:
        # Map user-friendly type to folder name
        type_to_folder = {
            'video': 'Video',
            'music': 'Music',
            'document': 'Documents',
            'videos': 'Video',
            'musics': 'Music',
            'documentos': 'Documents',
            'documento': 'Documents',
            'música': 'Music',
            'músicas': 'Music',
            'cancion': 'Music',
            'canciones': 'Music',
            'vídeo': 'Video',
            'vídeos': 'Video'
        }
        
        folder_name = type_to_folder.get(file_type.lower())
        if not folder_name:
            await event.reply(
                "❌ Tipo de archivo no válido.\n\n"
                "📋 Usa uno de estos comandos:\n"
                "/listar video - Muestra archivos de video\n"
                "/listar music - Muestra archivos de música\n"
                "/listar document - Muestra documentos"
            )
            return
            
        folder_path = os.path.join(DOWNLOAD_PATH, folder_name)
        
        if not os.path.exists(folder_path):
            await event.reply(f"❌ No se encontró la carpeta para {folder_name}")
            return
            
        files = [f for f in os.listdir(folder_path) 
                if os.path.isfile(os.path.join(folder_path, f))]
        
        if not files:
            await event.reply(f"📂 La carpeta de {folder_name} está vacía")
            return
            
        # Sort files by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)), reverse=True)
        
        # Format file sizes
        def format_size(size_bytes):
            if size_bytes == 0:
                return "0B"
            size_names = ("B", "KB", "MB", "GB", "TB")
            i = 0
            while size_bytes >= 1024 and i < len(size_names) - 1:
                size_bytes /= 1024
                i += 1
            return f"{size_bytes:.1f}{size_names[i]}"

        # Split files into chunks to avoid message length limits
        chunk_size = 10
        file_chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]
        
        for i, chunk in enumerate(file_chunks, 1):
            file_list = []
            for file in chunk:
                file_path = os.path.join(folder_path, file)
                file_size = format_size(os.path.getsize(file_path))
                file_list.append(f"• `{file}` ({file_size})")
                
            await event.reply(
                f"📂 **Archivos en {folder_name}**\n\n" +
                "\n".join(file_list) + 
                f"\n\n📋 Página {i}/{len(file_chunks)} • Total: {len(files)} archivos"
            )
            
    except Exception as e:
        await event.reply(f"❌ Error al listar archivos: {str(e)}")
        print(f"Error listing files: {str(e)}")

def guess_filename(filename):
    """Guess file information using guessit."""
    try:
        import guessit
        info = guessit.guessit(filename)
        return info
    except ImportError:
        return None

async def download_worker(http_session: aiohttp.ClientSession):
    """Worker that processes download tasks from the queue."""
    while True:
        task = await download_queue.get()
        local_id = id(task)
        
        try:
            async with download_lock:
                if local_id in active_downloads:
                    return  # Skip if task is already being processed
                    
                active_downloads[local_id] = task
                
                # Register the task in the centralized API before downloading
                payload = {
                    "user_id": task.event.sender_id,
                    "message_id": task.message.id,
                    "file_name": task.filename,
                    "file_size_bytes": task.message.file.size if task.message.file else None
                }
                
                try:
                    async with http_session.post(f"{API_BASE_URL}/tasks", json=payload) as response:
                        if response.status == 201:
                            data = await response.json()
                            task.task_id = data["task_id"]
                            print(f"Registered task in API. Task UUID: {task.task_id}")
                        else:
                            print(f"Failed to register task in API. Status: {response.status}")
                except Exception as e:
                    print(f"Error registering task in API: {str(e)}")
                
                # Create initial progress message in Telegram (best-effort)
                queue_size = download_queue.qsize()
                downloading_txt = (
                    f"⬇️ **En cola: {queue_size}**\n"
                    f"**Descargando:** `{task.filename}`\n"
                    f"💾 Tamaño: {task.message.file.size/1024/1024:.1f}MB"
                )
                
                try:
                    task.msg = await task.event.reply(downloading_txt)
                except Exception as e_reply:
                    logging.warning(f"Could not send Telegram reply (FloodWait?): {e_reply}")
                    task.msg = None

                try:
                    # Set up the throttled progress callback
                    last_update_info = {"last_update": 0}
                    task.progress_callback = partial(
                        report_progress,
                        task_id=task.task_id,
                        http_session=http_session,
                        last_update_info=last_update_info
                    )
                    
                    # Add timeout to prevent hanging on slow downloads
                    download_task = asyncio.create_task(
                        task.message.download_media(
                            file=task.download_path,
                            progress_callback=task.progress_callback
                        )
                    )
                    
                    # Wait for download to complete with timeout (6 hours)
                    await asyncio.wait_for(download_task, timeout=6*3600)
                    
                    # Update message when download is complete
                    file_size = os.path.getsize(task.download_path)
                    
                    # Update API task status to COMPLETED
                    if task.task_id:
                        payload = {
                            "status": "COMPLETED",
                            "progress": 1.0,
                            "downloaded_bytes": file_size
                        }
                        try:
                            async with http_session.patch(f"{API_BASE_URL}/tasks/{task.task_id}", json=payload) as response:
                                if response.status != 200:
                                    print(f"Failed to mark task completed in API: {response.status}")
                        except Exception as e_api:
                            print(f"Error marking task completed in API: {str(e_api)}")
                    
                    completion_msg = await task.msg.reply(
                        "✅ **Descarga completada**\n"
                        f"📁 `{task.filename}`\n"
                        f"💾 Tamaño: {file_size/1024/1024:.1f}MB\n"
                        f"📂 Guardado en: `{task.download_path}`"
                    )
                    print(f'\n✅ Downloaded to {task.download_path}')
                    
                    # Delete the progress and queue messages after a short delay
                    await asyncio.sleep(2)  # Give user time to see the completion message
                    try:
                        await task.msg.delete()
                    except Exception as e:
                        print(f"Could not delete progress message: {str(e)}")
                    
                    try:
                        if task.queue_msg:
                            await task.queue_msg.delete()
                    except Exception as e:
                        print(f"Could not delete queue message: {str(e)}")
                    
                except asyncio.TimeoutError:
                    error_msg = (
                        f"⏱️ **Tiempo de espera agotado**\n"
                        f"`{task.filename}`\n"
                        "La descarga tomó demasiado tiempo. Inténtalo de nuevo más tarde."
                    )
                    print(f'\n❌ Download timed out: {task.filename}')
                    
                    # Update API task status to FAILED
                    if task.task_id:
                        payload = {
                            "status": "FAILED",
                            "error_message": "Download timed out"
                        }
                        try:
                            async with http_session.patch(f"{API_BASE_URL}/tasks/{task.task_id}", json=payload) as response:
                                if response.status != 200:
                                    print(f"Failed to mark task failed in API: {response.status}")
                        except Exception as e_api:
                            print(f"Error marking task failed in API: {str(e_api)}")
                            
                    if task.msg:
                        try:
                            await task.msg.edit(error_msg)
                        except Exception as edit_err:
                            print(f"Failed to edit message to timeout: {str(edit_err)}")
                        
                except Exception as e:
                    error_msg = (
                        f"❌ **Error al descargar**\n"
                        f"`{task.filename}`\n"
                        f"Error: {str(e)}"
                    )
                    print(f'\n❌ Error downloading {task.filename}: {str(e)}')
                    
                    # Update API task status to FAILED
                    if task.task_id:
                        payload = {
                            "status": "FAILED",
                            "error_message": str(e)
                        }
                        try:
                            async with http_session.patch(f"{API_BASE_URL}/tasks/{task.task_id}", json=payload) as response:
                                if response.status != 200:
                                    print(f"Failed to mark task failed in API: {response.status}")
                        except Exception as e_api:
                            print(f"Error marking task failed in API: {str(e_api)}")
                            
                    if task.msg:
                        try:
                            await task.msg.edit(error_msg)
                        except Exception as edit_err:
                            print(f"Failed to edit message to error: {str(edit_err)}")
                    
        except Exception as e:
            print(f"\n❌ Error in download worker: {str(e)}")
            
        finally:
            active_downloads.pop(local_id, None)
            download_queue.task_done()
            # Small delay to prevent rate limiting
            await asyncio.sleep(1)

def guess_filename(filename):
    """Guess file information using guessit."""
    try:
        import guessit
        info = guessit.guessit(filename)

        extension = info.get('container') if info.get('container') is not None else filename.split(".")[-1]

        episode = f"E{info.get('episode')}" if info.get('episode') is not None else ""

        season = ''

        if info.get('episode') is not None:
            season = f"S{info.get('season')}" if info.get('season') is not None else 'S0'

        return f"{info.get('title')} - {season}{episode}.{extension}"
    except ImportError:
        print("guessit not installed")
        return None

def clean_string(s):
    """Clean string for filename usage."""
    return s.strip().replace('/', '_').replace('\\', '_').replace('\n', '_').replace('\r', '_').replace(':', '_')

async def main():
    async with aiohttp.ClientSession() as http_session:
        # Start download workers
        num_workers = 2  # You can increase this for parallel downloads
        workers = [asyncio.create_task(download_worker(http_session)) for _ in range(num_workers)]
        
        # Handler para mensajes nuevos
        @client.on(events.NewMessage)
        async def handler(event):
            if event.sender_id not in list(map(int, ALLOWED_USERS)):
                await event.reply("No tienes permisos para usar este bot.")
                return
        
            message_text = (event.message.text or "").strip().lower()
            
            # Handle help command
            if message_text in ['/help', '/ayuda', '/start']:
                await show_help(event)
                return
            
            # Handle list command
            if message_text.lower().startswith(('/listar', '/list', '/l')):
                parts = message_text.split(maxsplit=1)
                if len(parts) > 1:
                    await list_files_by_type(event, parts[1].strip())
                else:
                    # Show help for list command
                    await event.reply(
                        "📋 **Lista de archivos disponibles**\n\n"
                        "Usa uno de estos comandos:\n"
                        "`/listar video` - Muestra archivos de video\n"
                        "`/listar music` - Muestra archivos de música\n"
                        "`/listar document` - Muestra documentos\n\n"
                        "*Sugerencia:* Usa `/l` en lugar de `/listar` para ahorrar tiempo.\n"
                        "Ejemplo: `/l video`"
                    )
                return
    
            print("📥 Nuevo mensaje en Geoffrey:", message_text)
    
            if isinstance(event.message.media, MessageMediaDocument):
                attr_filename = ''
                filename = ''
                
                for attr in event.message.media.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        attr_filename = attr.file_name
                        print(f'Original filename: {attr_filename}')
                        break
    
                # Check file type
                file_type = get_file_type(event.message.media.document.mime_type)
                
                if not file_type:
                    await event.reply(f"❌ Tipo de archivo no soportado {file_type}. Solo se permiten videos, audios y documentos.")
                    return
    
                filename = attr_filename
    
                if file_type == "Video":
                    # Replace name whether the file is a Video
                    filename = f"{message_text} - {attr_filename}" if message_text else attr_filename
                    filename = guess_filename(clean_string(filename))
                
                # Clean filename    
                filename = clean_string(filename)
    
                print("Final Filename", filename)
    
                # Create download directory if it doesn't exist
                download_dir = f'{DOWNLOAD_PATH}/{file_type}'
                os.makedirs(download_dir, exist_ok=True)
                download_path = f'{download_dir}/{filename}'
    
                # Check if file already exists
                if check_filename_exists(download_path):
                    await event.reply(f"❌ El archivo {filename} ya existe en el servidor. Por favor, cambia el nombre del archivo e intenta de nuevo.")
                    return
    
                # Create download task and add to queue
                task = DownloadTask(
                    message=event.message,
                    filename=filename,
                    download_path=download_path,
                    event=event
                )
                
                await download_queue.put(task)
                queue_size = download_queue.qsize()
                
                # Notify user that the download is queued and store the message
                task.queue_msg = await event.reply(
                    f"📥 **Archivo agregado a la cola**\n"
                    f"📄 `{filename}`\n"
                    f"🔄 Posición en cola: {queue_size}"
                )
    
        # Mantener el cliente corriendo
        await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())