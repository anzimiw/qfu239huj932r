import requests
import re
import html
import base64
import json
import subprocess
import os
import time
import io
from urllib.parse import unquote


# ============================================================
# ПУТИ ПРОЕКТА
# ============================================================

ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_FOLDER = os.path.dirname(
    ENGINE_FOLDER
)

YTDLP = os.path.join(
    ENGINE_FOLDER,
    "yt-dlp.exe"
)

FFMPEG = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffmpeg.exe"
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)

TRACKS_FOLDER = os.path.join(
    PROJECT_FOLDER,
    "tracks"
)


# ============================================================
# БИБЛИОТЕКИ
# ============================================================

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB

    MUTAGEN_AVAILABLE = True

except ImportError:
    MUTAGEN_AVAILABLE = False


try:
    from PIL import Image

    PIL_AVAILABLE = True

except ImportError:
    PIL_AVAILABLE = False


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,*/*;q=0.8",

    "Accept-Language":
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",

    "Connection":
        "keep-alive"
}


YANDEX_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": HEADERS["Accept-Language"],
    "Referer": "https://music.yandex.ru/"
}


SOUNDCLOUD_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": HEADERS["Accept-Language"],
    "Referer": "https://soundcloud.com/"
}


# ============================================================
# НАСТРОЙКИ
# ============================================================

TIMEOUT = 20

MIN_FILE_SIZE = 10 * 1024

MP3PARTY_RETRIES = 3

DOWNLOAD_LRC = False

LRCLIB_DELAY = 1.0

DURATION_TOLERANCE = 3.0

SOUNDCLOUD_DURATION_TOLERANCE = 10.0

SOUNDCLOUD_SEARCH_TIMEOUT = 15

SOUNDCLOUD_DOWNLOAD_TIMEOUT = 90

SOUNDCLOUD_SEARCH_RESULTS = 15

SOUNDCLOUD_CLIENT_ID_TIMEOUT = 15


# ============================================================
# СЛУЖЕБНЫЕ ФУНКЦИИ
# ============================================================

def status(message):
    print()
    print(message)


def normalize(text):
    text = html.unescape(str(text))
    text = unquote(text)

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

    text = text.lower()

    text = re.sub(
        r"\bof\s+buda\b",
        "og buda",
        text
    )

    text = re.sub(
        r"\bfeaturing\b",
        "feat",
        text
    )

    text = re.sub(
        r"\bft\.?\b",
        "feat",
        text
    )

    text = re.sub(
        r"\bfeat\.?\b",
        " ",
        text
    )

    text = re.sub(
        r"[,;|/\\]+",
        " ",
        text
    )

    text = re.sub(
        r"[()[\]{}]",
        " ",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def normalize_words(text):
    return {
        word
        for word in normalize(text).split()
        if word
    }


def clean_search_query(text):
    text = re.sub(
        r"\(feat\.[^)]+\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\[feat\.[^\]]+\]",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\(ft\.[^)]+\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"[()[\]{}]",
        " ",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def clean_filename(text):
    text = unquote(text)

    text = re.sub(
        r"\(MP3\.tm\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.replace("_", " ")

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def safe_filename(text):
    return re.sub(
        r'[<>:"/\\|?*]',
        "",
        str(text)
    ).strip()


def format_duration(seconds):
    if seconds is None:
        return "??:??"

    try:
        seconds = int(
            round(float(seconds))
        )
    except Exception:
        return "??:??"

    return f"{seconds // 60}:{seconds % 60:02d}"


# ============================================================
# URL CHECKS
# ============================================================

def is_yandex_music_url(url):
    if not url:
        return False

    url = url.lower()

    return any(
        x in url
        for x in (
            "music.yandex.ru/",
            "music.yandex.com/",
            "music.yandex.kz/",
            "music.yandex.by/",
            "music.yandex.uz/"
        )
    )


def is_youtube_music_url(url):
    if not url:
        return False

    url = url.lower()

    return (
        "music.youtube.com/" in url
        or "youtube.com/" in url
        or "youtu.be/" in url
    )


# ============================================================
# YANDEX MUSIC
# ============================================================

def parse_yandex_url(url):
    if not is_yandex_music_url(url):
        return None

    track_match = re.search(
        r"/track/(\d+)",
        url,
        re.I
    )

    album_match = re.search(
        r"/album/(\d+)",
        url,
        re.I
    )

    if not track_match:
        return None

    return {
        "track_id": track_match.group(1),
        "album_id":
            album_match.group(1)
            if album_match
            else ""
    }


def get_yandex_music_info(url):

    status(
        "Получение информации из Яндекс Музыки..."
    )

    parsed = parse_yandex_url(url)

    if not parsed:
        print(
            "Не удалось определить ID трека Яндекс Музыки."
        )
        return None

    track_id = parsed["track_id"]
    album_id = parsed["album_id"]

    try:
        response = requests.get(
            f"https://api.music.yandex.net/tracks/{track_id}",
            headers=YANDEX_HEADERS,
            timeout=TIMEOUT
        )

    except requests.RequestException:
        print(
            "Не удалось получить данные Яндекс Музыки."
        )
        return None

    if response.status_code != 200:
        print(
            "Не удалось получить метаданные трека."
        )
        return None

    try:
        data = response.json()

    except Exception:
        print(
            "Не удалось обработать данные Яндекс Музыки."
        )
        return None

    result = data.get("result")

    if isinstance(result, dict):
        result = result.get(
            "track",
            result
        )

    elif isinstance(result, list):
        result = result[0] if result else None

    if not isinstance(result, dict):
        return None

    track = result

    artists = track.get("artists") or []

    artist = ", ".join(
        str(x.get("name"))
        for x in artists
        if isinstance(x, dict)
        and x.get("name")
    )

    title = track.get("title") or ""

    album = ""

    albums = track.get("albums")

    if (
        isinstance(albums, list)
        and albums
        and isinstance(albums[0], dict)
    ):
        album = albums[0].get("title") or ""

        album_id = str(
            albums[0].get("id")
            or album_id
        )

    duration = None

    if track.get("durationMs") is not None:
        try:
            duration = (
                float(track["durationMs"])
                / 1000
            )

        except Exception:
            pass

    cover_uri = (
        track.get("coverUri")
        or track.get("ogImage")
    )

    cover_url = None

    if cover_uri:
        cover_url = str(
            cover_uri
        ).replace(
            "%%",
            "720x720"
        )

        if cover_url.startswith("//"):
            cover_url = "https:" + cover_url

        elif not cover_url.startswith(
            ("http://", "https://")
        ):
            cover_url = "https://" + cover_url

    if (
        not artist
        or not title
        or duration is None
    ):
        print(
            "Не удалось определить данные трека."
        )
        return None

    print(
        f"Исполнитель: {artist}"
    )

    print(
        f"Название: {title}"
    )

    print(
        f"Альбом: {album or 'не определён'}"
    )

    print(
        f"Длительность: {format_duration(duration)}"
    )

    print(
        f"Обложка: "
        f"{'НАЙДЕНА' if cover_url else 'НЕ НАЙДЕНА'}"
    )

    return {
        "source": "yandex",
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration,
        "cover_url": cover_url,
        "track_id": track_id,
        "album_id": album_id
    }


# ============================================================
# SOUND / FILE MATCHING
# ============================================================

def candidate_text_score(
    filename,
    artist,
    title
):
    candidate = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    candidate_words = normalize_words(candidate)

    artist_words = normalize_words(
        wanted_artist
    )

    title_words = normalize_words(
        wanted_title
    )

    if not artist_words or not title_words:
        return -100000

    artist_ratio = (
        len(
            artist_words & candidate_words
        )
        / len(artist_words)
    )

    title_ratio = (
        len(
            title_words & candidate_words
        )
        / len(title_words)
    )

    if (
        artist_ratio < 0.4
        or title_ratio < 0.4
    ):
        return -100000

    score = 0

    score += (
        500
        if artist_ratio == 1
        else 300
        if artist_ratio >= .75
        else 100
    )

    score += (
        500
        if title_ratio == 1
        else 300
        if title_ratio >= .75
        else 100
    )

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    modifiers = {
        "nightcore",
        "remix",
        "slowed",
        "speed up",
        "sped up",
        "sped",
        "instrumental",
        "cover",
        "hardstyle",
        "phonk"
    }

    requested = normalize(
        artist + " " + title
    )

    for modifier in modifiers:
        if (
            modifier in candidate
            and modifier not in requested
        ):
            score -= 200

    return score


def is_duration_acceptable(
    candidate_duration,
    target_duration,
    tolerance=DURATION_TOLERANCE
):
    if (
        candidate_duration is None
        or target_duration is None
    ):
        return True

    return (
        abs(
            candidate_duration
            - target_duration
        )
        <= tolerance
    )


# ============================================================
# COVER + TAGS
# ============================================================

def embed_cover(
    mp3_filepath,
    cover_url,
    artist,
    title,
    album=""
):

    if not MUTAGEN_AVAILABLE:
        print(
            "Не удалось добавить теги: "
            "mutagen не установлен."
        )
        return

    if not cover_url:
        print(
            "Обложка для этого трека не найдена."
        )
        return

    if not PIL_AVAILABLE:
        print(
            "Не удалось обработать обложку: "
            "Pillow не установлен."
        )
        return

    status(
        "Добавление обложки и тегов..."
    )

    try:

        url_to_fetch = cover_url

        if "=w" in cover_url:
            url_to_fetch = re.sub(
                r'=w\d+-h\d+.*$',
                '=w720-h720-l90-rj',
                cover_url
            )

        response = requests.get(
            url_to_fetch,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            response = requests.get(
                cover_url,
                headers=HEADERS,
                timeout=15
            )

        if response.status_code != 200:
            print(
                "Не удалось получить обложку."
            )
            return

        img = Image.open(
            io.BytesIO(response.content)
        )

        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size

        min_dim = min(
            width,
            height
        )

        left = (
            width - min_dim
        ) // 2

        top = (
            height - min_dim
        ) // 2

        right = left + min_dim
        bottom = top + min_dim

        img = img.crop(
            (
                left,
                top,
                right,
                bottom
            )
        )

        resample_filter = getattr(
            Image,
            "Resampling",
            Image
        ).LANCZOS

        img = img.resize(
            (720, 720),
            resample_filter
        )

        output = io.BytesIO()

        img.save(
            output,
            format="JPEG",
            quality=95
        )

        tags = ID3()

        tags.add(
            TIT2(
                encoding=3,
                text=[str(title)]
            )
        )

        tags.add(
            TPE1(
                encoding=3,
                text=[str(artist)]
            )
        )

        if album:
            tags.add(
                TALB(
                    encoding=3,
                    text=[str(album)]
                )
            )

        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=output.getvalue()
            )
        )

        tags.save(
            mp3_filepath,
            v2_version=3
        )

        print(
            "Обложка (720x720) и теги добавлены."
        )

    except Exception as e:
        print(
            "Не удалось добавить обложку и теги:",
            e
        )


# ============================================================
# YOUTUBE MUSIC
# ============================================================

def get_youtube_music_info(url):

    status(
        "Получение информации из YouTube Music..."
    )

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
            print(
                "Не удалось получить информацию о треке."
            )
            return None

        data = json.loads(
            result.stdout
        )

        artist = (
            data.get("artist")
            or data.get("uploader")
            or data.get("creator")
        )

        title = (
            data.get("track")
            or data.get("title")
        )

        album = data.get(
            "album"
        ) or ""

        duration = data.get(
            "duration"
        )

        thumbnails = data.get(
            "thumbnails"
        ) or []

        cover_url = (
            thumbnails[-1].get("url")
            if thumbnails
            else data.get("thumbnail")
        )

        if not artist or not title:
            print(
                "Не удалось определить "
                "исполнителя или название."
            )
            return None

        return {
            "source": "youtube",
            "artist": artist,
            "title": title,
            "album": album,
            "duration": duration,
            "cover_url": cover_url
        }

    except FileNotFoundError:
        print(
            "Не найден yt-dlp.exe."
        )
        return None

    except (
        json.JSONDecodeError,
        subprocess.TimeoutExpired
    ):
        print(
            "Не удалось получить данные о треке."
        )
        return None

    except Exception as e:
        print(
            "Ошибка получения данных:",
            e
        )
        return None


def get_track_info(url):
    if is_yandex_music_url(url):
        return get_yandex_music_info(url)

    return get_youtube_music_info(url)


# ============================================================
# LRCLIB
# ============================================================

def search_lrclib(
    artist,
    title,
    album=None,
    duration=None
):

    status(
        "Поиск текста песни..."
    )

    clean_art = clean_search_query(
        artist
    )

    clean_tit = clean_search_query(
        title
    )

    # --------------------------------------------------------
    # 1. Точный запрос
    # --------------------------------------------------------

    if duration is not None:

        try:

            response = requests.get(
                "https://lrclib.net/api/get",
                params={
                    "track_name": clean_tit,
                    "artist_name": clean_art,
                    "duration":
                        int(
                            round(
                                float(duration)
                            )
                        )
                },
                headers={
                    "User-Agent":
                        HEADERS["User-Agent"],
                    "Accept":
                        "application/json"
                },
                timeout=TIMEOUT
            )

            if response.status_code == 200:

                data = response.json()

                synced = data.get(
                    "syncedLyrics"
                )

                plain = data.get(
                    "plainLyrics"
                )

                if synced and synced.strip():
                    return synced.strip()

                if plain and plain.strip():
                    return plain.strip()

        except Exception:
            pass

    # --------------------------------------------------------
    # 2. Гибкий поиск
    # --------------------------------------------------------

    queries = [
        f"{clean_art} {clean_tit}",
        f"{clean_tit}"
    ]

    plain_fallback = None

    for query in queries:

        try:

            response = requests.get(
                "https://lrclib.net/api/search",
                params={
                    "q": query
                },
                headers={
                    "User-Agent":
                        HEADERS["User-Agent"],
                    "Accept":
                        "application/json"
                },
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                continue

            results = response.json()

            if (
                not isinstance(results, list)
                or not results
            ):
                continue

            norm_target_title = normalize(
                title
            )

            for item in results:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                synced = item.get(
                    "syncedLyrics"
                )

                plain = item.get(
                    "plainLyrics"
                )

                if not synced and not plain:
                    continue

                item_track = normalize(
                    item.get(
                        "trackName"
                    ) or ""
                )

                target_words = normalize_words(
                    title
                )

                item_words = normalize_words(
                    item_track
                )

                if (
                    target_words
                    and not (
                        target_words
                        & item_words
                    )
                    and norm_target_title
                    not in item_track
                    and item_track
                    not in norm_target_title
                ):
                    continue

                if synced and synced.strip():
                    return synced.strip()

                if (
                    plain
                    and plain.strip()
                    and not plain_fallback
                ):
                    plain_fallback = plain.strip()

        except Exception:
            continue

    return plain_fallback


def save_lrc(
    mp3_filepath,
    lyrics
):

    path = (
        os.path.splitext(
            mp3_filepath
        )[0]
        + ".lrc"
    )

    try:

        with open(
            path,
            "w",
            encoding="utf-8-sig",
            newline="\n"
        ) as f:

            f.write(
                lyrics
            )

        print(
            "Текст сохранен в LRC."
        )

        return True

    except Exception:

        print(
            "Не удалось сохранить LRC."
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

        print(
            "Текст песни не найден."
        )

        return False

    is_synced = bool(
        re.search(
            r"\[\d{2}:\d{2}\.\d{2,3}\]",
            lyrics
        )
    )

    if is_synced:
        print(
            "Найден синхронизированный "
            "текст с таймкодами."
        )

    else:
        print(
            "Найден несинхронизированный "
            "обычный текст."
        )

    status(
        "Сохранение текста..."
    )

    return save_lrc(
        mp3_filepath,
        lyrics
    )


# ============================================================
# PLAYLIST
# ============================================================

def get_playlist_tracks(url):

    status(
        "Получение списка треков плейлиста..."
    )

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
            print(
                "Не удалось получить плейлист."
            )
            return None

        data = json.loads(
            result.stdout
        )

        tracks = []

        for entry in (
            data.get("entries")
            or []
        ):

            if not entry:
                continue

            track_url = (
                entry.get("webpage_url")
                or entry.get("original_url")
                or entry.get("url")
            )

            if not track_url:
                continue

            if not track_url.startswith(
                "http"
            ):
                track_url = (
                    "https://music.youtube.com/watch?v="
                    + track_url
                )

            tracks.append(
                track_url
            )

        if not tracks:
            return None

        return {
            "title":
                data.get("title")
                or "YouTube Music",
            "tracks":
                tracks
        }

    except Exception:

        print(
            "Не удалось получить плейлист."
        )

        return None


# ============================================================
# AUDIO VALIDATION
# ============================================================

def validate_audio_file(filename):

    if (
        not os.path.exists(filename)
        or os.path.getsize(filename)
        < MIN_FILE_SIZE
    ):
        return False

    try:

        result = subprocess.run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration",
                "-of",
                "json",
                filename
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if result.returncode != 0:
            return False

        duration = (
            json.loads(
                result.stdout
            )
            .get("format", {})
            .get("duration")
        )

        return bool(
            duration
            and float(duration) > 0
        )

    except Exception:
        return False


def get_duration(url):

    try:

        result = subprocess.run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                url
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if (
            result.returncode == 0
            and result.stdout.strip()
        ):
            return float(
                result.stdout.strip()
            )

    except Exception:
        pass

    return None


# ============================================================
# DIRECT DOWNLOAD
# ============================================================

def download_file(
    url,
    filename,
    referer=None,
    retries=1
):

    status(
        "Скачивание аудиофайла..."
    )

    temp_filename = (
        filename + ".tmp"
    )

    for attempt in range(
        1,
        retries + 1
    ):

        try:

            if os.path.exists(
                temp_filename
            ):
                os.remove(
                    temp_filename
                )

            headers = dict(
                HEADERS
            )

            headers["Accept"] = (
                "audio/mpeg,audio/*;"
                "q=0.9,*/*;q=0.8"
            )

            headers["Range"] = (
                "bytes=0-"
            )

            if referer:
                headers["Referer"] = (
                    referer
                )

            with requests.Session() as session:

                response = session.get(
                    url,
                    headers=headers,
                    timeout=60,
                    stream=True,
                    allow_redirects=True
                )

                if response.status_code not in (
                    200,
                    206
                ):

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                content_type = (
                    response.headers
                    .get(
                        "Content-Type",
                        ""
                    )
                    .lower()
                )

                total = 0

                with open(
                    temp_filename,
                    "wb"
                ) as f:

                    for chunk in response.iter_content(
                        chunk_size=262144
                    ):

                        if chunk:
                            f.write(chunk)
                            total += len(chunk)

                if (
                    "text/html"
                    in content_type
                    or "text/plain"
                    in content_type
                    or total < MIN_FILE_SIZE
                ):

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                status(
                    "Проверка аудиофайла..."
                )

                if not validate_audio_file(
                    temp_filename
                ):

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                if os.path.exists(
                    filename
                ):
                    os.remove(
                        filename
                    )

                os.replace(
                    temp_filename,
                    filename
                )

                print(
                    "Аудиофайл готов."
                )

                return True

        except Exception:

            if attempt < retries:
                time.sleep(1)
                continue

            return False

    return False


