import requests
import re
import html
import base64
import json
import subprocess
import os
import time
from urllib.parse import unquote


# ============================================================
# НАСТРОЙКИ
# ============================================================

YTDLP = r"C:\Users\Константин\OneDrive\Desktop\Youtube Music Downloader\yt-dlp.exe"

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive"
}

TIMEOUT = 20

MIN_FILE_SIZE = 10 * 1024

MP3PARTY_RETRIES = 3

DOWNLOAD_LRC = False

LRCLIB_DELAY = 1.0

COVER_SIZE = 720


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def status(message):
    print()
    print(message)


def normalize(text):

    text = html.unescape(str(text))

    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("_", " ")

    text = re.sub(
        r"\(MP3\.tm\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\(audiostart\.net\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"[,;|/\\]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip().lower()


def normalize_words(text):

    text = normalize(text)

    return set(
        word
        for word in text.split()
        if word
    )


def clean_filename(text):

    text = unquote(text)

    text = re.sub(
        r"\(MP3\.tm\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.replace("_", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def safe_filename(text):

    text = re.sub(
        r'[<>:"/\\|?*]',
        "",
        str(text)
    )

    return text.strip()


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    try:
        seconds = int(round(float(seconds)))
    except Exception:
        return "??:??"

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


# ============================================================
# YOUTUBE MUSIC
# ============================================================

def get_youtube_music_info(url):

    status("Получение информации из YouTube Music...")

    command = [
        YTDLP,
        "--dump-single-json",
        "--no-download",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

        if result.returncode != 0:

            print()
            print("Не удалось получить информацию о треке.")

            return None

        data = json.loads(result.stdout)

        artist = (
            data.get("artist")
            or data.get("uploader")
            or data.get("creator")
        )

        title = (
            data.get("track")
            or data.get("title")
        )

        album = (
            data.get("album")
            or ""
        )

        duration = data.get("duration")

        thumbnail = (
            data.get("thumbnail")
            or ""
        )

        if not artist or not title:

            print()
            print(
                "Не удалось определить "
                "исполнителя или название."
            )

            return None

        return {
            "artist": artist,
            "title": title,
            "album": album,
            "duration": duration,
            "thumbnail": thumbnail
        }

    except FileNotFoundError:

        print()
        print("ОШИБКА")
        print("yt-dlp.exe не найден.")
        print(YTDLP)

        return None

    except json.JSONDecodeError:

        print()
        print("ОШИБКА")
        print("yt-dlp не вернул корректные данные.")

        return None

    except subprocess.TimeoutExpired:

        print()
        print(
            "ОШИБКА: получение данных "
            "заняло слишком много времени."
        )

        return None

    except Exception as e:

        print()
        print("ОШИБКА:")
        print(e)

        return None


# ============================================================
# LRCLIB
# ============================================================

def search_lrclib(
    artist,
    title,
    album=None,
    duration=None
):

    status("Поиск синхронизированного текста...")

    if duration is None:

        print(
            "Недостаточно данных для точного поиска текста."
        )

        return None

    try:

        params = {
            "track_name": title,
            "artist_name": artist,
            "album_name": album or "",
            "duration": int(round(float(duration)))
        }

        response = requests.get(
            "https://lrclib.net/api/get",
            params=params,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Accept": "application/json"
            },
            timeout=TIMEOUT
        )

        if response.status_code != 200:

            print(
                "Синхронизированный текст не найден."
            )

            return None

        data = response.json()

        synced_lyrics = data.get(
            "syncedLyrics"
        )

        if not synced_lyrics:

            print(
                "Синхронизированный текст не найден."
            )

            return None

        return synced_lyrics.strip()

    except requests.RequestException:

        print(
            "Не удалось получить текст."
        )

        return None

    except Exception:

        print(
            "Не удалось обработать текст."
        )

        return None


def save_lrc(
    mp3_filepath,
    lyrics
):

    lrc_filepath = os.path.splitext(
        mp3_filepath
    )[0] + ".lrc"

    try:

        with open(
            lrc_filepath,
            "w",
            encoding="utf-8-sig",
            newline="\n"
        ) as file:

            file.write(
                lyrics
            )

        print(
            "LRC готов."
        )

        return True

    except Exception as e:

        print()
        print(
            "Не удалось сохранить LRC:",
            e
        )

        return False


def process_lrc(
    artist,
    title,
    album,
    duration,
    mp3_filepath
):

    lyrics = search_lrclib(
        artist,
        title,
        album,
        duration
    )

    if not lyrics:
        return False

    status("Сохранение LRC...")

    return save_lrc(
        mp3_filepath,
        lyrics
    )


# ============================================================
# ПРОВЕРКА JPEG
# ============================================================

def check_jpeg_file(filename):

    print()
    print("=" * 60)
    print("ПРОВЕРКА JPEG")
    print("=" * 60)

    print()
    print("Файл:")
    print(filename)

    if not os.path.exists(filename):

        print()
        print("ОШИБКА: файл не существует.")

        return None

    size = os.path.getsize(filename)

    print()
    print(
        "Размер:",
        size,
        "байт"
    )

    try:

        with open(
            filename,
            "rb"
        ) as file:

            first_bytes = file.read(32)

        print()
        print("Первые байты:")
        print(first_bytes)

        print()
        print("HEX:")
        print(
            first_bytes.hex(" ")
        )

        # ----------------------------------------------------
        # JPEG signature
        # ----------------------------------------------------

        if (
            len(first_bytes) >= 3
            and
            first_bytes[0:3] == b"\xff\xd8\xff"
        ):

            print()
            print("JPEG-сигнатура: OK")

        else:

            print()
            print(
                "ОШИБКА: JPEG-сигнатура не обнаружена."
            )

            return None

        # ----------------------------------------------------
        # FFPROBE
        # ----------------------------------------------------

        command = [
            FFPROBE,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            filename
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        print()
        print("FFPROBE OUTPUT:")

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print()
            print("FFPROBE STDERR:")
            print(result.stderr)

        if result.returncode != 0:

            print()
            print(
                "ОШИБКА: ffprobe не смог обработать JPEG."
            )

            return None

        data = json.loads(
            result.stdout
        )

        streams = data.get(
            "streams",
            []
        )

        if not streams:

            print()
            print(
                "ОШИБКА: ffprobe не обнаружил поток."
            )

            return None

        stream = streams[0]

        codec = stream.get(
            "codec_name"
        )

        width = stream.get(
            "width"
        )

        height = stream.get(
            "height"
        )

        print()
        print(
            "Распознанный кодек:",
            codec
        )

        print(
            "Описание:",
            stream.get("codec_long_name")
        )

        print(
            "Размер:",
            width,
            "x",
            height
        )

        # ----------------------------------------------------
        # ВАЖНО:
        # mjpeg здесь НОРМАЛЬНО.
        # Это JPEG-картинка.
        # ----------------------------------------------------

        if codec != "mjpeg":

            print()
            print(
                "ОШИБКА: ffprobe не распознал JPEG как MJPEG."
            )

            return None

        if not width or not height:

            print()
            print(
                "ОШИБКА: не удалось определить размер."
            )

            return None

        print()
        print(
            "JPEG-файл корректен."
        )

        print(
            "Исходное соотношение:",
            f"{width}:{height}"
        )

        return {
            "codec": codec,
            "width": width,
            "height": height
        }

    except Exception as e:

        print()
        print(
            "ОШИБКА проверки JPEG:"
        )

        print(e)

        return None


# ============================================================
# ПРОВЕРКА ВСТРОЕННОЙ ОБЛОЖКИ
# ============================================================

def verify_embedded_cover(mp3_filepath):

    print()
    print("=" * 60)
    print("ПРОВЕРКА ВСТРОЕННОЙ ОБЛОЖКИ")
    print("=" * 60)

    print()
    print("Файл:")
    print(mp3_filepath)

    command = [
        FFPROBE,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        mp3_filepath
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        print()
        print("FFPROBE MP3 OUTPUT:")

        if result.stdout:
            print(result.stdout)

        if result.stderr:

            print()
            print("FFPROBE STDERR:")
            print(result.stderr)

        if result.returncode != 0:

            print()
            print(
                "ОШИБКА: ffprobe не смог проверить MP3."
            )

            return False

        data = json.loads(
            result.stdout
        )

        streams = data.get(
            "streams",
            []
        )

        audio_found = False
        cover_found = False

        print()
        print(
            "Найдено потоков:",
            len(streams)
        )

        for stream in streams:

            index = stream.get(
                "index"
            )

            codec = stream.get(
                "codec_name"
            )

            codec_type = stream.get(
                "codec_type"
            )

            width = stream.get(
                "width"
            )

            height = stream.get(
                "height"
            )

            disposition = stream.get(
                "disposition",
                {}
            )

            print()
            print(
                f"Поток № {index}"
            )

            print(
                "Codec:",
                codec
            )

            print(
                "Тип:",
                codec_type
            )

            print(
                "Размер:",
                width,
                "x",
                height
            )

            print(
                "Disposition:",
                disposition
            )

            # ------------------------------------------------
            # Аудио
            # ------------------------------------------------

            if codec_type == "audio":

                audio_found = True

            # ------------------------------------------------
            # Обложка
            # ------------------------------------------------

            if (
                codec_type == "video"
                and
                codec == "mjpeg"
                and
                width == COVER_SIZE
                and
                height == COVER_SIZE
            ):

                attached_pic = disposition.get(
                    "attached_pic",
                    0
                )

                if attached_pic == 1:

                    cover_found = True

        print()
        print("=" * 60)

        if audio_found:

            print(
                "Аудиопоток: OK"
            )

        else:

            print(
                "Аудиопоток: НЕ НАЙДЕН"
            )

        if cover_found:

            print(
                "Встроенная обложка: OK"
            )

        else:

            print(
                "Встроенная обложка: НЕ НАЙДЕНА"
            )

        print("=" * 60)

        return (
            audio_found
            and
            cover_found
        )

    except Exception as e:

        print()
        print(
            "ОШИБКА проверки встроенной обложки:"
        )

        print(e)

        return False


# ============================================================
# ОБЛОЖКА YOUTUBE MUSIC
# ============================================================

def download_cover(
    thumbnail_url,
    mp3_filepath
):

    print()
    print("=" * 60)
    print("ОБРАБОТКА ОБЛОЖКИ")
    print("=" * 60)

    print()
    print("URL ОБЛОЖКИ:")
    print(thumbnail_url)

    if not thumbnail_url:

        print()
        print(
            "ОШИБКА: URL обложки отсутствует."
        )

        return False

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    temp_original = os.path.join(
        script_folder,
        "_cover_original.jpg"
    )

    temp_cover = os.path.join(
        script_folder,
        "_cover_720.jpg"
    )

    temp_mp3 = (
        mp3_filepath
        +
        ".cover.tmp.mp3"
    )

    try:

        # ====================================================
        # ШАГ 1
        # ====================================================

        print()
        print("=" * 60)
        print("ШАГ 1. СКАЧИВАНИЕ ИСХОДНОЙ ОБЛОЖКИ")
        print("=" * 60)

        print()
        print("GET:")
        print(thumbnail_url)

        response = requests.get(
            thumbnail_url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        print()
        print(
            "HTTP-код:",
            response.status_code
        )

        print(
            "Content-Type:",
            response.headers.get(
                "Content-Type"
            )
        )

        print(
            "Content-Length:",
            response.headers.get(
                "Content-Length"
            )
        )

        print(
            "Фактический размер:",
            len(response.content),
            "байт"
        )

        print(
            "Финальный URL:",
            response.url
        )

        if response.status_code != 200:

            print()
            print(
                "ОШИБКА: HTTP-код не 200."
            )

            return False

        if not response.content:

            print()
            print(
                "ОШИБКА: сервер вернул пустой файл."
            )

            return False

        print()
        print("Первые 32 байта:")
        print(
            response.content[:32]
        )

        print()
        print("Первые байты HEX:")
        print(
            response.content[:32].hex(" ")
        )

        with open(
            temp_original,
            "wb"
        ) as file:

            file.write(
                response.content
            )

        print()
        print(
            "Исходная обложка сохранена:"
        )

        print(
            temp_original
        )

        # ====================================================
        # ПРОВЕРКА ИСХОДНОЙ ОБЛОЖКИ
        # ====================================================

        print()
        print("=" * 60)
        print("ПРОВЕРКА: ИСХОДНАЯ ОБЛОЖКА")
        print("=" * 60)

        original_info = check_jpeg_file(
            temp_original
        )

        if not original_info:

            print()
            print(
                "ОШИБКА: исходная обложка "
                "не прошла проверку."
            )

            return False

        # ====================================================
        # ШАГ 2
        # ====================================================

        print()
        print("=" * 60)
        print("ШАГ 2. ПОДГОТОВКА 720x720")
        print("=" * 60)

        crop_filter = (
            "crop="
            "min(iw\\,ih):"
            "min(iw\\,ih):"
            "(iw-min(iw\\,ih))/2:"
            "(ih-min(iw\\,ih))/2,"
            f"scale={COVER_SIZE}:{COVER_SIZE}"
        )

        print()
        print("FFMPEG FILTER:")
        print(crop_filter)

        crop_command = [
            FFMPEG,
            "-y",
            "-i",
            temp_original,
            "-vf",
            crop_filter,
            "-frames:v",
            "1",
            "-c:v",
            "mjpeg",
            "-q:v",
            "2",
            temp_cover
        ]

        print()
        print("FFMPEG COMMAND:")

        print(
            " ".join(
                f'"{x}"' if " " in x else x
                for x in crop_command
            )
        )

        print()
        print("Запуск FFmpeg...")

        result = subprocess.run(
            crop_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

        print()
        print(
            "FFMPEG RETURN CODE:",
            result.returncode
        )

        print()
        print("FFMPEG STDOUT:")

        print(
            result.stdout
            if result.stdout
            else "(пусто)"
        )

        print()
        print("FFMPEG STDERR:")

        print(
            result.stderr
            if result.stderr
            else "(пусто)"
        )

        if result.returncode != 0:

            print()
            print(
                "ОШИБКА: FFmpeg не смог "
                "подготовить квадратную обложку."
            )

            return False

        if not os.path.exists(temp_cover):

            print()
            print(
                "ОШИБКА: файл 720x720 не создан."
            )

            return False

        # ====================================================
        # ПРОВЕРКА 720x720
        # ====================================================

        print()
        print("=" * 60)
        print("ПРОВЕРКА: ПОДГОТОВЛЕННАЯ ОБЛОЖКА 720x720")
        print("=" * 60)

        cover_info = check_jpeg_file(
            temp_cover
        )

        if not cover_info:

            print()
            print(
                "ОШИБКА: подготовленная обложка "
                "не прошла проверку."
            )

            return False

        if (
            cover_info["width"] != COVER_SIZE
            or
            cover_info["height"] != COVER_SIZE
        ):

            print()
            print(
                "ОШИБКА: после обработки "
                "обложка не 720x720."
            )

            return False

        print()
        print(
            "Размер 720x720 подтверждён."
        )

        # ====================================================
        # ШАГ 3
        # ====================================================

        print()
        print("=" * 60)
        print("ШАГ 3. ВСТРАИВАНИЕ ОБЛОЖКИ В MP3")
        print("=" * 60)

        print()
        print("Исходный MP3:")
        print(mp3_filepath)

        print()
        print(
            "Размер исходного MP3:",
            os.path.getsize(mp3_filepath),
            "байт"
        )

        print()
        print("Временный MP3:")
        print(temp_mp3)

        # ----------------------------------------------------
        # ВАЖНО:
        #
        # JPEG -> MJPEG внутри MP3 — это нормально.
        # attached_pic = 1 сообщает MP3/ID3, что это
        # прикреплённая обложка, а не обычное видео.
        # ----------------------------------------------------

        embed_command = [
            FFMPEG,
            "-y",

            "-i",
            mp3_filepath,

            "-i",
            temp_cover,

            "-map",
            "0:a:0",

            "-map",
            "1:v:0",

            "-map_metadata",
            "0",

            "-c:a",
            "copy",

            "-c:v",
            "mjpeg",

            "-disposition:v:0",
            "attached_pic",

            "-id3v2_version",
            "3",

            "-metadata:s:v:0",
            "title=Album cover",

            "-metadata:s:v:0",
            "comment=Cover (front)",

            temp_mp3
        ]

        print()
        print("FFMPEG COMMAND:")

        print(
            " ".join(
                f'"{x}"' if " " in x else x
                for x in embed_command
            )
        )

        print()
        print(
            "Запуск FFmpeg для встраивания..."
        )

        result = subprocess.run(
            embed_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

        print()
        print(
            "FFMPEG RETURN CODE:",
            result.returncode
        )

        print()
        print("FFMPEG STDOUT:")

        print(
            result.stdout
            if result.stdout
            else "(пусто)"
        )

        print()
        print("FFMPEG STDERR:")

        print(
            result.stderr
            if result.stderr
            else "(пусто)"
        )

        if result.returncode != 0:

            print()
            print(
                "ОШИБКА: FFmpeg не смог "
                "встроить обложку."
            )

            return False

        if not os.path.exists(temp_mp3):

            print()
            print(
                "ОШИБКА: временный MP3 не создан."
            )

            return False

        print()
        print(
            "Размер временного MP3:",
            os.path.getsize(temp_mp3),
            "байт"
        )

        # ====================================================
        # ПРОВЕРКА ВРЕМЕННОГО MP3
        # ====================================================

        print()
        print(
            "Проверяем временный MP3 "
            "до замены исходного..."
        )

        verified = verify_embedded_cover(
            temp_mp3
        )

        if not verified:

            print()
            print(
                "ОШИБКА: встроенная обложка "
                "не прошла проверку."
            )

            print()
            print(
                "Исходный MP3 НЕ будет заменён."
            )

            return False

        # ====================================================
        # ЗАМЕНА
        # ====================================================

        print()
        print(
            "Проверка пройдена."
        )

        print()
        print(
            "Замена исходного MP3..."
        )

        os.replace(
            temp_mp3,
            mp3_filepath
        )

        print()
        print(
            "Исходный MP3 заменён."
        )

        # ====================================================
        # ФИНАЛЬНАЯ ПРОВЕРКА
        # ====================================================

        final_verified = verify_embedded_cover(
            mp3_filepath
        )

        if not final_verified:

            print()
            print(
                "ВНИМАНИЕ: после замены "
                "финальная проверка не пройдена."
            )

            return False

        print()
        print("=" * 60)
        print("ОБЛОЖКА УСПЕШНО ВСТРОЕНА")
        print("=" * 60)

        print()
        print(
            "Формат изображения: JPEG"
        )

        print(
            "FFprobe codec: mjpeg"
        )

        print(
            "Размер:",
            f"{COVER_SIZE}x{COVER_SIZE}"
        )

        print(
            "Обложка: attached_pic"
        )

        return True

    except Exception as e:

        print()
        print("=" * 60)
        print("КРИТИЧЕСКАЯ ОШИБКА ОБЛОЖКИ")
        print("=" * 60)

        print()
        print(
            type(e).__name__ + ":",
            e
        )

        return False

    finally:

        for temp_file in (
            temp_original,
            temp_cover,
            temp_mp3
        ):

            if os.path.exists(temp_file):

                try:
                    os.remove(temp_file)
                except Exception:
                    pass


# ============================================================
# ПОЛУЧЕНИЕ ПЛЕЙЛИСТА
# ============================================================

def get_playlist_tracks(url):

    status("Получение списка треков плейлиста...")

    command = [
        YTDLP,
        "--flat-playlist",
        "--dump-single-json",
        "--quiet",
        "--no-warnings",
        url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )

        if result.returncode != 0:

            print()
            print("Не удалось получить плейлист.")

            return None

        data = json.loads(result.stdout)

        entries = data.get("entries") or []

        tracks = []

        for entry in entries:

            if not entry:
                continue

            track_url = (
                entry.get("webpage_url")
                or entry.get("original_url")
                or entry.get("url")
            )

            if not track_url:
                continue

            if not track_url.startswith("http"):

                track_url = (
                    "https://music.youtube.com/watch?v="
                    + track_url
                )

            tracks.append(track_url)

        if not tracks:
            return None

        playlist_title = (
            data.get("title")
            or "YouTube Music"
        )

        return {
            "title": playlist_title,
            "tracks": tracks
        }

    except Exception as e:

        print()
        print("Ошибка получения плейлиста:")
        print(e)

        return None


# ============================================================
# FFPROBE — ПРОВЕРКА ФАЙЛА
# ============================================================

def validate_audio_file(filename):

    if not os.path.exists(filename):
        return False

    try:

        size = os.path.getsize(filename)

        if size < MIN_FILE_SIZE:
            return False

        command = [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration",
            "-of",
            "json",
            filename
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)

        format_data = data.get("format", {})

        duration = format_data.get("duration")

        if not duration:
            return False

        try:

            if float(duration) <= 0:
                return False

        except Exception:

            return False

        return True

    except Exception:

        return False


# ============================================================
# ПОЛУЧЕНИЕ ДЛИТЕЛЬНОСТИ MP3 ПО URL
# ============================================================

def get_duration(url):

    try:

        command = [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            url
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if result.returncode != 0:
            return None

        value = result.stdout.strip()

        if not value:
            return None

        return float(value)

    except Exception:

        return None


# ============================================================
# СКАЧИВАНИЕ ФАЙЛА
# ============================================================

def download_file(
    url,
    filename,
    referer=None,
    retries=1
):

    status("Скачивание аудиофайла...")

    temp_filename = filename + ".tmp"

    for attempt in range(
        1,
        retries + 1
    ):

        try:

            if os.path.exists(temp_filename):

                try:
                    os.remove(temp_filename)
                except Exception:
                    pass

            headers = dict(HEADERS)

            headers["Accept"] = (
                "audio/mpeg,"
                "audio/*;"
                "q=0.9,"
                "*/*;"
                "q=0.8"
            )

            headers["Range"] = "bytes=0-"

            if referer:
                headers["Referer"] = referer

            with requests.Session() as session:

                r = session.get(
                    url,
                    headers=headers,
                    timeout=60,
                    stream=True,
                    allow_redirects=True
                )

                if r.status_code not in (
                    200,
                    206
                ):

                    if attempt < retries:

                        status(
                            "Повторная попытка скачивания..."
                        )

                        time.sleep(1)

                        continue

                    return False

                total = 0

                with open(
                    temp_filename,
                    "wb"
                ) as f:

                    for chunk in r.iter_content(
                        chunk_size=262144
                    ):

                        if chunk:

                            f.write(chunk)

                            total += len(chunk)

                print()
                print(
                    "Получено:",
                    round(
                        total / 1024 / 1024,
                        2
                    ),
                    "МБ"
                )

                if total < MIN_FILE_SIZE:

                    if attempt < retries:

                        status(
                            "Получен некорректный файл. "
                            "Повторная попытка..."
                        )

                        time.sleep(1)

                        continue

                    return False

                status("Проверка аудиофайла...")

                if not validate_audio_file(
                    temp_filename
                ):

                    if attempt < retries:

                        status(
                            "Файл не прошёл проверку. "
                            "Повторная попытка..."
                        )

                        time.sleep(1)

                        continue

                    return False

                if os.path.exists(filename):

                    try:
                        os.remove(filename)
                    except Exception:
                        pass

                os.replace(
                    temp_filename,
                    filename
                )

                print()
                print("Аудиофайл готов.")

                return True

        except Exception as e:

            if attempt < retries:

                status(
                    "Ошибка соединения. "
                    "Повторная попытка..."
                )

                time.sleep(1)

                continue

            print()
            print(
                "Ошибка скачивания:",
                e
            )

            return False

    return False


# ============================================================
# ПОИСК АУДИО — MP3PARTY
# ============================================================

def search_mp3party(
    artist,
    title
):

    status("Поиск подходящего аудиофайла...")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://mp3party.net/search",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            return None

        text = html.unescape(r.text)

        pattern = re.compile(
            r'<div class="track__user-panel"'
            r'[^>]*'
            r'data-js-artist-name="([^"]+)"'
            r'[^>]*'
            r'data-js-id="(\d+)"'
            r'[^>]*'
            r'data-js-song-title="([^"]+)"'
            r'[^>]*'
            r'data-js-url="([^"]+)"',
            re.I
        )

        results = pattern.findall(text)

        wanted_artist = normalize(artist)
        wanted_title = normalize(title)

        for (
            found_artist,
            song_id,
            found_title,
            mp3_url
        ) in results:

            if (
                normalize(found_artist)
                ==
                wanted_artist
                and
                normalize(found_title)
                ==
                wanted_title
            ):

                url = (
                    "https://dl2.mp3party.net/download/"
                    + song_id
                )

                return {
                    "url": url,
                    "referer": "https://mp3party.net/"
                }

    except Exception:

        pass

    return None


# ============================================================
# MP3TM — ОЦЕНКА
# ============================================================

def score_mp3tm_candidate(
    filename,
    artist,
    title
):

    name = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    name_words = normalize_words(name)
    artist_words = normalize_words(artist)
    title_words = normalize_words(title)

    score = 0

    artist_matches = (
        artist_words
        &
        name_words
    )

    if artist_words:

        artist_ratio = (
            len(artist_matches)
            /
            len(artist_words)
        )

        if artist_ratio == 1:

            score += 300

        elif artist_ratio >= 0.5:

            score += 120

        else:

            return -10000

    title_matches = (
        title_words
        &
        name_words
    )

    if title_words:

        title_ratio = (
            len(title_matches)
            /
            len(title_words)
        )

        if title_ratio == 1:

            score += 300

        elif title_ratio >= 0.5:

            score += 120

        else:

            return -10000

    if wanted_artist in name:
        score += 200

    if wanted_title in name:
        score += 200

    exact_phrase = (
        wanted_artist
        + " - "
        + wanted_title
    )

    if exact_phrase in name:
        score += 500

    reverse_phrase = (
        wanted_title
        + " - "
        + wanted_artist
    )

    if reverse_phrase in name:
        score += 350

    expected = (
        wanted_artist
        + " "
        + wanted_title
    )

    if name == expected:
        score += 500

    requested_words = (
        artist_words
        |
        title_words
    )

    extra_words = (
        name_words
        -
        requested_words
    )

    score -= len(extra_words) * 20

    modifiers = [
        "nightcore",
        "remix",
        "slowed",
        "sped",
        "speed",
        "bass",
        "type",
        "beat",
        "edit",
        "extended",
        "instrumental",
        "cover",
        "live",
        "acoustic",
        "rework",
        "version",
        "bootleg",
        "club",
        "hardstyle",
        "phonk",
        "prod"
    ]

    requested_text = (
        wanted_artist
        + " "
        + wanted_title
    )

    for modifier in modifiers:

        if (
            modifier in name
            and
            modifier not in requested_text
        ):

            score -= 100

    return score


# ============================================================
# MP3TM — ПОИСК
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    status("Проверка дополнительных вариантов...")

    query = f"{artist} {title}"

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip("-").lower()

    url = (
        f"https://{slug}.mp3tm.net/"
    )

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            return None

        text = html.unescape(r.text)

        links = re.findall(
            r'https?://[^"\']+\.mp3(?:\?[^"\']*)?',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(links)
        )

        candidates = []

        for link in links:

            filename = clean_filename(
                link.split("/")[-1]
            )

            score = score_mp3tm_candidate(
                filename,
                artist,
                title
            )

            if score <= -1000:
                continue

            candidates.append({
                "url": link,
                "filename": filename,
                "score": score,
                "duration": None
            })

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        top_score = candidates[0]["score"]

        top_candidates = [
            c
            for c in candidates
            if c["score"] == top_score
        ]

        for candidate in top_candidates[:10]:

            candidate["duration"] = get_duration(
                candidate["url"]
            )

        if target_duration is not None:

            valid = [
                c
                for c in top_candidates
                if c["duration"] is not None
            ]

            if valid:

                valid.sort(
                    key=lambda c:
                    abs(
                        c["duration"]
                        -
                        target_duration
                    )
                )

                best = valid[0]

            else:

                best = top_candidates[0]

        else:

            best = top_candidates[0]

        return {
            "url": best["url"],
            "referer": url
        }

    except Exception:

        pass

    return None


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(
    artist,
    title
):

    status("Проверка ещё одного варианта...")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://audiostart.net/",
            params={"song": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            return None

        text = html.unescape(r.text)

        links = re.findall(
            r'href=["\']([^"\']*?/getmp3/[^"\']+)["\']',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(links)
        )

        wanted_artist = normalize(artist)
        wanted_title = normalize(title)

        for link in links:

            try:

                encoded = link.split(
                    "/getmp3/",
                    1
                )[1]

                decoded = base64.b64decode(
                    encoded
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                decoded = unquote(
                    decoded
                )

                decoded_normalized = normalize(
                    decoded
                )

                if (
                    wanted_artist
                    in
                    decoded_normalized
                    and
                    wanted_title
                    in
                    decoded_normalized
                ):

                    if link.startswith("//"):

                        link = (
                            "https:"
                            +
                            link
                        )

                    return {
                        "url": link,
                        "referer": "https://audiostart.net/"
                    }

            except Exception:

                continue

    except Exception:

        pass

    return None


# ============================================================
# ПОИСК И СКАЧИВАНИЕ ТРЕКА
# ============================================================

def find_and_download_track(
    artist,
    title,
    album,
    duration,
    output_folder
):

    print()
    print("=" * 60)

    print(
        "ТРЕК:",
        artist,
        "—",
        title
    )

    print(
        "Длительность:",
        format_duration(duration)
    )

    print("=" * 60)

    filename = (
        f"{safe_filename(artist)} - "
        f"{safe_filename(title)}.mp3"
    )

    filepath = os.path.join(
        output_folder,
        filename
    )

    result = search_mp3party(
        artist,
        title
    )

    if result:

        success = download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=MP3PARTY_RETRIES
        )

        if success:
            return filepath

    result = search_mp3tm(
        artist,
        title,
        duration
    )

    if result:

        success = download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=2
        )

        if success:
            return filepath

    result = search_audiostart(
        artist,
        title
    )

    if result:

        success = download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=2
        )

        if success:
            return filepath

    print()
    print(
        "Не удалось найти подходящий аудиофайл."
    )

    return None


# ============================================================
# ОПРЕДЕЛЕНИЕ ПЛЕЙЛИСТА
# ============================================================

def is_playlist_url(url):

    return (
        "list=" in url
        and
        (
            "youtube.com" in url
            or
            "music.youtube.com" in url
        )
    )


# ============================================================
# ОДИН ТРЕК
# ============================================================

def process_single_track(
    url,
    output_folder
):

    info = get_youtube_music_info(
        url
    )

    if not info:
        return False

    artist = info["artist"]
    title = info["title"]
    album = info["album"]
    duration = info["duration"]
    thumbnail = info["thumbnail"]

    print()
    print("=" * 50)
    print("ИНФОРМАЦИЯ О ТРЕКЕ")
    print("=" * 50)

    print()
    print(
        "Исполнитель:",
        artist
    )

    print(
        "Название:   ",
        title
    )

    if album:

        print(
            "Альбом:     ",
            album
        )

    print(
        "Длительность:",
        format_duration(duration)
    )

    filepath = find_and_download_track(
        artist,
        title,
        album,
        duration,
        output_folder
    )

    if not filepath:
        return False

    # ========================================================
    # ОБЛОЖКА
    # ========================================================

    cover_success = download_cover(
        thumbnail,
        filepath
    )

    if not cover_success:

        print()
        print(
            "ВНИМАНИЕ: трек сохранён, "
            "но обложка не была встроена."
        )

    # ========================================================
    # LRC
    # ========================================================

    if DOWNLOAD_LRC:

        time.sleep(
            LRCLIB_DELAY
        )

        process_lrc(
            artist,
            title,
            album,
            duration,
            filepath
        )

    return True


# ============================================================
# ПЛЕЙЛИСТ
# ============================================================

def process_playlist(url):

    playlist = get_playlist_tracks(
        url
    )

    if not playlist:

        print()
        print("=" * 60)
        print(
            "НЕ УДАЛОСЬ ПОЛУЧИТЬ ПЛЕЙЛИСТ"
        )
        print("=" * 60)

        return

    playlist_title = safe_filename(
        playlist["title"]
    )

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    output_folder = os.path.join(
        script_folder,
        playlist_title
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    tracks = playlist["tracks"]

    print()
    print("=" * 60)
    print("ПЛЕЙЛИСТ")
    print("=" * 60)

    print(
        "Название:",
        playlist["title"]
    )

    print(
        "Треков:",
        len(tracks)
    )

    print("=" * 60)

    downloaded = 0
    failed = 0

    for index, track_url in enumerate(
        tracks,
        1
    ):

        print()
        print()
        print(
            "#" * 60
        )

        print(
            f"ТРЕК {index}/{len(tracks)}"
        )

        print(
            "#" * 60
        )

        success = process_single_track(
            track_url,
            output_folder
        )

        if success:

            downloaded += 1

        else:

            failed += 1

    print()
    print()
    print(
        "=" * 60
    )

    print(
        "ПЛЕЙЛИСТ ЗАВЕРШЁН"
    )

    print(
        "=" * 60
    )

    print(
        "Всего треков:",
        len(tracks)
    )

    print(
        "Скачано:",
        downloaded
    )

    print(
        "Не скачано:",
        failed
    )

    print(
        "Папка:",
        output_folder
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global DOWNLOAD_LRC

    print("=" * 60)
    print("YTMUSIC DOWNLOADER")
    print("=" * 60)

    print()
    print(
        "Скачивать текст песни в формате LRC?"
    )

    print()
    print("1 — Да")
    print("2 — Нет")
    print()

    while True:

        choice = input(
            "Ваш выбор [1/2]: "
        ).strip()

        if choice == "1":

            DOWNLOAD_LRC = True
            break

        if choice == "2":

            DOWNLOAD_LRC = False
            break

        print()
        print(
            "Введите 1 или 2."
        )

    print()

    url = input(
        "Ссылка на трек или плейлист YouTube Music: "
    ).strip()

    if not url:

        print()
        print(
            "Ссылка не указана."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    if is_playlist_url(url):

        process_playlist(
            url
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    tracks_folder = os.path.join(
        script_folder,
        "tracks"
    )

    os.makedirs(
        tracks_folder,
        exist_ok=True
    )

    success = process_single_track(
        url,
        tracks_folder
    )

    print()

    if success:

        print("=" * 60)
        print(
            "ТРЕК УСПЕШНО СКАЧАН"
        )
        print("=" * 60)

        print()
        print(
            "Папка:",
            tracks_folder
        )

    else:

        print("=" * 60)
        print(
            "ТРЕК НЕ СКАЧАН"
        )
        print("=" * 60)

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
