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

from sources_soundcloud import (
    get_soundcloud_client_id,
    normalize_soundcloud_metadata,
    evaluate_soundcloud_candidate,
    fetch_soundcloud_results,
    search_soundcloud,
    download_from_soundcloud,
)

from sources_mp3party import search_mp3party

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive"
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

YOUTUBE_INFO_RETRIES = 3

YOUTUBE_INFO_RETRY_DELAYS = (
    2,
    5
)

# Последняя диагностическая ошибка yt-dlp.
# Важно:
# age restriction не считается окончательной ошибкой,
# если позже удалось получить метаданные или скачать файл.
LAST_YOUTUBE_ERROR = ""

# КЭШ SOUNDCLOUD CLIENT ID

SOUNDCLOUD_CLIENT_ID_CACHE = None

def status(message):
    print()
    print(message)

def normalize(text):
    text = html.unescape(str(text))
    text = unquote(text)
    text = text.replace("–", "-").replace("—", "-").replace("_", " ")
    text = re.sub(r"\(MP3\.tm\)", "", text, flags=re.I)
    text = re.sub(r"\(audiostart\.net\)", "", text, flags=re.I)
    text = re.sub(r"\.mp3$", "", text, flags=re.I)
    text = text.lower()
    text = re.sub(r"\bof\s+buda\b", "og buda", text)
    text = re.sub(r"\bfeaturing\b", "feat", text)
    text = re.sub(r"\bft\.?\b", "feat", text)
    text = re.sub(r"\bfeat\.?\b", " ", text)
    text = re.sub(r"[,;|/\\]+", " ", text)
    text = re.sub(r"[()[\]{}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

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

    text = text.replace(
        "_",
        " "
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()

def safe_filename(name):
    """
    Безопасная очистка имени файла для Windows.

    Удаляются только:
      - управляющие ASCII-символы;
      - запрещённые Windows-символы.

    Обычные латинские символы,
    кириллица, цифры, пробелы,
    скобки, точки, дефисы и Unicode
    сохраняются.
    """

    if name is None:
        return ""

    text = str(name)

    result = []

    for char in text:
        code = ord(char)

        # Управляющие ASCII-символы.
        if code < 32 or code == 127:
            continue

        # Запрещённые Windows-символы:
        # < > : " / \ | ? *
        if char in '<>:"/\\|?*':
            continue

        result.append(char)

    text = "".join(result)

    # Windows не разрешает пробел или точку
    # в конце имени файла.
    text = text.rstrip(" .")

    if not text:
        text = "audio"

    return text

def format_duration(seconds):
    if seconds is None:
        return "??:??"

    try:
        seconds = int(
            round(
                float(seconds)
            )
        )
    except Exception:
        return "??:??"

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )

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

def extract_youtube_video_id(url):
    if not url:
        return None

    patterns = (
        r"[?&]v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})"
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            url,
            re.I
        )

        if match:
            return match.group(1)

    return None

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
        "album_id": (
            album_match.group(1)
            if album_match
            else ""
        )
    }