# ============================================================
# SOUNDCloud CLIENT ID
# ============================================================

def get_soundcloud_client_id():

    try:

        response = requests.get(
            "https://soundcloud.com/",
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_CLIENT_ID_TIMEOUT
        )

        if response.status_code != 200:
            return None

        text = response.text

        patterns = [
            r'client_id["\']?\s*[:=]\s*["\']'
            r'([A-Za-z0-9_-]{32,})["\']',

            r'clientId["\']?\s*[:=]\s*["\']'
            r'([A-Za-z0-9_-]{32,})["\']'
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.I
            )

            if match:
                return match.group(1)

        scripts = re.findall(
            r'<script[^>]+src=["\']'
            r'([^"\']+)["\']',
            text,
            re.I
        )

        for script in scripts:

            if script.startswith("//"):
                script = "https:" + script

            elif script.startswith("/"):
                script = (
                    "https://soundcloud.com"
                    + script
                )

            elif not script.startswith(
                "http"
            ):
                continue

            try:

                r = requests.get(
                    script,
                    headers=SOUNDCLOUD_HEADERS,
                    timeout=SOUNDCLOUD_CLIENT_ID_TIMEOUT
                )

                if r.status_code != 200:
                    continue

                for pattern in patterns:

                    match = re.search(
                        pattern,
                        r.text,
                        re.I
                    )

                    if match:
                        return match.group(1)

            except Exception:
                continue

    except Exception:
        pass

    return None


