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
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

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

def make_progress_bar(progress, total=100, length=20):
    percent = int(progress / total * 100)
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {percent}%"

async def download_progress(msg_reply, downloading_txt, received_bytes, total):
    # Initialize static variables if they don't exist
    if not hasattr(download_progress, 'last_update'):
        download_progress.last_update = {}
    if not hasattr(download_progress, 'last_percent'):
        download_progress.last_percent = {}
    
    # Use message ID as key to track progress per download
    msg_id = id(msg_reply)
    current_time = time.time()
    current_percent = int((received_bytes / total) * 100) if total > 0 else 0
    
    # Only update if:
    # 1. This is the first update for this message, or
    # 2. At least 2 seconds have passed since last update, or
    # 3. The progress has increased by at least 2%, or
    # 4. The download is complete
    last_update = download_progress.last_update.get(msg_id, 0)
    last_percent = download_progress.last_percent.get(msg_id, -1)
    
    should_update = (
        last_percent == -1 or  # First update
        current_time - last_update >= 2.0 or  # At least 2 seconds since last update
        current_percent >= last_percent + 2 or  # At least 2% progress
        received_bytes >= total  # Download complete
    )
    
    if should_update:
        download_progress.last_update[msg_id] = current_time
        download_progress.last_percent[msg_id] = current_percent
        
        # Generate progress bar
        bar = make_progress_bar(received_bytes, total)
        speed = ""
        
        # Add speed calculation if we have previous data
        if hasattr(download_progress, 'last_bytes') and hasattr(download_progress, 'last_time'):
            time_diff = current_time - download_progress.last_time
            bytes_diff = received_bytes - download_progress.last_bytes
            if time_diff > 0 and bytes_diff > 0:
                speed_mb = (bytes_diff / (1024 * 1024)) / time_diff
                speed = f"\n⚡ {speed_mb:.1f} MB/s"
        
        try:
            await msg_reply.edit(
                f"{downloading_txt}\n\n"
                f"{bar}\n"
                f"📊 {current_percent}% • {received_bytes/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                f"{speed}"
            )
        except Exception as e:
            if "message not modified" not in str(e).lower() and "A wait of" not in str(e):
                print(f"Error updating progress: {str(e)}")
    
    # Update speed calculation data
    download_progress.last_bytes = received_bytes
    download_progress.last_time = current_time
    
    # Clean up progress tracking for completed downloads
    if received_bytes >= total and msg_id in download_progress.last_update:
        download_progress.last_update.pop(msg_id, None)
        download_progress.last_percent.pop(msg_id, None)
        

def get_file_type(filename):
    extension = filename.split('.')[-1].lower()
    video_extensions = ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv']
    audio_extensions = ['mp3', 'wav', 'aac', 'flac', 'ogg']
    document_extensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']

    if extension in video_extensions:
        return 'Video'
    elif extension in audio_extensions:
        return 'Music'
    elif extension in document_extensions:
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

async def download_worker():
    """Worker that processes download tasks from the queue."""
    while True:
        task = await download_queue.get()
        task_id = id(task)
        
        try:
            async with download_lock:
                if task_id in active_downloads:
                    return  # Skip if task is already being processed
                    
                active_downloads[task_id] = task
                
                # Create progress message
                queue_size = download_queue.qsize()
                downloading_txt = (
                    f"⬇️ **En cola: {queue_size}**\n"
                    f"**Descargando:** `{task.filename}`\n"
                    f"💾 Tamaño: {task.message.file.size/1024/1024:.1f}MB"
                )
                
                try:
                    task.msg = await task.event.reply(downloading_txt)
                    
                    # Download the file with progress callback
                    task.progress_callback = partial(
                        download_progress, 
                        task.msg, 
                        downloading_txt
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
                        print(task.queue_msg)
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
                    if task.msg:
                        await task.msg.edit(error_msg)
                        
                except Exception as e:
                    error_msg = (
                        f"❌ **Error al descargar**\n"
                        f"`{task.filename}`\n"
                        f"Error: {str(e)}"
                    )
                    print(f'\n❌ Error downloading {task.filename}: {str(e)}')
                    if task.msg:
                        await task.msg.edit(error_msg)
                    
        except Exception as e:
            print(f"\n❌ Error in download worker: {str(e)}")
            
        finally:
            active_downloads.pop(task_id, None)
            download_queue.task_done()
            # Small delay to prevent rate limiting
            await asyncio.sleep(1)

def guess_filename(filename):
    """Guess file information using guessit."""
    try:
        import guessit
        info = guessit.guessit(filename)

        return f"{info['title']} - S{info['season']}E{info['episode']}.{info['container']}"
    except ImportError:
        print("guessit not installed")
        return None

def clean_string(s):
    """Clean string for filename usage."""
    return s.strip().replace('/', '_').replace('\\', '_').replace('\n', '_').replace('\r', '_').replace(':', '_')

async def main():
    # Start download workers
    num_workers = 2  # You can increase this for parallel downloads
    workers = [asyncio.create_task(download_worker()) for _ in range(num_workers)]
    
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
            file_type = get_file_type(attr_filename)
            
            if not file_type:
                await event.reply("❌ Tipo de archivo no soportado. Solo se permiten videos, audios y documentos.")
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