def get_yandex_music_info(url):
    status(
        "Получение информации из Яндекс Музыки..."
    )

    parsed = parse_yandex_url(url)

    if not parsed:
        print(
            "Не удалось определить ID трека "
            "Яндекс Музыки."
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
            "Не удалось получить данные "
            "Яндекс Музыки."
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
            "Не удалось обработать данные "
            "Яндекс Музыки."
        )
        return None

    result = data.get("result")

    if isinstance(result, dict):
        result = result.get(
            "track",
            result
        )

    elif isinstance(result, list):
        result = (
            result[0]
            if result
            else None
        )

    if not isinstance(result, dict):
        return None

    track = result

    artists = track.get("artists") or []

    artist = ", ".join(
        str(x.get("name"))
        for x in artists
        if (
            isinstance(x, dict)
            and x.get("name")
        )
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
            cover_url = (
                "https:"
                + cover_url
            )

        elif not cover_url.startswith(
            (
                "http://",
                "https://"
            )
        ):
            cover_url = (
                "https://"
                + cover_url
            )

    if (
        not artist
        or not title
        or duration is None
    ):
        print(
            "Не удалось определить "
            "данные трека."
        )
        return None

    print(
        f"Исполнитель: {artist}"
    )

    print(
        f"Название: {title}"
    )

    print(
        f"Альбом: "
        f"{album or 'не определён'}"
    )

    print(
        f"Длительность: "
        f"{format_duration(duration)}"
    )

    print(
        "Обложка: "
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

# YOUTUBE AGE RESTRICTION

def is_youtube_age_error(error_text):
    if not error_text:
        return False

    text = error_text.lower()

    age_markers = (
        "sign in to confirm your age",
        "confirm your age",
        "age-restricted",
        "age restricted",
        "this video may be inappropriate",
        "use --cookies-from-browser",
        "age verification"
    )

    return any(
        marker in text
        for marker in age_markers
    )

# YOUTUBE CLIENT COMMAND

def build_ytdlp_command(
    base_command,
    client=None
):
    command = list(base_command)

    if client:
        try:
            output_index = command.index(
                "-o"
            )
        except ValueError:
            output_index = len(command)

        command[
            output_index:output_index
        ] = [
            "--extractor-args",
            f"youtube:player_client={client}"
        ]

    return command

# JSON EXTRACTION FROM YOUTUBE MUSIC HTML

def extract_json_after_marker(
    text,
    marker
):
    """
    Ищет JSON-объект после указанного маркера.

    Не используется обычный regex с .*,
    потому что JSON содержит вложенные объекты.
    """

    position = text.find(
        marker
    )

    if position < 0:
        return None

    start = text.find(
        "{",
        position + len(marker)
    )

    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start,
        len(text)
    ):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False

            elif char == "\\":
                escaped = True

            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                candidate = text[
                    start:index + 1
                ]

                try:
                    return json.loads(
                        candidate
                    )
                except Exception:
                    return None

    return None

def extract_youtube_music_json_objects(
    text
):
    objects = []

    markers = (
        "ytInitialPlayerResponse =",
        "ytInitialData =",
        "var ytInitialPlayerResponse =",
        "var ytInitialData =",
        "window['ytInitialPlayerResponse'] =",
        "window['ytInitialData'] ="
    )

    for marker in markers:
        data = extract_json_after_marker(
            text,
            marker
        )

        if isinstance(
            data,
            dict
        ):
            objects.append(
                data
            )

    return objects

def collect_text_runs(value):
    """
    Рекурсивно собирает текст из структур
    YouTube runs/text.
    """

    result = []

    if isinstance(value, dict):
        if isinstance(
            value.get("simpleText"),
            str
        ):
            result.append(
                value["simpleText"]
            )

        runs = value.get(
            "runs"
        )

        if isinstance(
            runs,
            list
        ):
            for run in runs:
                if isinstance(
                    run,
                    dict
                ):
                    text = run.get(
                        "text"
                    )

                    if text:
                        result.append(
                            str(text)
                        )

        for key, item in value.items():
            if key in (
                "runs",
                "simpleText"
            ):
                continue

            result.extend(
                collect_text_runs(item)
            )

    elif isinstance(value, list):
        for item in value:
            result.extend(
                collect_text_runs(item)
            )

    return result

def get_first_text(value):
    texts = collect_text_runs(
        value
    )

    for text in texts:
        if (
            isinstance(text, str)
            and text.strip()
        ):
            return text.strip()

    return ""

def recursive_find_video_node(
    obj,
    video_id
):
    """
    Ищет объект, содержащий нужный videoId.
    """

    if isinstance(
        obj,
        dict
    ):
        if obj.get("videoId") == video_id:
            return obj

        for value in obj.values():
            found = recursive_find_video_node(
                value,
                video_id
            )

            if found is not None:
                return found

    elif isinstance(
        obj,
        list
    ):
        for item in obj:
            found = recursive_find_video_node(
                item,
                video_id
            )

            if found is not None:
                return found

    return None

def recursive_find_key(
    obj,
    key
):
    if isinstance(
        obj,
        dict
    ):
        if key in obj:
            return obj[key]

        for value in obj.values():
            found = recursive_find_key(
                value,
                key
            )

            if found is not None:
                return found

    elif isinstance(
        obj,
        list
    ):
        for item in obj:
            found = recursive_find_key(
                item,
                key
            )

            if found is not None:
                return found

    return None

def extract_youtube_music_metadata_from_json(
    data,
    video_id
):
    """
    Пытается извлечь title / artist / album /
    duration / thumbnail из ytInitialData или
    ytInitialPlayerResponse.
    """

    artist = ""
    title = ""
    album = ""
    duration = None
    cover_url = None

    # 1. videoDetails

    video_details = data.get(
        "videoDetails"
    )

    if isinstance(
        video_details,
        dict
    ):
        if video_details.get(
            "videoId"
        ) == video_id:

            title = (
                video_details.get(
                    "title"
                )
                or ""
            )

            length_seconds = (
                video_details.get(
                    "lengthSeconds"
                )
            )

            if length_seconds:
                try:
                    duration = float(
                        length_seconds
                    )
                except Exception:
                    pass

            thumbnail = (
                video_details.get(
                    "thumbnail"
                )
            )

            if isinstance(
                thumbnail,
                dict
            ):
                thumbnails = (
                    thumbnail.get(
                        "thumbnails"
                    )
                    or []
                )

                if thumbnails:
                    cover_url = (
                        thumbnails[-1].get(
                            "url"
                        )
                    )

    # 2. Ищем node нужного видео.

    node = recursive_find_video_node(
        data,
        video_id
    )

    if node:
        if not title:
            title = (
                get_first_text(
                    node.get("title")
                )
                or get_first_text(
                    node.get("headline")
                )
            )

        if not cover_url:
            thumbnail = node.get(
                "thumbnail"
            )

            if isinstance(
                thumbnail,
                dict
            ):
                thumbnails = (
                    thumbnail.get(
                        "thumbnails"
                    )
                    or []
                )

                if thumbnails:
                    cover_url = (
                        thumbnails[-1].get(
                            "url"
                        )
                    )

        if duration is None:
            length_text = (
                get_first_text(
                    node.get("lengthText")
                )
            )

            if length_text:
                match = re.match(
                    r"(?:(\d+):)?(\d+):(\d+)$",
                    length_text.strip()
                )

                if match:
                    groups = match.groups()

                    try:
                        if groups[0]:
                            duration = (
                                int(groups[0])
                                * 3600
                                + int(groups[1])
                                * 60
                                + int(groups[2])
                            )
                        else:
                            duration = (
                                int(groups[1])
                                * 60
                                + int(groups[2])
                            )
                    except Exception:
                        pass

    # 3. YouTube Music metadata.
    # В разных версиях страницы структура отличается,
    # поэтому ищем несколько возможных полей.

    music_track = recursive_find_key(
        data,
        "musicTrack"
    )

    if isinstance(
        music_track,
        dict
    ):
        title = (
            title
            or get_first_text(
                music_track.get("title")
            )
        )

        artist = (
            artist
            or get_first_text(
                music_track.get("artist")
            )
        )

        album = (
            album
            or get_first_text(
                music_track.get("album")
            )
        )

    # 4. Попытка найти исполнителя через
    # owner / author / byline.

    possible_artist_keys = (
        "author",
        "ownerText",
        "longBylineText",
        "shortBylineText",
        "bylineText"
    )

    for key in possible_artist_keys:
        if artist:
            break

        value = recursive_find_key(
            data,
            key
        )

        text = get_first_text(
            value
        )

        if text:
            artist = text

    # 5. Если title найден, но artist всё ещё нет,
    # пытаемся использовать музыкальные строки.

    if not artist:
        text_candidates = []

        for key in (
            "subtitle",
            "description",
            "secondTitle"
        ):
            value = recursive_find_key(
                data,
                key
            )

            text = get_first_text(
                value
            )

            if text:
                text_candidates.append(
                    text
                )

        for candidate in text_candidates:
            parts = [
                x.strip()
                for x in re.split(
                    r"\s*[•·|]\s*",
                    candidate
                )
                if x.strip()
            ]

            if parts:
                for part in parts:
                    lowered = part.lower()

                    if (
                        lowered
                        not in (
                            "youtube music",
                            "music"
                        )
                        and part != title
                    ):
                        artist = part
                        break

            if artist:
                break

    # 6. Иногда title приходит в формате
    # "Artist - Title".

    if (
        not artist
        and title
        and " - " in title
    ):
        possible_artist, possible_title = (
            title.split(
                " - ",
                1
            )
        )

        if (
            possible_artist.strip()
            and possible_title.strip()
        ):
            artist = (
                possible_artist.strip()
            )

            title = (
                possible_title.strip()
            )

    if not title:
        return None

    return {
        "artist": artist.strip(),
        "title": title.strip(),
        "album": album.strip(),
        "duration": duration,
        "cover_url": cover_url
    }

# DIRECT YOUTUBE MUSIC METADATA FALLBACK

def get_youtube_music_page_info(
    url
):
    """
    Прямое получение метаданных со страницы
    music.youtube.com.

    Это отдельный fallback и не зависит от
    успешности YouTube player API.
    """

    status(
        "Получение метаданных непосредственно "
        "со страницы YouTube Music..."
    )

    video_id = extract_youtube_video_id(
        url
    )

    if not video_id:
        return None

    page_urls = [
        (
            "https://music.youtube.com/watch?v="
            + video_id
        ),
        (
            "https://www.youtube.com/watch?v="
            + video_id
        )
    ]

    for page_url in page_urls:
        try:
            response = requests.get(
                page_url,
                headers={
                    **HEADERS,
                    "Referer": (
                        "https://music.youtube.com/"
                    )
                },
                timeout=30,
                allow_redirects=True
            )

        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        text = response.text

        # Сначала стандартные JSON-объекты.

        json_objects = (
            extract_youtube_music_json_objects(
                text
            )
        )

        for data in json_objects:
            info = (
                extract_youtube_music_metadata_from_json(
                    data,
                    video_id
                )
            )

            if not info:
                continue

            if (
                info.get("artist")
                and info.get("title")
            ):
                print()
                print(
                    "Метаданные получены "
                    "непосредственно "
                    "со страницы YouTube Music."
                )

                return {
                    "source": "youtube",
                    "artist": info["artist"],
                    "title": info["title"],
                    "album": info.get("album") or "",
                    "duration": info.get("duration"),
                    "cover_url": info.get("cover_url"),
                    "youtube_client": "webpage",
                    "age_restricted": False
                }

        # Дополнительный fallback:
        # JSON-LD / meta tags.

        title = ""
        artist = ""
        album = ""
        duration = None
        cover_url = None

        match = re.search(
            r'<meta[^>]+itemprop=["\']name["\']'
            r'[^>]+content=["\']([^"\']+)',
            text,
            re.I
        )

        if match:
            title = html.unescape(
                match.group(1)
            )

        if not title:
            match = re.search(
                r'<meta[^>]+property=["\']og:title["\']'
                r'[^>]+content=["\']([^"\']+)',
                text,
                re.I
            )

            if match:
                title = html.unescape(
                    match.group(1)
                )

        match = re.search(
            r'<meta[^>]+itemprop=["\']author["\']'
            r'[^>]+content=["\']([^"\']+)',
            text,
            re.I
        )

        if match:
            artist = html.unescape(
                match.group(1)
            )

        if not artist:
            match = re.search(
                r'"author":\s*\{\s*"name":\s*"([^"]+)"',
                text,
                re.I
            )

            if match:
                artist = html.unescape(
                    match.group(1)
                )

        match = re.search(
            r'<meta[^>]+property=["\']og:image["\']'
            r'[^>]+content=["\']([^"\']+)',
            text,
            re.I
        )

        if match:
            cover_url = html.unescape(
                match.group(1)
            )

        if title and artist:
            print()
            print(
                "Метаданные получены "
                "из HTML страницы YouTube."
            )

            return {
                "source": "youtube",
                "artist": artist.strip(),
                "title": title.strip(),
                "album": album,
                "duration": duration,
                "cover_url": cover_url,
                "youtube_client": "webpage",
                "age_restricted": False
            }

    return None

# YOUTUBE MUSIC INFO VIA YT-DLP

def parse_ytdlp_youtube_info(
    stdout_text
):
    try:
        data = json.loads(
            stdout_text
        )
    except Exception:
        return None

    artist = (
        data.get("artist")
        or data.get("uploader")
        or data.get("creator")
        or ""
    )

    title = (
        data.get("track")
        or data.get("title")
        or ""
    )

    album = (
        data.get("album")
        or ""
    )

    duration = data.get(
        "duration"
    )

    thumbnails = (
        data.get("thumbnails")
        or []
    )

    cover_url = (
        thumbnails[-1].get("url")
        if thumbnails
        and isinstance(
            thumbnails[-1],
            dict
        )
        else data.get("thumbnail")
    )

    if not artist or not title:
        return None

    return {
        "source": "youtube",
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration,
        "cover_url": cover_url,
        "youtube_client": "default"
    }

def try_youtube_client(
    base_command,
    client
):
    print()
    print(
        "Пробуем дополнительный "
        "клиент YouTube:"
    )

    print(
        client
    )

    command = build_ytdlp_command(
        base_command,
        client=client
    )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

    except (
        subprocess.TimeoutExpired,
        Exception
    ):
        return None, ""

    if (
        result.returncode == 0
        and result.stdout.strip()
    ):
        info = parse_ytdlp_youtube_info(
            result.stdout
        )

        if info:
            info[
                "youtube_client"
            ] = client

            return (
                info,
                ""
            )

    return (
        None,
        (
            result.stderr.strip()
            if result.stderr
            else ""
        )
    )

def get_youtube_music_info(
    url,
    retries=1
):
    global LAST_YOUTUBE_ERROR

    LAST_YOUTUBE_ERROR = ""

    status(
        "Получение информации из YouTube Music..."
    )

    base_command = [
        YTDLP,
        "--dump-single-json",
        "--no-download",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        url
    ]

    last_error = ""

    # 1. Основной yt-dlp.

    for attempt in range(
        1,
        retries + 1
    ):
        try:
            result = subprocess.run(
                base_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )

        except FileNotFoundError:
            LAST_YOUTUBE_ERROR = (
                "Не найден yt-dlp.exe."
            )

            print(
                LAST_YOUTUBE_ERROR
            )

            return None

        except subprocess.TimeoutExpired:
            last_error = (
                "Истекло время ожидания "
                "yt-dlp (60 секунд)."
            )

            if attempt < retries:
                delay = (
                    YOUTUBE_INFO_RETRY_DELAYS[
                        min(
                            attempt - 1,
                            len(
                                YOUTUBE_INFO_RETRY_DELAYS
                            ) - 1
                        )
                    ]
                )

                print(
                    "Повторная попытка "
                    f"через {delay} сек..."
                )

                time.sleep(
                    delay
                )

                continue

            break

        except Exception as e:
            last_error = str(e)
            break

        stderr_text = (
            result.stderr.strip()
            if result.stderr
            else ""
        )

        if (
            result.returncode == 0
            and result.stdout.strip()
        ):
            info = parse_ytdlp_youtube_info(
                result.stdout
            )

            if info:
                LAST_YOUTUBE_ERROR = ""

                info["age_restricted"] = False

                return info

            last_error = (
                stderr_text
                or
                "yt-dlp вернул данные "
                "без необходимых метаданных."
            )

        else:
            last_error = (
                stderr_text
                or
                f"yt-dlp завершился "
                f"с кодом {result.returncode}"
            )

        # Если это age restriction, обычные retries
        # здесь не нужны. Переходим к fallback-клиентам.

        if is_youtube_age_error(
            last_error
        ):
            break

        if attempt < retries:
            delay = (
                YOUTUBE_INFO_RETRY_DELAYS[
                    min(
                        attempt - 1,
                        len(
                            YOUTUBE_INFO_RETRY_DELAYS
                        ) - 1
                    )
                ]
            )

            print(
                "Не удалось получить "
                "информацию о треке."
            )

            print(
                f"Повторная попытка "
                f"{attempt + 1}/{retries} "
                f"через {delay} сек..."
            )

            time.sleep(
                delay
            )

    # 2. Дополнительные YouTube clients.

    age_error_detected = (
        is_youtube_age_error(
            last_error
        )
    )

    if age_error_detected:
        print()
        print(
            "YouTube запросил "
            "подтверждение возраста."
        )

    # 3. НОВЫЙ ГЛАВНЫЙ FALLBACK:
    #    непосредственная страница YouTube Music.

    webpage_info = (
        get_youtube_music_page_info(
            url
        )
    )

    if webpage_info:
        LAST_YOUTUBE_ERROR = ""

        webpage_info["age_restricted"] = (
            age_error_detected
        )

        if age_error_detected:
            print()
            print(
                "YouTube: метаданные получены "
                "через страницу, но ранее было "
                "обнаружено подтверждение возраста."
            )
            print(
                "YouTube: прямое скачивание "
                "через yt-dlp будет запрещено."
            )

        return webpage_info

    # 4. Только теперь считаем получение метаданных
    #    неудачным.
    # Важно: age restriction остаётся только внутренней
    # диагностикой и не будет автоматически записана
    # как причина, если файл потом будет скачан.

    if age_error_detected:
        LAST_YOUTUBE_ERROR = (
            "Не удалось получить "
            "метаданные YouTube Music "
            "даже после fallback-методов."
        )

        print()
        print(
            "Не удалось получить "
            "метаданные трека."
        )

        print(
            "Диагностика:"
        )

        print(
            LAST_YOUTUBE_ERROR
        )

        return None

    LAST_YOUTUBE_ERROR = (
        last_error
        or
        "Не удалось получить "
        "метаданные YouTube Music."
    )

    print()
    print(
        "Не удалось получить "
        "информацию о треке."
    )

    print(
        "Диагностика yt-dlp:"
    )

    print(
        LAST_YOUTUBE_ERROR
    )

    return None

# GENERAL TRACK INFO

def get_track_info(
    url,
    youtube_retries=1
):
    if is_yandex_music_url(url):
        return get_yandex_music_info(url)

    return get_youtube_music_info(
        url,
        retries=youtube_retries
    )

# LRCLIB

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

    if duration is not None:
        try:
            response = requests.get(
                "https://lrclib.net/api/get",
                params={
                    "track_name": clean_tit,
                    "artist_name": clean_art,
                    "duration": int(
                        round(
                            float(duration)
                        )
                    )
                },
                headers={
                    "User-Agent": HEADERS[
                        "User-Agent"
                    ],
                    "Accept": "application/json"
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

                if (
                    synced
                    and synced.strip()
                ):
                    return synced.strip()

                if (
                    plain
                    and plain.strip()
                ):
                    return plain.strip()

        except Exception:
            pass

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
                    "User-Agent": HEADERS[
                        "User-Agent"
                    ],
                    "Accept": "application/json"
                },
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                continue

            results = response.json()

            if (
                not isinstance(
                    results,
                    list
                )
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
                    )
                    or ""
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

                if (
                    synced
                    and synced.strip()
                ):
                    return synced.strip()

                if (
                    plain
                    and plain.strip()
                    and not plain_fallback
                ):
                    plain_fallback = (
                        plain.strip()
                    )

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
            f.write(lyrics)

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

# PLAYLIST

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
                    "https://music.youtube.com/"
                    "watch?v="
                    + track_url
                )

            tracks.append(
                track_url
            )

        if not tracks:
            return None

        return {
            "title": (
                data.get("title")
                or "YouTube Music"
            ),
            "tracks": tracks
        }

    except Exception:
        print(
            "Не удалось получить плейлист."
        )

        return None

# AUDIO VALIDATION

def validate_audio_file(
    filename
):
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

# DIRECT FILE DOWNLOAD

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
        filename
        + ".tmp"
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
                    or
                    "text/plain"
                    in content_type
                    or
                    total < MIN_FILE_SIZE
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

# COVER + ID3

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
            "Обложка для этого трека "
            "не найдена."
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
            io.BytesIO(
                response.content
            )
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

        right = (
            left + min_dim
        )

        bottom = (
            top + min_dim
        )

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
            "Обложка (720x720) "
            "и теги добавлены."
        )

    except Exception as e:
        print(
            "Не удалось добавить "
            "обложку и теги:",
            e
        )