# ============================================================
# SOUNDCloud CANDIDATE EVALUATION
# ============================================================

def evaluate_soundcloud_candidate(
    found_artist,
    found_title,
    candidate_duration,
    target_artist,
    target_title,
    target_duration
):

    if (
        target_duration is not None
        and candidate_duration is not None
    ):

        if (
            abs(
                candidate_duration
                - target_duration
            )
            > SOUNDCLOUD_DURATION_TOLERANCE
        ):
            return False, 0, False

    norm_requested = normalize(
        f"{target_artist} {target_title}"
    )

    norm_title = normalize(
        found_title
    )

    norm_artist = normalize(
        found_artist
    )

    norm_combined = (
        f"{norm_artist} {norm_title}"
    )

    strict_modifiers = {
        "remix",
        "slowed",
        "speed up",
        "speedup",
        "sped up",
        "sped",
        "phonk",
        "instrumental",
        "cover",
        "nightcore",
        "hardstyle"
    }

    for mod in strict_modifiers:

        if (
            mod in norm_combined
            and mod not in norm_requested
        ):
            return False, 0, False

    target_artist_words = normalize_words(
        target_artist
    )

    target_title_words = normalize_words(
        target_title
    )

    artist_words = normalize_words(
        found_artist
    )

    title_words = normalize_words(
        found_title
    )

    combined_words = normalize_words(
        norm_combined
    )

    if not target_title_words:
        return False, 0, False

    title_match_ratio = (
        len(
            target_title_words
            & combined_words
        )
        / len(target_title_words)
    )

    if title_match_ratio < 0.4:
        return False, 0, False

    artist_match_ratio = (
        len(
            target_artist_words
            & combined_words
        )
        / len(target_artist_words)
        if target_artist_words
        else 1.0
    )

    artist_in_artist_field = (
        artist_match_ratio >= 0.6
    )

    title_in_title_field = (
        len(
            target_title_words
            & title_words
        )
        / len(target_title_words)
    ) >= 0.6

    artist_and_title_in_title = (
        artist_match_ratio >= 0.6
        and
        (
            len(
                target_title_words
                & title_words
            )
            / len(target_title_words)
        ) >= 0.6
    )

    is_strict = (
        (
            artist_in_artist_field
            and title_in_title_field
        )
        or artist_and_title_in_title
    )

    score = (
        artist_match_ratio * 300
    ) + (
        title_match_ratio * 500
    )

    if (
        target_duration is not None
        and candidate_duration is not None
    ):

        diff = abs(
            candidate_duration
            - target_duration
        )

        score += max(
            0,
            300 - diff * 30
        )

    return True, score, is_strict


