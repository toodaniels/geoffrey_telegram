import os
import re
import shutil
import logging
from dotenv import load_dotenv

load_dotenv()
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "./downloads")
SERIES_BASE = os.getenv("JELLYFIN_SERIES_PATH", "/mnt/avivo/Series")
MOVIES_BASE = os.getenv("JELLYFIN_MOVIES_PATH", "/mnt/avivo/Movies")

logging.basicConfig(level=logging.INFO)


def get_active_downloads():
    """Obtiene nombres de archivos en descarga activa desde los logs del bot."""
    log_stream = os.popen("podman logs geoffrey-bot | tail -n 100").read()
    pattern = r"Original filename: (.*?)\n"
    return re.findall(pattern, log_stream)


def clean_series_name(name):
    """
    Limpia el nombre de serie extrayendo solo la parte significativa.
    Elimina números sueltos al inicio, sufijos como 'capítulo'/'episodio',
    y caracteres Unicode/emojis de Telegram.
    """
    name = name.strip().rstrip(".-_ ")
    # Eliminar números iniciales tipo "34 blue lock" → "blue lock"
    name = re.sub(r"^\d+\s+", "", name)
    # Cortar en palabras clave: capítulo, episodio, temporada, y todo lo que sigue
    name = re.split(
        r"\s+(?:capítulo|episodio|temporada|ep)\b",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    name = name.strip().rstrip(".-_ ")
    # Eliminar caracteres no imprimibles y emojis (dejar ASCII + acentos comunes)
    name = re.sub(r"[^\x20-\x7E\xC0-\xFF\u0100-\u024F\s]", "", name)
    # Colapsar espacios múltiples
    name = re.sub(r"\s+", " ", name).strip()
    # Capitalizar tipo título
    name = name.title()
    return name


def parse_episode_info(filename):
    """
    Extrae nombre de serie, temporada y episodio desde el filename.

    Retorna (series_name, season, episode, extension) o None si no se pudo identificar.
    """
    root, ext = os.path.splitext(filename)
    if ext.lower() not in (".mp4", ".mkv", ".avi", ".mov"):
        return None

    # Patrón 1: "Nombre - S1E10.basura" o "Nombre - s01e10.basura"
    m = re.search(r"(.+?)\s*-\s*[Ss](\d+)[Ee](\d+)", root)
    if m:
        series = clean_series_name(m.group(1))
        if series:
            return series, int(m.group(2)), int(m.group(3)), ext

    # Patrón 2: "Nombre - capítulo X.basura" o "Nombre - episodio X.basura"
    m = re.search(
        r"(.+?)\s*-\s*(?:capítulo|episodio|ep)\s*\.?\s*(\d+)",
        root,
        re.IGNORECASE,
    )
    if m:
        series = clean_series_name(m.group(1))
        if series:
            return series, 1, int(m.group(2)), ext

    # Patrón 3: "Nombre X - basura" (X es número de episodio)
    m = re.search(r"(.+?)\s+(\d+)\s*-", root)
    if m:
        series = clean_series_name(m.group(1))
        if series:
            return series, 1, int(m.group(2)), ext

    # Patrón 4: "Nombre 01×01 - basura" o "Nombre 1x01 - basura" (temporada×episodio)
    m = re.search(r"(.+?)\s+(\d+)[×xX](\d+)\s*-", root)
    if m:
        series = clean_series_name(m.group(1))
        if series:
            return series, int(m.group(2)), int(m.group(3)), ext

    return None


def organize_media(file_path):
    """
    Identifica si es serie o película y mueve a la carpeta correspondiente
    usando el nombre limpio con formato 'Serie - S#E#.ext'.
    """
    filename = os.path.basename(file_path)

    info = parse_episode_info(filename)

    if not info:
        logging.warning(
            "No se pudo identificar serie/película, moviendo a Movies: %s", filename
        )
        os.makedirs(MOVIES_BASE, exist_ok=True)
        shutil.move(file_path, os.path.join(MOVIES_BASE, filename))
        return

    series_name, season, episode, ext = info
    new_filename = f"{series_name} - S{season}E{episode}{ext}"
    target_dir = os.path.join(SERIES_BASE, series_name, f"Season {season}")

    os.makedirs(target_dir, exist_ok=True)
    shutil.move(file_path, os.path.join(target_dir, new_filename))
    logging.info("✓ %s → %s/%s", filename, target_dir, new_filename)


def main():
    active_downloads = get_active_downloads()
    video_path = os.path.join(DOWNLOAD_PATH, "Video")

    if not os.path.exists(video_path):
        return

    for filename in sorted(os.listdir(video_path)):
        if not filename.endswith((".mkv", ".mp4")):
            continue

        # Omitir si es un archivo en descarga activa
        if any(filename in active for active in active_downloads):
            print("⏳ Omitiendo %s: está en descarga activa.", filename)
            continue

        file_path = os.path.join(video_path, filename)
        organize_media(file_path)


if __name__ == "__main__":
    main()