# SoundCloud track search endpoint.
SOUNDCLOUD_SEARCH_URL = (
    "https://api-v2.soundcloud.com/search/tracks"
)












def clean_soundcloud_text(text):
    """
    Удаляет только служебные модификаторы, не являющиеся
    основной частью названия трека.

    Пример:
        Artist - Track (Prod by XXX) [Sped Up]
        ->
        Artist - Track
    """
    text = html.unescape(str(text or ""))
    text = unquote(text)

    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("_", " ")

    # Удаляем конструкции produced by / prod by с последующим именем.
    text = re.sub(
        r"\b(?:prod(?:uced)?\s*by)\b[\s:.-]*"
        r"[^()\[\]{}|/,;]+",
        " ",
        text,
        flags=re.I
    )

    # Удаляем распространённые модификаторы внутри скобок/квадратных скобок.
    modifier_pattern = (
        r"\b(?:remix|slowed|slowed\s*\+\s*reverb|"
        r"sped\s*up|speed\s*up|speedup|nightcore|phonk|"
        r"edit|version|mix|extended(?:\s+mix)?|"
        r"remastered|remaster|rework|bootleg|flip|mashup|"
        r"live|acoustic|instrumental|club|hardstyle|bass)\b"
    )

    for _ in range(3):
        text = re.sub(
            rf"[\(\[\{{][^()\[\]{{}}]*?{modifier_pattern}"
            rf"[^()\[\]{{}}]*?[\)\]\}}]",
            " ",
            text,
            flags=re.I
        )

    # После удаления содержимого могут остаться пустые скобки.
    text = re.sub(r"\(\s*\)|\[\s*\]|\{\s*\}", " ", text)

    # Удаляем одиночные служебные слова, если они остались вне скобок.
    text = re.sub(
        modifier_pattern,
        " ",
        text,
        flags=re.I
    )

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[-:|]+\s*", " ", text)

    return normalize(text)