# ============================================================
# SOUNDCloud SEARCH
# ============================================================

def fetch_soundcloud_results(
    query_str,
    client_id
):

    try:

        response = requests.get(
            "https://api-v2.soundcloud.com/search/tracks",
            params={
                "q": query_str,
                "client_id": client_id,
                "limit": SOUNDCLOUD_SEARCH_RESULTS
            },
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_SEARCH_TIMEOUT
        )

        if response.status_code == 200:
            return (
                response.json()
                .get("collection")
                or []
            )

    except Exception:
        pass

    return []


def search_soundcloud(
    artist,
    title,
    target_duration=None
):

    status(
        "Поиск на SoundCloud..."
    )

    client_id = get_soundcloud_client_id()

    if not client_id:
        print(
            "SoundCloud недоступен."
        )
        return None

    clean_art = clean_search_query(
        artist
    )

    clean_tit = clean_search_query(
        title
    )

    queries = [
        f"{clean_art} {clean_tit}",
        f"{clean_tit}"
    ]

    strict_candidates = []

    fallback_candidates = []

    for q in queries:

        collection = fetch_soundcloud_results(
            q,
            client_id
        )

        if not collection:
            continue

        for entry in collection:

            if not isinstance(
                entry,
                dict
            ):
                continue

            permalink_url = (
                entry.get(
                    "permalink_url"
                )
                or ""
            )

            if not permalink_url:

                user = (
                    entry.get("user")
                    or {}
                )

                username = (
                    user.get("permalink")
                    or ""
                )

                permalink = (
                    entry.get("permalink")
                    or ""
                )

                if username and permalink:

                    permalink_url = (
                        "https://soundcloud.com/"
                        f"{username}/{permalink}"
                    )

            if not permalink_url:
                continue

            found_title = (
                entry.get("title")
                or ""
            )

            found_artist = (
                entry.get("user")
                or {}
            ).get(
                "username"
            ) or ""

            candidate_duration = (
                entry.get("duration")
            )

            try:

                candidate_duration = (
                    float(candidate_duration)
                    / 1000
                    if candidate_duration
                    is not None
                    else None
                )

            except Exception:

                candidate_duration = None

            is_valid, score, is_strict = (
                evaluate_soundcloud_candidate(
                    found_artist,
                    found_title,
                    candidate_duration,
                    artist,
                    title,
                    target_duration
                )
            )

            if not is_valid:
                continue

            candidate_info = {
                "url": permalink_url,
                "title": found_title,
                "artist": found_artist,
                "duration": candidate_duration,
                "final_score": score
            }

            if is_strict:
                strict_candidates.append(
                    candidate_info
                )

            else:
                fallback_candidates.append(
                    candidate_info
                )

        if (
            strict_candidates
            or fallback_candidates
        ):
            break

    if strict_candidates:

        strict_candidates.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        best = strict_candidates[0]

        print(
            "Найден трек SoundCloud "
            "(точное совпадение): "
            f"{best['artist']} - "
            f"{best['title']}"
        )

        return best

    if fallback_candidates:

        fallback_candidates.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        best = fallback_candidates[0]

        print(
            "Найден трек SoundCloud "
            "(гибкое совпадение): "
            f"{best['artist']} - "
            f"{best['title']}"
        )

        return best

    print(
        "Подходящий трек на SoundCloud "
        "не найден."
    )

    return None