def soundcloud_query_variants(artist, title):
    """
    Возвращает каскад поисковых запросов:

    1. artist + original title
    2. artist + cleaned title
    3. cleaned title
    4. flexible words
    """
    original_artist = normalize(artist)
    original_title = normalize(title)

    cleaned_artist = clean_soundcloud_text(artist)
    cleaned_title = clean_soundcloud_text(title)

    variants = []

    def add(value):
        value = re.sub(r"\s+", " ", value or "").strip()
        if value and value not in variants:
            variants.append(value)

    # 1. Строго.
    add(f"{original_artist} {original_title}")

    # 2. Исполнитель + очищенное название.
    add(f"{original_artist} {cleaned_title}")

    # Дополнительный вариант с очищенным исполнителем.
    add(f"{cleaned_artist} {cleaned_title}")

    # 3. Только очищенное название.
    add(cleaned_title)

    # 4. Гибкий поиск.
    artist_words = [
        word for word in normalize_words(cleaned_artist)
        if len(word) >= 2
    ]
    title_words = [
        word for word in normalize_words(cleaned_title)
        if len(word) >= 2
    ]

    # Сначала сохраняем наиболее информативные слова.
    flexible_words = []
    for word in artist_words + title_words:
        if word not in flexible_words:
            flexible_words.append(word)

    if flexible_words:
        add(" ".join(flexible_words))

    return variants