# ============================================================
# SOUNDCloud DOWNLOAD
# ============================================================

def download_from_soundcloud(
    soundcloud_url,
    filepath,
    target_duration=None
):

    status(
        "Скачивание с SoundCloud..."
    )

    temp_template = (
        os.path.splitext(filepath)[0]
        + ".soundcloud.tmp.%(ext)s"
    )

    command = [
        YTDLP,

        "--no-playlist",
        "--quiet",
        "--no-warnings",

        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",

        # ====================================================
        # УСКОРЕНИЕ SOUNDCloud:
        # одновременная загрузка нескольких фрагментов
        # ====================================================
        "--concurrent-fragments",
        "8",

        "--no-part",

        "-o",
        temp_template,

        soundcloud_url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SOUNDCLOUD_DOWNLOAD_TIMEOUT
        )

    except subprocess.TimeoutExpired:

        print(
            "Скачивание SoundCloud "
            "превысило лимит времени."
        )

        return False

    except Exception:

        print(
            "Не удалось скачать трек с SoundCloud."
        )

        return False

    if result.returncode != 0:

        print(
            "SoundCloud не удалось скачать. "
            "Переходим к следующему источнику..."
        )

        return False

    directory = os.path.dirname(
        filepath
    )

    base = os.path.splitext(
        os.path.basename(filepath)
    )[0]

    possible_files = []

    if os.path.isdir(directory):

        for filename in os.listdir(
            directory
        ):

            if filename.startswith(
                base + ".soundcloud.tmp."
            ):

                possible_files.append(
                    os.path.join(
                        directory,
                        filename
                    )
                )

    if not possible_files:

        print(
            "Скачанный файл не найден."
        )

        return False

    source_file = max(
        possible_files,
        key=os.path.getmtime
    )

    if not validate_audio_file(
        source_file
    ):

        try:
            os.remove(
                source_file
            )
        except Exception:
            pass

        print(
            "Скачанный файл не прошёл проверку."
        )

        return False

    actual_duration = get_duration(
        source_file
    )

    if not is_duration_acceptable(
        actual_duration,
        target_duration,
        SOUNDCLOUD_DURATION_TOLERANCE
    ):

        try:
            os.remove(
                source_file
            )
        except Exception:
            pass

        print(
            "Длительность скачанного файла "
            "значительно отличается от оригинальной."
        )

        return False

    if os.path.exists(
        filepath
    ):
        os.remove(
            filepath
        )

    os.replace(
        source_file,
        filepath
    )

    print(
        "Аудиофайл готов."
    )

    return True