def soundcloud_candidate_score(
    found_artist,
    found_title,
    requested_artist,
    requested_title,
    stage
):
    """
    Оценивает SoundCloud-кандидата.

    Важное отличие от старой логики:
    служебные модификаторы не являются автоматическим reject.

    На поздних этапах поиска допускается, что исполнитель может
    находиться внутри title, а title может частично совпадать
    с artist/title в разных полях.
    """
    found_artist = normalize(found_artist)
    found_title = normalize(found_title)

    requested_artist = normalize(requested_artist)
    requested_title = normalize(requested_title)

    cleaned_artist = clean_soundcloud_text(requested_artist)
    cleaned_title = clean_soundcloud_text(requested_title)

    candidate_text = normalize(
        f"{found_artist} {found_title}"
    )

    if not candidate_text:
        return -100000

    artist_words = normalize_words(cleaned_artist)
    title_words = normalize_words(cleaned_title)
    candidate_words = normalize_words(candidate_text)

    if not artist_words or not title_words:
        return -100000

    artist_hits = len(artist_words & candidate_words)
    title_hits = len(title_words & candidate_words)

    artist_ratio = artist_hits / len(artist_words)
    title_ratio = title_hits / len(title_words)

    # Строгие этапы требуют нормального совпадения.
    if stage <= 2:
        if artist_ratio < 0.5 or title_ratio < 0.5:
            return -100000

    # На гибком этапе допускаем отсутствие исполнителя в user.username,
    # если он присутствует непосредственно в title.
    if stage >= 3:
        if title_ratio < 0.5:
            return -100000

    score = 0

    # Основное совпадение названия.
    score += int(title_ratio * 700)

    # Исполнитель.
    score += int(artist_ratio * 500)

    # Точное название.
    if cleaned_title and cleaned_title in candidate_text:
        score += 350

    # Точный исполнитель.
    if cleaned_artist and cleaned_artist in candidate_text:
        score += 300

    # Полное сочетание.
    combined_1 = normalize(f"{cleaned_artist} {cleaned_title}")
    combined_2 = normalize(f"{cleaned_title} {cleaned_artist}")

    if combined_1 and combined_1 in candidate_text:
        score += 450

    if combined_2 and combined_2 in candidate_text:
        score += 400

    # Проверяем отдельно поля SoundCloud.
    if cleaned_artist:
        if cleaned_artist in found_artist:
            score += 250

        if cleaned_artist in found_title:
            score += 180

    if cleaned_title:
        if cleaned_title in found_title:
            score += 300

        if cleaned_title in found_artist:
            score += 80

    # Штраф за слова, не относящиеся к artist/title.
    expected_words = artist_words | title_words
    extra_words = candidate_words - expected_words

    # Служебные слова не должны давать огромный штраф.
    service_words = set()
    for modifier in SOUNDCLOUD_SERVICE_MODIFIERS:
        service_words.update(normalize_words(modifier))

    meaningful_extra_words = extra_words - service_words

    score -= len(meaningful_extra_words) * 12

    # Служебные модификаторы дают небольшой штраф,
    # но не выбрасывают кандидата.
    modifier_hits = 0
    for modifier in SOUNDCLOUD_SERVICE_MODIFIERS:
        modifier_words = normalize_words(modifier)
        if modifier_words and modifier_words.issubset(candidate_words):
            requested_words = normalize_words(
                f"{requested_artist} {requested_title}"
            )
            if not modifier_words.issubset(requested_words):
                modifier_hits += 1

    score -= modifier_hits * 35

    # На строгом этапе наличие лишних модификаторов снижает рейтинг сильнее,
    # но всё ещё не является абсолютным reject.
    if stage == 1:
        score -= modifier_hits * 60

    return score