# ============================================================
# MP3PARTY
# ============================================================

def search_mp3party(
    artist,
    title,
    target_duration=None
):

    try:

        response = requests.get(
            "https://mp3party.net/search",
            params={
                "q":
                    f"{artist} {title}"
            },
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return None

        text = html.unescape(
            response.text
        )

        pattern = re.compile(
            r'<div class="track__user-panel"'
            r'[^>]*data-js-artist-name="([^"]+)"'
            r'[^>]*data-js-id="(\d+)"'
            r'[^>]*data-js-song-title="([^"]+)"'
            r'[^>]*data-js-url="([^"]+)"',
            re.I
        )

        candidates = []

        for (
            found_artist,
            song_id,
            found_title,
            found_url
        ) in pattern.findall(text):

            score = candidate_text_score(
                f"{found_artist} - {found_title}",
                artist,
                title
            )

            if score < 0:
                continue

            candidates.append({
                "url":
                    f"https://dl2.mp3party.net/download/{song_id}",

                "referer":
                    f"https://mp3party.net/music/{song_id}",

                "text_score":
                    score
            })

        if not candidates:
            return None

        candidates.sort(
            key=lambda x:
                x["text_score"],
            reverse=True
        )

        for candidate in candidates[:10]:

            duration = get_duration(
                candidate["url"]
            )

            if is_duration_acceptable(
                duration,
                target_duration
            ):
                return {
                    "url":
                        candidate["url"],

                    "referer":
                        candidate["referer"]
                }

    except Exception:
        pass

    return None


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    query = (
        f"{artist} {title}"
    )

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip(
        "-"
    ).lower()

    page_url = (
        f"https://{slug}.mp3tm.net/"
    )

    try:

        response = requests.get(
            page_url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return None

        links = list(
            dict.fromkeys(
                re.findall(
                    r'https?://[^"\']+\.mp3'
                    r'(?:\?[^"\']*)?',
                    html.unescape(
                        response.text
                    ),
                    re.I
                )
            )
        )

        candidates = []

        for link in links:

            filename = clean_filename(
                link.split("/")[-1]
            )

            score = candidate_text_score(
                filename,
                artist,
                title
            )

            if score >= 0:
                candidates.append(
                    (score, link)
                )

        candidates.sort(
            reverse=True
        )

        for _, link in candidates:

            duration = get_duration(
                link
            )

            if is_duration_acceptable(
                duration,
                target_duration
            ):

                return {
                    "url": link,
                    "referer": page_url
                }

    except Exception:
        pass

    return None


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(
    artist,
    title,
    target_duration=None
):

    try:

        response = requests.get(
            "https://audiostart.net/",
            params={
                "song":
                    f"{artist} {title}"
            },
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return None

        links = list(
            dict.fromkeys(
                re.findall(
                    r'href=["\']'
                    r'([^"\']*?/getmp3/[^"\']+)'
                    r'["\']',
                    html.unescape(
                        response.text
                    ),
                    re.I
                )
            )
        )

        candidates = []

        for link in links:

            try:

                encoded = (
                    link.split(
                        "/getmp3/",
                        1
                    )[1]
                )

                decoded = (
                    unquote(
                        base64.b64decode(
                            encoded
                        ).decode(
                            "utf-8",
                            errors="ignore"
                        )
                    )
                )

                score = candidate_text_score(
                    decoded,
                    artist,
                    title
                )

                if score >= 0:

                    if link.startswith("//"):
                        link = "https:" + link

                    elif link.startswith("/"):
                        link = (
                            "https://audiostart.net"
                            + link
                        )

                    candidates.append(
                        (score, link)
                    )

            except Exception:
                continue

        candidates.sort(
            reverse=True
        )

        for _, link in candidates:

            duration = get_duration(
                link
            )

            if is_duration_acceptable(
                duration,
                target_duration
            ):

                return {
                    "url": link,
                    "referer":
                        "https://audiostart.net/"
                }

    except Exception:
        pass

    return None


# ============================================================
# YOUTUBE FALLBACK
# ============================================================

def download_with_ytdlp(
    youtube_url,
    filepath
):

    status(
        "Резервное скачивание..."
    )

    temp_template = (
        os.path.splitext(filepath)[0]
        + ".yt-dlp.tmp.%(ext)s"
    )

    command = [
        YTDLP,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "-o",
        temp_template,
        youtube_url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180
        )

        if result.returncode != 0:
            return False

        directory = os.path.dirname(
            filepath
        )

        base = os.path.splitext(
            os.path.basename(filepath)
        )[0]

        files = [
            os.path.join(
                directory,
                f
            )
            for f in os.listdir(
                directory
            )
            if f.startswith(
                base + ".yt-dlp.tmp."
            )
        ]

        if not files:
            return False

        source_file = max(
            files,
            key=os.path.getmtime
        )

        if not validate_audio_file(
            source_file
        ):

            try:
                os.remove(
                    source_file
                )
            except Exception:
                pass

            return False

        if os.path.exists(
            filepath
        ):
            os.remove(
                filepath
            )

        os.replace(
            source_file,
            filepath
        )

        print(
            "Аудиофайл готов."
        )

        return True

    except Exception:
        return False


# ============================================================
# FIND + DOWNLOAD
# ============================================================

def find_and_download_track(
    artist,
    title,
    duration,
    output_folder,
    source_url,
    source
):

    print()
    print("=" * 60)
    print("ПОИСК АУДИОФАЙЛА")
    print("=" * 60)

    filename = (
        f"{safe_filename(artist)} - "
        f"{safe_filename(title)}.mp3"
    )

    filepath = os.path.join(
        output_folder,
        filename
    )

    # --------------------------------------------------------
    # SOUNDCloud
    # --------------------------------------------------------

    result = search_soundcloud(
        artist,
        title,
        duration
    )

    if result:

        if download_from_soundcloud(
            result["url"],
            filepath,
            duration
        ):
            return filepath

    # --------------------------------------------------------
    # MP3Party
    # --------------------------------------------------------

    status(
        "Проверка MP3Party..."
    )

    result = search_mp3party(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            result["referer"],
            MP3PARTY_RETRIES
        ):
            return filepath

    # --------------------------------------------------------
    # MP3TM
    # --------------------------------------------------------

    status(
        "Проверка MP3TM..."
    )

    result = search_mp3tm(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            result["referer"],
            2
        ):
            return filepath

    # --------------------------------------------------------
    # AudioStart
    # --------------------------------------------------------

    status(
        "Проверка AudioStart..."
    )

    result = search_audiostart(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            result["referer"],
            2
        ):
            return filepath

    # --------------------------------------------------------
    # YouTube fallback
    # --------------------------------------------------------

    if source == "youtube" and source_url:

        if download_with_ytdlp(
            source_url,
            filepath
        ):
            return filepath

    print(
        "Не удалось скачать подходящий аудиофайл."
    )

    return None


# ============================================================
# SINGLE TRACK
# ============================================================

def process_single_track(
    url,
    output_folder
):

    info = get_track_info(
        url
    )

    if not info:
        return False

    source = info.get(
        "source",
        "youtube"
    )

    artist = info["artist"]
    title = info["title"]

    album = info["album"]
    duration = info["duration"]

    cover_url = info.get(
        "cover_url"
    )

    print()
    print("=" * 60)
    print("ИНФОРМАЦИЯ О ТРЕКЕ")
    print("=" * 60)

    print(
        f"Источник: {source}"
    )

    print(
        f"Исполнитель: {artist}"
    )

    print(
        f"Название: {title}"
    )

    if album:
        print(
            f"Альбом: {album}"
        )

    print(
        f"Длительность: "
        f"{format_duration(duration)}"
    )

    print(
        f"Обложка: "
        f"{'НАЙДЕНА' if cover_url else 'НЕ НАЙДЕНА'}"
    )

    source_url = (
        url
        if source == "youtube"
        else None
    )

    filepath = find_and_download_track(
        artist,
        title,
        duration,
        output_folder,
        source_url,
        source
    )

    if not filepath:
        return False

    embed_cover(
        filepath,
        cover_url,
        artist,
        title,
        album
    )

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
# PLAYLIST PROCESSING
# ============================================================

def process_playlist(url):

    playlist = get_playlist_tracks(
        url
    )

    if not playlist:

        print(
            "Не удалось получить плейлист."
        )

        return

    playlist_title = safe_filename(
        playlist["title"]
    )

    output_folder = os.path.join(
        PROJECT_FOLDER,
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
        f"Название: {playlist['title']}"
    )

    print(
        f"Треков: {len(tracks)}"
    )

    downloaded = 0
    failed = 0

    for index, track_url in enumerate(
        tracks,
        1
    ):

        print()
        print(
            f"Трек {index}/{len(tracks)}"
        )

        if process_single_track(
            track_url,
            output_folder
        ):
            downloaded += 1

        else:
            failed += 1

    print()
    print("=" * 60)
    print("ПЛЕЙЛИСТ ЗАВЕРШЁН")
    print("=" * 60)

    print(
        f"Всего треков: {len(tracks)}"
    )

    print(
        f"Скачано: {downloaded}"
    )

    print(
        f"Не скачано: {failed}"
    )

    print(
        f"Папка: {output_folder}"
    )


# ============================================================
# URL PLAYLIST
# ============================================================

def is_playlist_url(url):

    return (
        "list=" in url
        and (
            "youtube.com" in url
            or "music.youtube.com" in url
        )
    )


# ============================================================
# ENVIRONMENT
# ============================================================

def check_environment():

    errors = []

    for path, name in (
        (YTDLP, "yt-dlp.exe"),
        (FFMPEG, "ffmpeg.exe"),
        (FFPROBE, "ffprobe.exe")
    ):

        if not os.path.isfile(path):

            errors.append(
                f"Не найден {name}:\n"
                f"{path}"
            )

    if errors:

        print("=" * 60)
        print(
            "ОШИБКА СТРУКТУРЫ ПРОЕКТА"
        )
        print("=" * 60)

        for error in errors:

            print()
            print(error)

        return False

    os.makedirs(
        TRACKS_FOLDER,
        exist_ok=True
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    global DOWNLOAD_LRC

    print("=" * 60)
    print("YTMUSIC DOWNLOADER")
    print("=" * 60)
    print()

    if not check_environment():

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    print(
        "Скачивать текст песни "
        "в формате LRC?"
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

        print(
            "Введите 1 или 2."
        )

    print()

    url = input(
        "Ссылка на трек или плейлист "
        "YouTube Music/Яндекс Музыка: "
    ).strip()

    if not url:

        print(
            "Ссылка не указана."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    if is_playlist_url(url):

        process_playlist(
            url
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    success = process_single_track(
        url,
        TRACKS_FOLDER
    )

    print()
    print("=" * 60)

    print(
        "ТРЕК УСПЕШНО СКАЧАН"
        if success
        else
        "ТРЕК НЕ СКАЧАН"
    )

    print("=" * 60)

    if success:

        print()

        print(
            "Папка:",
            TRACKS_FOLDER
        )

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