def candidate_text_score(filename, artist, title):
    """
    Совместимая функция для MP3Party/MP3TM/AudioStart.

    SoundCloud использует отдельную soundcloud_candidate_score(),
    поэтому изменение каскада SoundCloud не ломает остальные источники.
    """
    candidate = normalize(filename)
    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    candidate_words = normalize_words(candidate)
    artist_words = normalize_words(wanted_artist)
    title_words = normalize_words(wanted_title)

    if not artist_words or not title_words:
        return -100000

    artist_ratio = len(artist_words & candidate_words) / len(artist_words)
    title_ratio = len(title_words & candidate_words) / len(title_words)

    if artist_ratio < 0.5 or title_ratio < 0.5:
        return -100000

    score = 0
    score += 500 if artist_ratio == 1 else 300 if artist_ratio >= 0.75 else 100
    score += 500 if title_ratio == 1 else 300 if title_ratio >= 0.75 else 100

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    if wanted_artist + " " + wanted_title in candidate:
        score += 400

    if wanted_title + " " + wanted_artist in candidate:
        score += 350

    score -= len(candidate_words - (artist_words | title_words)) * 15

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

def search_audiostart(
    artist,
    title,
    target_duration=None
):
    try:
        response = requests.get(
            "https://audiostart.net/",
            params={
                "song": f"{artist} {title}"
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
                encoded = link.split(
                    "/getmp3/",
                    1
                )[1]

                decoded = unquote(
                    base64.b64decode(
                        encoded
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )
                )

                score = candidate_text_score(
                    decoded,
                    artist,
                    title
                )

                if score >= 0:
                    if link.startswith("//"):
                        link = (
                            "https:"
                            + link
                        )

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
                    "referer": (
                        "https://audiostart.net/"
                    )
                }

    except Exception:
        pass

    return None

# YT-DLP AUDIO DOWNLOAD

def find_temp_ytdlp_file(
    directory,
    base
):
    files = []

    if not os.path.isdir(
        directory
    ):
        return files

    prefix = (
        base
        + ".yt-dlp.tmp."
    )

    for filename in os.listdir(
        directory
    ):
        if filename.startswith(
            prefix
        ):
            files.append(
                os.path.join(
                    directory,
                    filename
                )
            )

    return files

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

    base_command = [
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

    # 1. Обычный yt-dlp.

    try:
        print("YouTube yt-dlp: subprocess.run() будет запущен.")
        result = subprocess.run(
            base_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180
        )

    except subprocess.TimeoutExpired:
        print(
            "Скачивание yt-dlp "
            "превысило лимит времени."
        )

        return False

    except Exception:
        return False

    if result.returncode != 0:
        return False
        return False

    directory = os.path.dirname(
        filepath
    )

    base = os.path.splitext(
        os.path.basename(filepath)
    )[0]

    files = find_temp_ytdlp_file(
        directory,
        base
    )

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

# FIND AND DOWNLOAD

def find_youtube_fallback_url(
    artist,
    title,
    target_duration
):
    """
    Последний fallback для Яндекс Музыки.

    Ищет подходящий трек на YouTube по метаданным.
    Не скачивает age-restricted результат.
    Проверяет длительность кандидата.
    """

    global LAST_YOUTUBE_ERROR

    print()
    print(
        "YouTube fallback: "
        "поиск по метаданным..."
    )

    query = (
        f"{artist} {title}"
    ).strip()

    if not query:
        print(
            "YouTube fallback: "
            "пустой поисковый запрос."
        )
        return None

    command = [
        YTDLP,
        "--dump-single-json",
        "--flat-playlist",
        "--playlist-end",
        "5",
        "--quiet",
        "--no-warnings",
        "ytsearch5:" + query
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90
        )

    except subprocess.TimeoutExpired:
        print(
            "YouTube fallback: "
            "поиск превысил лимит времени."
        )
        return None

    except Exception as e:
        print(
            "YouTube fallback: "
            f"ошибка поиска: {e}"
        )
        return None

    stderr = (
        result.stderr
        if result.stderr
        else ""
    )

    if result.returncode != 0:
        if is_youtube_age_error(
            stderr
        ):
            LAST_YOUTUBE_ERROR = stderr

            print(
                "YouTube fallback: "
                "YouTube запросил "
                "подтверждение возраста."
            )

        return None

    try:
        data = json.loads(
            result.stdout
        )
    except Exception:
        print(
            "YouTube fallback: "
            "не удалось разобрать "
            "результат поиска."
        )
        return None

    entries = (
        data.get("entries")
        if isinstance(data, dict)
        else None
    )

    if not isinstance(
        entries,
        list
    ):
        return None

    best_url = None
    best_difference = None

    try:
        target = float(
            target_duration
        )
    except Exception:
        target = None

    for entry in entries:
        if not isinstance(
            entry,
            dict
        ):
            continue

        video_id = entry.get(
            "id"
        )

        if not video_id:
            continue

        video_url = (
            entry.get(
                "webpage_url"
            )
            or
            f"https://www.youtube.com/watch?v={video_id}"
        )

        candidate_duration = entry.get(
            "duration"
        )

        try:
            candidate_duration = (
                float(candidate_duration)
                if candidate_duration is not None
                else None
            )
        except Exception:
            candidate_duration = None

        if (
            target is not None
            and candidate_duration is not None
        ):
            difference = abs(
                candidate_duration
                - target
            )

            if difference > 30:
                continue

        else:
            difference = 999999

        if (
            best_url is None
            or difference < best_difference
        ):
            best_url = video_url
            best_difference = difference

    if not best_url:
        print(
            "YouTube fallback: "
            "подходящий кандидат "
            "не найден."
        )
        return None

    print(
        "YouTube fallback: "
        f"кандидат найден: {best_url}"
    )

    # ========================================================
    # ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА ПЕРЕД СКАЧИВАНИЕМ
    # ========================================================

    print(
        "YouTube fallback: "
        "проверка кандидата..."
    )

    check_command = [
        YTDLP,
        "--dump-single-json",
        "--no-download",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        best_url
    ]

    try:
        check = subprocess.run(
            check_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

    except subprocess.TimeoutExpired:
        print(
            "YouTube fallback: "
            "проверка кандидата "
            "превысила лимит времени."
        )
        return None

    except Exception as e:
        print(
            "YouTube fallback: "
            f"ошибка проверки: {e}"
        )
        return None

    if check.returncode != 0:
        error_text = (
            check.stderr
            if check.stderr
            else ""
        )

        if is_youtube_age_error(
            error_text
        ):
            LAST_YOUTUBE_ERROR = (
                error_text
            )

            print(
                "YouTube fallback: "
                "кандидат требует "
                "подтверждения возраста."
            )

            print(
                "YouTube fallback: "
                "скачивание запрещено."
            )

        else:
            print(
                "YouTube fallback: "
                "кандидат не прошёл проверку."
            )

        return None

    try:
        checked_info = json.loads(
            check.stdout
        )
    except Exception:
        checked_info = {}

    checked_duration = (
        checked_info.get(
            "duration"
        )
    )

    if (
        target is not None
        and checked_duration is not None
    ):
        try:
            checked_duration = float(
                checked_duration
            )

            difference = abs(
                checked_duration
                - target
            )

            if difference > 30:
                print(
                    "YouTube fallback: "
                    "длительность кандидата "
                    "не подходит."
                )

                print(
                    "YouTube fallback: "
                    f"разница {difference:.1f} сек."
                )

                return None

        except Exception:
            pass

    print(
        "YouTube fallback: "
        "кандидат прошёл проверку."
    )

    return best_url


def find_and_download_track(
    artist,
    title,
    duration,
    output_folder,
    source_url,
    source,
    youtube_age_restricted=False
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

    # ========================================================
    # 1. SOUNDCLOUD
    # ========================================================

    status(
        "Проверка SoundCloud..."
    )

    result = search_soundcloud(
        artist,
        title,
        duration
    )

    if result:
        soundcloud_candidates = [
            result
        ]

        alternatives = result.get(
            "alternatives",
            []
        )

        if isinstance(
            alternatives,
            list
        ):
            soundcloud_candidates.extend(
                alternatives
            )

        soundcloud_candidates = (
            soundcloud_candidates[:5]
        )

        print(
            "SoundCloud: кандидатов "
            "для проверки: "
            f"{len(soundcloud_candidates)}"
        )

        for candidate_index, candidate_result in enumerate(
            soundcloud_candidates,
            1
        ):
            print()
            print(
                "SoundCloud: проверка кандидата "
                f"{candidate_index}/"
                f"{len(soundcloud_candidates)}"
            )

            print(
                "SoundCloud: score: "
                f"{candidate_result.get('score', 0):.1f}"
            )

            print(
                "SoundCloud: название кандидата: "
                f"{candidate_result.get('title', '')}"
            )

            print(
                "SoundCloud: исполнитель кандидата: "
                f"{candidate_result.get('artist', '')}"
            )

            candidate_url = (
                candidate_result.get(
                    "url"
                )
            )

            if not candidate_url:
                print(
                    "SoundCloud: у кандидата "
                    "отсутствует URL. Пропуск."
                )
                continue

            if download_from_soundcloud(
                candidate_url,
                filepath,
                duration,
                candidate_result.get(
                    "exact_match",
                    False
                )
            ):
                print(
                    "SoundCloud: кандидат "
                    f"{candidate_index} подходит."
                )

                return filepath

            print(
                "SoundCloud: кандидат "
                f"{candidate_index} не подошёл."
            )

        print(
            "SoundCloud: все кандидаты "
            "не подошли."
        )

    # ========================================================
    # 2. MP3PARTY
    # ========================================================

    status(
        "Проверка MP3Party..."
    )

    result = search_mp3party(
        artist,
        title,
        duration
    )

    if result and download_file(
        result["url"],
        filepath,
        result["referer"],
        MP3PARTY_RETRIES
    ):
        return filepath

    # ========================================================
    # 3. MP3TM
    # ========================================================

    status(
        "Проверка MP3TM..."
    )

    result = search_mp3tm(
        artist,
        title,
        duration
    )

    if result and download_file(
        result["url"],
        filepath,
        result["referer"],
        2
    ):
        return filepath

    # ========================================================
    # 4. AUDIOSTART
    # ========================================================

    status(
        "Проверка AudioStart..."
    )

    result = search_audiostart(
        artist,
        title,
        duration
    )

    if result and download_file(
        result["url"],
        filepath,
        result["referer"],
        2
    ):
        return filepath

    # ========================================================
    # 5. YOUTUBE / YT-DLP
    # ========================================================

    print()
    print(
        "YouTube fallback: "
        "проверка финального этапа..."
    )

    print(
        "YouTube fallback: "
        f"source = {source!r}"
    )

    print(
        "YouTube fallback: "
        f"source_url = {source_url!r}"
    )

    print(
        "YouTube fallback: "
        f"youtube_age_restricted = "
        f"{youtube_age_restricted!r}"
    )

    # --------------------------------------------------------
    # Сценарий 1:
    # Исходная ссылка YouTube Music.
    # Если было подтверждение возраста —
    # yt-dlp НЕ запускаем.
    # --------------------------------------------------------

    if (
        source == "youtube"
        and youtube_age_restricted
    ):
        print()
        print(
            "YouTube fallback: "
            "скачивание пропущено."
        )

        print(
            "Причина: исходный YouTube "
            "запросил подтверждение возраста."
        )

    # --------------------------------------------------------
    # Сценарий 2:
    # Обычная YouTube Music без age restriction.
    # Используем исходный URL.
    # --------------------------------------------------------

    elif (
        source == "youtube"
        and source_url
    ):
        print()
        print(
            "YouTube fallback: "
            "возрастное ограничение "
            "не обнаружено."
        )

        print(
            "YouTube fallback: "
            "запуск yt-dlp..."
        )

        if download_with_ytdlp(
            source_url,
            filepath
        ):
            print(
                "YouTube fallback: "
                "аудиофайл успешно получен."
            )

            return filepath

        print(
            "YouTube fallback: "
            "yt-dlp не смог скачать "
            "аудиофайл."
        )

    # --------------------------------------------------------
    # Сценарий 3:
    # Исходная ссылка Яндекс Музыки.
    #
    # Прямое скачивание с Яндекса НЕ используем.
    # Ищем соответствующий трек на YouTube
    # по артисту + названию.
    # --------------------------------------------------------

    elif source == "yandex":
        print()
        print(
            "YouTube fallback: "
            "исходный источник — Яндекс Музыка."
        )

        print(
            "YouTube fallback: "
            "поиск соответствующего трека "
            "на YouTube по метаданным."
        )

        fallback_url = (
            find_youtube_fallback_url(
                artist,
                title,
                duration
            )
        )

        if fallback_url:
            print(
                "YouTube fallback: "
                "запуск yt-dlp..."
            )

            if download_with_ytdlp(
                fallback_url,
                filepath
            ):
                print(
                    "YouTube fallback: "
                    "аудиофайл успешно получен."
                )

                return filepath

            print(
                "YouTube fallback: "
                "yt-dlp не смог скачать "
                "найденный YouTube-трек."
            )

    else:
        print()
        print(
            "YouTube fallback: "
            "не запущен — отсутствует "
            "подходящий источник."
        )

    print(
        "Не удалось скачать "
        "подходящий аудиофайл."
    )

    return None


# SINGLE TRACK

def process_single_track(
    url,
    output_folder,
    youtube_retries=1,
    return_failure=False
):
    info = get_track_info(
        url,
        youtube_retries=youtube_retries
    )

    if not info:
        reason = (
            LAST_YOUTUBE_ERROR
            if LAST_YOUTUBE_ERROR
            else
            "Информация из "
            "YouTube Music не получена."
        )

        failure = {
            "artist": "",
            "title": "",
            "url": url,
            "reason": reason
        }

        if return_failure:
            return (
                False,
                failure
            )

        return False

    source = info.get(
        "source",
        "youtube"
    )

    youtube_age_restricted = bool(
        info.get(
            "age_restricted",
            False
        )
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
        "Обложка: "
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
        source,
        youtube_age_restricted=youtube_age_restricted
    )

    if not filepath:
        failure = {
            "artist": artist,
            "title": title,
            "url": url,
            "reason": (
                "Подходящий аудиофайл "
                "не найден или "
                "не прошёл проверку."
            )
        }

        if return_failure:
            return (
                False,
                failure
            )

        return False

    # Если файл всё-таки скачан, любые предыдущие
    # age restriction ошибки уже не имеют значения.

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

    if return_failure:
        return (
            True,
            None
        )

    return True

# FAILED TRACKS

def save_failed_tracks(
    output_folder,
    failed_tracks
):
    if not failed_tracks:
        return None

    filepath = os.path.join(
        output_folder,
        "failed_tracks.txt"
    )

    try:
        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "НЕСКАЧАННЫЕ ТРЕКИ\n"
            )

            f.write(
                "=" * 60
                + "\n\n"
            )

            for index, track in enumerate(
                failed_tracks,
                1
            ):
                artist = (
                    track.get("artist")
                    or "Неизвестный исполнитель"
                )

                title = (
                    track.get("title")
                    or "Название не определено"
                )

                url = (
                    track.get("url")
                    or ""
                )

                reason = (
                    track.get("reason")
                    or "Причина не определена"
                )

                f.write(
                    f"{index}. "
                    f"{artist} — {title}\n"
                )

                f.write(
                    f"Ссылка: {url}\n"
                )

                f.write(
                    f"Причина: {reason}\n"
                )

                f.write(
                    "\n"
                )

        return filepath

    except Exception as e:
        print()
        print(
            "Не удалось создать "
            "failed_tracks.txt:"
        )

        print(
            e
        )

        return None

# PLAYLIST PROCESSING

def process_playlist(url):
    playlist = get_playlist_tracks(
        url
    )

    if not playlist:
        print(
            "Не удалось получить "
            "плейлист."
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
        f"Название: "
        f"{playlist['title']}"
    )

    print(
        f"Треков: {len(tracks)}"
    )

    downloaded = 0
    failed = 0

    failed_tracks = []

    for index, track_url in enumerate(
        tracks,
        1
    ):
        print()
        print(
            f"Трек {index}/{len(tracks)}"
        )

        success, failure = (
            process_single_track(
                track_url,
                output_folder,
                youtube_retries=YOUTUBE_INFO_RETRIES,
                return_failure=True
            )
        )

        if success:
            downloaded += 1

        else:
            failed += 1

            if failure:
                failed_tracks.append(
                    failure
                )

    failed_file = save_failed_tracks(
        output_folder,
        failed_tracks
    )

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

    if failed_tracks:
        print()
        print(
            "НЕ СКАЧАННЫЕ ТРЕКИ:"
        )

        print()

        for index, track in enumerate(
            failed_tracks,
            1
        ):
            artist = (
                track.get("artist")
                or "Исполнитель не определён"
            )

            title = (
                track.get("title")
                or "Название не определено"
            )

            reason = (
                track.get("reason")
                or "Причина не определена"
            )

            print(
                f"{index}. "
                f"{artist} — {title}"
            )

            print(
                f"   Причина: {reason}"
            )

        if failed_file:
            print()
            print(
                "Полный список со ссылками:"
            )

            print(
                failed_file
            )

    print()
    print(
        f"Папка: {output_folder}"
    )

# URL HELPERS

def is_playlist_url(url):
    return (
        "list=" in url
        and (
            "youtube.com" in url
            or "music.youtube.com" in url
        )
    )

# ENVIRONMENT

def check_environment():
    errors = []

    for path, name in (
        (
            YTDLP,
            "yt-dlp.exe"
        ),
        (
            FFMPEG,
            "ffmpeg.exe"
        ),
        (
            FFPROBE,
            "ffprobe.exe"
        )
    ):
        if not os.path.isfile(
            path
        ):
            errors.append(
                f"Не найден {name}:\n"
                f"{path}"
            )

    if errors:
        print(
            "=" * 60
        )

        print(
            "ОШИБКА СТРУКТУРЫ ПРОЕКТА"
        )

        print(
            "=" * 60
        )

        for error in errors:
            print()
            print(
                error
            )

        return False

    os.makedirs(
        TRACKS_FOLDER,
        exist_ok=True
    )

    return True

def main():
    global DOWNLOAD_LRC

    print(
        "=" * 60
    )

    print(
        "YTMUSIC DOWNLOADER"
    )

    print(
        "=" * 60
    )

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
    print(
        "1 — Да"
    )

    print(
        "2 — Нет"
    )

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
    print(
        "=" * 60
    )

    print(
        "ТРЕК УСПЕШНО СКАЧАН"
        if success
        else
        "ТРЕК НЕ СКАЧАН"
    )

    print(
        "=" * 60
    )

    if success:
        print()
        print(
            "Папка:",
            TRACKS_FOLDER
        )

    input(
        "\nНажмите Enter для выхода..."
    )

if __name__ == "__main__":
    main()
