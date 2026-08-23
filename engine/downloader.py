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
                    "youtube_client": "webpage"
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
                "youtube_client": "webpage"
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

def get_soundcloud_client_id():
    global SOUNDCLOUD_CLIENT_ID_CACHE

    if SOUNDCLOUD_CLIENT_ID_CACHE:
        return SOUNDCLOUD_CLIENT_ID_CACHE

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
                SOUNDCLOUD_CLIENT_ID_CACHE = (
                    match.group(1)
                )

                return SOUNDCLOUD_CLIENT_ID_CACHE

        scripts = re.findall(
            r'<script[^>]+src=["\']'
            r'([^"\']+)["\']',
            text,
            re.I
        )

        for script in scripts:
            if script.startswith("//"):
                script = (
                    "https:"
                    + script
                )

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
                        SOUNDCLOUD_CLIENT_ID_CACHE = (
                            match.group(1)
                        )

                        return (
                            SOUNDCLOUD_CLIENT_ID_CACHE
                        )

            except Exception:
                continue

    except Exception:
        pass

    return None


def normalize_soundcloud_metadata(
    artist,
    title
):
    import re

    raw_artist = str(
        artist or ""
    ).strip()

    raw_title = str(
        title or ""
    ).strip()

    soundcloud_artist = ""
    soundcloud_original_title = raw_title
    soundcloud_clean_title = raw_title

    # --------------------------------------------------------
    # 1. Проверяем, является ли artist служебным описанием.
    # --------------------------------------------------------

    technical_artist = bool(
        re.search(
            r"(?i)"
            r"(?:"
            r"video\s+prod\.?\s+by|"
            r"music\s+by|"
            r"produced\s+by|"
            r"production\s+by|"
            r"prod\.?\s+by|"
            r"beat\s+by"
            r")",
            raw_artist
        )
    )

    # --------------------------------------------------------
    # 2. Разбираем:
    #
    # KIZARU - Если бы я был тобой (Prod.Realitybeats)
    #
    # --------------------------------------------------------

    title_match = re.match(
        r"^\s*(.+?)\s*[-–—:]\s*(.+?)\s*$",
        raw_title
    )

    if title_match:

        possible_artist = (
            title_match.group(1).strip()
        )

        possible_title = (
            title_match.group(2).strip()
        )

        if (
            possible_artist
            and possible_title
        ):

            soundcloud_artist = (
                possible_artist
            )

            soundcloud_clean_title = (
                possible_title
            )

    # --------------------------------------------------------
    # 3. Если title не имеет Artist - Title,
    #    используем нормальный artist.
    # --------------------------------------------------------

    if not soundcloud_artist:

        if not technical_artist:

            soundcloud_artist = (
                raw_artist
            )

    # --------------------------------------------------------
    # 4. Удаляем служебные Prod./Produced/... из названия.
    # --------------------------------------------------------

    soundcloud_clean_title = re.sub(
        r"\s*"
        r"[\(\[]"
        r"\s*"
        r"(?:"
        r"prod\.?|"
        r"produced\s+by|"
        r"production\s+by|"
        r"music\s+by|"
        r"beat\s+by"
        r")"
        r"[^)\]]*"
        r"[\)\]]"
        r"\s*$",
        "",
        soundcloud_clean_title,
        flags=re.I
    ).strip()

    # Дополнительный вариант:
    # Prod.Realitybeats без скобок.
    soundcloud_clean_title = re.sub(
        r"\s+"
        r"prod(?:uced)?\.?"
        r"\s*"
        r"(?:by)?"
        r"\s*"
        r"[\w.@:/-]+"
        r"\s*$",
        "",
        soundcloud_clean_title,
        flags=re.I
    ).strip()

    # --------------------------------------------------------
    # 5. Если artist всё ещё пустой,
    #    пробуем извлечь его из очищенного title.
    # --------------------------------------------------------

    if not soundcloud_artist:

        fallback_match = re.match(
            r"^\s*(.+?)\s*[-–—:]\s*(.+?)\s*$",
            soundcloud_clean_title
        )

        if fallback_match:

            soundcloud_artist = (
                fallback_match.group(1).strip()
            )

            soundcloud_clean_title = (
                fallback_match.group(2).strip()
            )

    # --------------------------------------------------------
    # 6. Финальная очистка пробелов.
    # --------------------------------------------------------

    soundcloud_artist = re.sub(
        r"\s+",
        " ",
        soundcloud_artist
    ).strip()

    soundcloud_original_title = re.sub(
        r"\s+",
        " ",
        soundcloud_original_title
    ).strip()

    soundcloud_clean_title = re.sub(
        r"\s+",
        " ",
        soundcloud_clean_title
    ).strip()

    return (
        soundcloud_artist,
        soundcloud_original_title,
        soundcloud_clean_title
    )



def evaluate_soundcloud_candidate(
    candidate,
    artist,
    title,
    duration
):
    """
    Оценивает SoundCloud-кандидата.

    Главный принцип:

    1. Исполнитель является обязательным условием.
    2. Точное название + точный исполнитель имеют
       абсолютный приоритет.
    3. Кандидат с другим исполнителем не может
       победить правильного исполнителя только
       из-за совпадения названия.
    4. Remix / Ремикс / Slowed / Nightcore /
       Reverb / Edit и другие альтернативные
       версии получают сильный штраф.
    5. Регистр не имеет значения.
    6. feat / ft / featuring НЕ являются
       модификаторами версии.
    """

    if not isinstance(
        candidate,
        dict
    ):
        return None

    candidate_title = str(
        candidate.get("title")
        or candidate.get("name")
        or ""
    ).strip()

    if not candidate_title:
        return None

    candidate_user = candidate.get(
        "user"
    )

    candidate_username = ""

    if isinstance(
        candidate_user,
        dict
    ):
        candidate_username = str(
            candidate_user.get("username")
            or candidate_user.get("permalink")
            or ""
        ).strip()

    candidate_artist = str(
        candidate.get("artist")
        or candidate.get("publisher")
        or candidate.get("metadata_artist")
        or ""
    ).strip()


    # ========================================================
    # НОРМАЛИЗАЦИЯ
    # ========================================================

    def norm(value):

        value = str(
            value or ""
        ).lower()

        value = re.sub(
            r"https?://\S+",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = value.replace(
            "&",
            " and "
        )

        value = re.sub(
            r"[^\w\sа-яё]",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value


    def tokens(value):

        return set(
            norm(value).split()
        )


    requested_artist = norm(
        artist
    )

    requested_title = norm(
        title
    )

    candidate_title_norm = norm(
        candidate_title
    )

    candidate_artist_norm = norm(
        candidate_artist
    )

    candidate_username_norm = norm(
        candidate_username
    )

    if not requested_title:
        return None


    requested_title_tokens = tokens(
        requested_title
    )

    requested_artist_tokens = tokens(
        requested_artist
    )


    # ========================================================
    # ОБРАБОТКА "Artist - Track"
    # ========================================================

    candidate_track_title = (
        candidate_title_norm
    )

    title_artist_part = ""

    separator_match = re.match(
        r"^\s*(.*?)\s+-\s+(.*?)\s*$",
        candidate_title_norm
    )

    if separator_match:

        possible_artist = (
            separator_match.group(
                1
            ).strip()
        )

        possible_title = (
            separator_match.group(
                2
            ).strip()
        )

        if (
            possible_artist
            and possible_title
        ):

            title_artist_part = (
                possible_artist
            )

            candidate_track_title = (
                possible_title
            )


    # ========================================================
    # МОДИФИКАТОРЫ ВЕРСИЙ
    #
    # IGNORECASE означает, что:
    #
    # REMIX
    # Remix
    # remix
    # РЕМИКС
    # Ремикс
    #
    # обрабатываются одинаково.
    # ========================================================

    version_patterns = (

        # English

        r"\bclean\b",
        r"\bcensored\b",
        r"\bexplicit\b",
        r"\buncensored\b",

        r"\bremix\w*\b",
        r"\bremaster\w*\b",
        r"\brework\w*\b",
        r"\bbootleg\w*\b",

        r"\bnightcore\w*\b",
        r"\bslowed\w*\b",

        r"\bsped\s*up\b",
        r"\bspeed\s*up\b",

        r"\bedit\w*\b",
        r"\blive\w*\b",
        r"\bacoustic\w*\b",

        r"\binstrumental\w*\b",
        r"\bmashup\w*\b",
        r"\bflip\w*\b",

        r"\bextended\w*\b",

        r"\bradio\s+edit\b",

        r"\bversion\s*\d+\b",
        r"\bver\.?\s*\d+\b",

        r"\bpart\s*\d+\b",
        r"\bpt\.?\s*\d+\b",

        r"\b\d+\s*(?:mix|edit|version)\b",


        # Russian

        r"\bцензур\w*\b",
        r"\bнецензур\w*\b",

        r"\bремикс\w*\b",
        r"\bремикш\w*\b",

        r"\bремастер\w*\b",
        r"\bремастирован\w*\b",
        r"\bремастирова\w*\b",

        r"\bпереработк\w*\b",
        r"\bбутлег\w*\b",

        r"\bночкор\w*\b",
        r"\bнайткор\w*\b",

        r"\bзамедлен\w*\b",
        r"\bзамедл\w*\b",

        r"\bускорен\w*\b",
        r"\bускор\w*\b",

        r"\bспид\s*ап\b",
        r"\bспид-ап\b",

        r"\bреверб\w*\b",

        r"\bэдит\w*\b",
        r"\bлайв\w*\b",

        r"\bакустическ\w*\b",
        r"\bинструментал\w*\b",

        r"\bмэшап\w*\b",
        r"\bмешап\w*\b",

        r"\bфлип\w*\b",

        r"\bкавер\w*\b",
        r"\bкараоке\w*\b",

        r"\bрасширен\w*\b",

        r"\bрадио\s+верси\w*\b",

        r"\bклубн\w*\b",
    )


    has_version_modifier = any(
        re.search(
            pattern,
            candidate_title,
            flags=re.IGNORECASE
        )
        for pattern
        in version_patterns
    )


    # ========================================================
    # ПРОВЕРКА ИСПОЛНИТЕЛЯ
    #
    # Это КРИТИЧЕСКИ ВАЖНО.
    #
    # Если запрос:
    #
    #     Платина Abu Dhabi Ba6y
    #
    # кандидат:
    #
    #     Dummo - Abu Dhabi Ba6y
    #
    # НЕ проходит.
    #
    # Совпадение названия само по себе
    # недостаточно.
    # ========================================================

    artist_match = False

    exact_artist = False

    if requested_artist:

        # ----------------------------------------------------
        # Точное совпадение username
        # ----------------------------------------------------

        if (
            candidate_username_norm
            == requested_artist
        ):
            artist_match = True
            exact_artist = True


        # ----------------------------------------------------
        # Точное совпадение artist metadata
        # ----------------------------------------------------

        if (
            candidate_artist_norm
            == requested_artist
        ):
            artist_match = True
            exact_artist = True


        # ----------------------------------------------------
        # Несколько исполнителей.
        #
        # Например:
        #
        # requested:
        # Платина OG Buda MAYOT
        #
        # candidate:
        # Платина OG Buda MAYOT Official
        #
        # Такое совпадение разрешаем.
        # ----------------------------------------------------

        if not artist_match:

            sources = []

            if candidate_username_norm:
                sources.append(
                    candidate_username_norm
                )

            if candidate_artist_norm:
                sources.append(
                    candidate_artist_norm
                )

            requested_artist_set = set(
                requested_artist.split()
            )

            for source in sources:

                source_set = set(
                    source.split()
                )

                if (
                    requested_artist_set
                    <= source_set
                ):

                    artist_match = True

                    break


        # ----------------------------------------------------
        # SoundCloud может хранить:
        #
        # Artist - Track
        #
        # непосредственно в title.
        # ----------------------------------------------------

        if (
            not artist_match
            and title_artist_part
        ):

            if (
                title_artist_part
                == requested_artist
            ):

                artist_match = True
                exact_artist = True

            elif (
                requested_artist_tokens
                and requested_artist_tokens
                <= set(
                    title_artist_part.split()
                )
            ):

                artist_match = True


        # ----------------------------------------------------
        # Если исполнитель НЕ совпадает —
        # кандидат полностью отбрасывается.
        # ----------------------------------------------------

        if not artist_match:
            return None


    # ========================================================
    # СОВПАДЕНИЕ НАЗВАНИЯ
    # ========================================================

    exact_title = (
        candidate_track_title
        == requested_title
    )


    candidate_title_tokens = tokens(
        candidate_track_title
    )


    title_intersection = (
        requested_title_tokens
        & candidate_title_tokens
    )


    title_ratio = (
        len(title_intersection)
        / max(
            1,
            len(
                requested_title_tokens
            )
        )
    )


    if (
        title_ratio < 0.50
        and not exact_title
    ):
        return None


    # ========================================================
    # ТОЧНАЯ ИДЕНТИЧНОСТЬ
    #
    # Точный исполнитель
    # +
    # точное название
    # +
    # НЕ remix/version
    #
    # получает абсолютный приоритет.
    # ========================================================

    exact_identity = (
        exact_title
        and (
            exact_artist
            or not requested_artist
        )
        and not has_version_modifier
    )


    # ========================================================
    # ДЛИТЕЛЬНОСТЬ
    # ========================================================

    candidate_duration = candidate.get(
        "duration"
    )

    try:

        if candidate_duration is not None:

            candidate_duration = float(
                candidate_duration
            )

            if candidate_duration > 1000:

                candidate_duration /= 1000.0

    except (
        TypeError,
        ValueError
    ):

        candidate_duration = None


    try:

        requested_duration = (
            float(duration)
            if duration is not None
            else None
        )

    except (
        TypeError,
        ValueError
    ):

        requested_duration = None


    duration_difference = None


    if (
        candidate_duration is not None
        and requested_duration is not None
    ):

        duration_difference = abs(
            candidate_duration
            - requested_duration
        )

        # Для абсолютного точного совпадения
        # не отбрасываем кандидат только
        # из-за ошибочной длительности SC.

        if (
            duration_difference > 10
            and not exact_identity
        ):
            return None


    # ========================================================
    # ШТРАФЫ
    # ========================================================

    version_penalty = 0


    if has_version_modifier:

        version_penalty += 80


    # Дополнительные слова в названии.
    #
    # feat / ft / featuring НЕ штрафуем.
    # Это важно, поскольку дополнительные
    # исполнители могут быть частью оригинального
    # трека.

    extra_tokens = (
        candidate_title_tokens
        - requested_title_tokens
    )


    meaningful_extra_tokens = set(
        extra_tokens
    )


    meaningful_extra_tokens -= {
        "feat",
        "ft",
        "featuring"
    }


    if meaningful_extra_tokens:

        version_penalty += (
            len(
                meaningful_extra_tokens
            )
            * 20
        )


    # ========================================================
    # SCORE
    # ========================================================

    score = 0.0


    score += (
        title_ratio
        * 60
    )


    if exact_title:

        score += 100


    if artist_match:

        score += 60


    if exact_artist:

        score += 100


    if (
        title_artist_part
        == requested_artist
    ):

        score += 50


    if duration_difference is not None:

        if duration_difference <= 1:

            score += 40

        elif duration_difference <= 2:

            score += 32

        elif duration_difference <= 4:

            score += 22

        elif duration_difference <= 6:

            score += 12

        else:

            score += 4


    score -= version_penalty


    # ========================================================
    # АБСОЛЮТНЫЙ ПРИОРИТЕТ
    #
    # Если внутри первых 15 результатов есть:
    #
    #     правильный исполнитель
    #     +
    #     точное название
    #
    # он получает score >= 1000.
    #
    # Поэтому случайный трек с другим исполнителем
    # никогда не сможет его обойти.
    # ========================================================

    if exact_identity:

        score = max(
            score,
            1000.0
        )


    # ========================================================
    # MINIMUM SCORE
    # ========================================================

    if exact_identity:

        minimum_score = 900

    elif (
        exact_title
        and artist_match
    ):

        minimum_score = 100

    elif (
        title_ratio >= 0.80
        and artist_match
    ):

        minimum_score = 65

    elif (
        artist_match
        and title_ratio >= 0.60
    ):

        minimum_score = 65

    else:

        minimum_score = 75


    if score < minimum_score:
        return None


    return {
        "score": score,
        "candidate": candidate,
        "title_ratio": title_ratio,
        "artist_ratio": (
            1.0
            if artist_match
            else 0.0
        ),
        "duration_difference": (
            duration_difference
        ),
        "exact_title": exact_title,
        "exact_artist": exact_artist,
        "exact_identity": exact_identity,
    }

def fetch_soundcloud_results(
    query_str,
    client_id
):
    try:

        response = requests.get(
            "https://api-v2.soundcloud.com/"
            "search/tracks",
            params={
                "q": query_str,
                "client_id": client_id,
                "limit": SOUNDCLOUD_SEARCH_RESULTS
            },
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_SEARCH_TIMEOUT
        )

        print(
            "SoundCloud API: HTTP-код: "
            f"{response.status_code}"
        )

        print(
            "SoundCloud API: размер ответа: "
            f"{len(response.text)} байт"
        )

        if response.status_code != 200:

            print(
                "SoundCloud API: ответ "
                "не 200."
            )

            if response.text:

                print(
                    "SoundCloud API: ответ:"
                )

                print(
                    response.text[:500]
                )

            return []

        try:

            data = response.json()

        except Exception as error:

            print(
                "SoundCloud API: ошибка "
                "JSON: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            print(
                "SoundCloud API: "
                "начало ответа:"
            )

            print(
                response.text[:500]
            )

            return []

        collection = (
            data.get("collection")
            if isinstance(data, dict)
            else None
        )

        if not isinstance(
            collection,
            list
        ):

            print(
                "SoundCloud API: "
                "collection отсутствует "
                "или имеет неверный формат."
            )

            return []

        print(
            "SoundCloud API: "
            f"collection = {len(collection)}"
        )

        return collection

    except Exception as error:

        print(
            "SoundCloud API: исключение: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return []

def search_soundcloud(
    artist,
    title,
    duration=None
):
    """
    Каскадный поиск SoundCloud.

    Этап 1:
        полный исполнитель + очищенное название.

    Этап 2:
        основной исполнитель + название без feat.

    Этап 3:
        полный исполнитель + исходное название.

    Этап 4:
        основной исполнитель + исходное название без feat.

    Каждый этап независим.

    Следующий этап запускается только если
    предыдущий не дал подходящего кандидата.
    """

    if not artist:
        artist = ""

    if not title:
        title = ""

    original_artist = str(
        artist
    ).strip()

    original_title = str(
        title
    ).strip()

    print(
        "SoundCloud: запуск поиска..."
    )

    print(
        "SoundCloud: исполнитель: "
        f"{original_artist}"
    )

    print(
        "SoundCloud: название: "
        f"{original_title}"
    )

    print(
        "SoundCloud: длительность: "
        f"{duration}"
    )

    (
        soundcloud_artist,
        soundcloud_original_title,
        soundcloud_clean_title
    ) = normalize_soundcloud_metadata(
        original_artist,
        original_title
    )

    print(
        "SoundCloud: нормализованный исполнитель: "
        f"{soundcloud_artist}"
    )

    print(
        "SoundCloud: исходное название: "
        f"{soundcloud_original_title}"
    )

    print(
        "SoundCloud: очищенное название: "
        f"{soundcloud_clean_title}"
    )

    if not soundcloud_artist:

        soundcloud_artist = (
            original_artist
        )

    if not soundcloud_clean_title:

        soundcloud_clean_title = (
            original_title
        )

    # --------------------------------------------------------
    # Очистка служебных конструкций
    # --------------------------------------------------------

    def clean_query(value):

        value = str(
            value or ""
        )

        value = re.sub(
            r"https?://\S+",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\b(?:video\s+)?prod(?:uced)?\.?\s+by\b.*",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\bmusic\s+by\b.*",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value

    # --------------------------------------------------------
    # Основной исполнитель
    # --------------------------------------------------------

    def get_primary_artist(value):

        value = str(
            value or ""
        ).strip()

        if not value:

            return ""

        parts = re.split(
            r"\s*,\s*",
            value
        )

        if parts:

            primary = (
                parts[0].strip()
            )

            if primary:

                return primary

        return value

    # --------------------------------------------------------
    # Удаление feat только для fallback
    # --------------------------------------------------------

    def remove_featured_artists(value):

        value = str(
            value or ""
        ).strip()

        if not value:

            return ""

        value = re.sub(
            r"\s*[\(\[]\s*"
            r"(?:feat\.?|ft\.?|featuring)\b"
            r".*?"
            r"[\)\]]\s*$",
            "",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+"
            r"(?:feat\.?|ft\.?|featuring)\b"
            r".*$",
            "",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value

    # --------------------------------------------------------
    # Подготавливаем основные запросы
    # --------------------------------------------------------

    cleaned_query_artist = clean_query(
        soundcloud_artist
    )

    cleaned_query_title = clean_query(
        soundcloud_clean_title
    )

    original_query_artist = clean_query(
        original_artist
    )

    original_query_title = clean_query(
        original_title
    )

    if not cleaned_query_artist:

        cleaned_query_artist = (
            original_query_artist
        )

    if not cleaned_query_title:

        cleaned_query_title = (
            original_query_title
        )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    primary_artist = get_primary_artist(
        cleaned_query_artist
    )

    primary_artist = clean_query(
        primary_artist
    )

    if not primary_artist:

        primary_artist = (
            cleaned_query_artist
        )

    cleaned_base_title = (
        remove_featured_artists(
            cleaned_query_title
        )
    )

    original_base_title = (
        remove_featured_artists(
            original_query_title
        )
    )

    if not cleaned_base_title:

        cleaned_base_title = (
            cleaned_query_title
        )

    if not original_base_title:

        original_base_title = (
            original_query_title
        )

    print(
        "SoundCloud: основной исполнитель "
        "для fallback-поиска: "
        f"{primary_artist}"
    )

    print(
        "SoundCloud: базовое очищенное название "
        "для fallback-поиска: "
        f"{cleaned_base_title}"
    )

    # --------------------------------------------------------
    # КАСКАД
    # --------------------------------------------------------

    search_stages = [

        (
            1,
            "исполнитель + очищенное название",
            (
                f"{cleaned_query_artist} "
                f"{cleaned_query_title}"
            ).strip(),
            cleaned_query_artist,
            cleaned_query_title
        ),

        (
            2,
            "основной исполнитель + название без feat",
            (
                f"{primary_artist} "
                f"{cleaned_base_title}"
            ).strip(),
            primary_artist,
            cleaned_base_title
        ),

        (
            3,
            "исполнитель + исходное название",
            (
                f"{original_query_artist} "
                f"{original_query_title}"
            ).strip(),
            original_query_artist,
            original_query_title
        ),

        (
            4,
            "основной исполнитель + исходное название без feat",
            (
                f"{primary_artist} "
                f"{original_base_title}"
            ).strip(),
            primary_artist,
            original_base_title
        ),
    ]

    # --------------------------------------------------------
    # НЕ удаляем дубли.
    #
    # Одинаковый запрос может использовать разные
    # requested_artist / requested_title.
    # --------------------------------------------------------

    unique_stages = []

    for (
        stage_number,
        stage_name,
        query,
        requested_artist,
        requested_title
    ) in search_stages:

        query = re.sub(
            r"\s+",
            " ",
            str(query or "")
        ).strip()

        requested_artist = re.sub(
            r"\s+",
            " ",
            str(requested_artist or "")
        ).strip()

        requested_title = re.sub(
            r"\s+",
            " ",
            str(requested_title or "")
        ).strip()

        if not query:

            continue

        unique_stages.append(
            (
                stage_number,
                stage_name,
                query,
                requested_artist,
                requested_title
            )
        )

    # --------------------------------------------------------
    # client_id
    # --------------------------------------------------------

    client_id = (
        get_soundcloud_client_id()
    )

    if not client_id:

        print(
            "SoundCloud: "
            "client_id не получен."
        )

        return None

    print(
        "SoundCloud: client_id получен."
    )

    # --------------------------------------------------------
    # ПОЭТАПНЫЙ ПОИСК
    # --------------------------------------------------------

    for (
        stage_number,
        stage_name,
        query,
        requested_artist,
        requested_title
    ) in unique_stages:

        print()
        print(
            "-" * 60
        )

        print(
            "SoundCloud: ЭТАП "
            f"{stage_number}/4"
        )

        print(
            "SoundCloud: режим: "
            f"{stage_name}"
        )

        print(
            "SoundCloud: поисковый запрос: "
            f"{query}"
        )

        print(
            "SoundCloud: максимум результатов: "
            f"{SOUNDCLOUD_SEARCH_RESULTS}"
        )

        print(
            "-" * 60
        )

        try:

            collection = (
                fetch_soundcloud_results(
                    query,
                    client_id
                )
            )

        except Exception as error:

            print(
                "SoundCloud: ошибка запроса: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            continue

        if not isinstance(
            collection,
            list
        ):

            collection = []

        print(
            "SoundCloud: получено результатов: "
            f"{len(collection)}"
        )

        if not collection:

            print(
                "SoundCloud: на этом этапе "
                "результатов нет."
            )

            continue

        # ----------------------------------------------------
        # Оценка только текущего этапа
        # ----------------------------------------------------

        stage_candidates = []

        for candidate in collection:

            result = (
                evaluate_soundcloud_candidate(
                    candidate,
                    requested_artist,
                    requested_title,
                    duration
                )
            )

            if not result:

                continue

            result[
                "search_stage"
            ] = stage_number

            result[
                "search_query"
            ] = query

            stage_candidates.append(
                result
            )

        print(
            "SoundCloud: подходящих кандидатов "
            "на этом этапе: "
            f"{len(stage_candidates)}"
        )

        if not stage_candidates:

            print(
                "SoundCloud: подходящий кандидат "
                "не найден. Переход к следующему этапу."
            )

            continue

        # ----------------------------------------------------
        # Дубликаты внутри текущего этапа
        # ----------------------------------------------------

        unique = {}

        for item in stage_candidates:

            candidate = item[
                "candidate"
            ]

            candidate_id = (
                candidate.get("id")
            )

            if candidate_id is None:

                candidate_id = (
                    candidate.get(
                        "permalink_url"
                    )
                    or candidate.get(
                        "uri"
                    )
                    or candidate.get(
                        "title"
                    )
                )

            previous = unique.get(
                candidate_id
            )

            if (
                previous is None
                or item["score"]
                > previous["score"]
            ):

                unique[
                    candidate_id
                ] = item

        candidates = list(
            unique.values()
        )

        if not candidates:

            print(
                "SoundCloud: после удаления "
                "дубликатов кандидатов не осталось."
            )

            continue

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        best = candidates[0]

        candidate = best[
            "candidate"
        ]

        candidate_title = str(
            candidate.get("title")
            or ""
        ).strip()

        user = candidate.get(
            "user"
        )

        if isinstance(
            user,
            dict
        ):

            candidate_artist = str(
                user.get("username")
                or ""
            ).strip()

        else:

            candidate_artist = ""

        candidate_url = (
            candidate.get(
                "permalink_url"
            )
            or candidate.get(
                "uri"
            )
            or ""
        )

        if not candidate_url:

            print(
                "SoundCloud: у кандидата "
                "отсутствует URL."
            )

            continue

        print()
        print(
            "SoundCloud: КАНДИДАТ НАЙДЕН."
        )

        print(
            "SoundCloud: этап: "
            f"{stage_number}/4"
        )

        print(
            "SoundCloud: запрос: "
            f"{query}"
        )

        print(
            "SoundCloud: score: "
            f"{best['score']:.1f}"
        )

        print(
            "SoundCloud: название кандидата: "
            f"{candidate_title}"
        )

        print(
            "SoundCloud: исполнитель кандидата: "
            f"{candidate_artist}"
        )

        print(
            "SoundCloud: URL: "
            f"{candidate_url}"
        )

        print(
            "SoundCloud: используем результат "
            f"этапа {stage_number}."
        )

        return {
            "url": candidate_url,
            "title": candidate_title,
            "artist": candidate_artist,
            "duration": candidate.get(
                "duration"
            ),
            "score": best["score"],
            "candidate": candidate,
            "search_stage": stage_number,
            "search_query": query,

            # Признак очень точного совпадения.
            #
            # Для exact_match НЕ используются конкретные
            # имена исполнителей или названия треков.
            #
            # Проверяем:
            #   1. высокий score;
            #   2. точное совпадение названия;
            #   3. совпадение исполнителя.
            "exact_match": (
                best["score"] >= 900
                and (
                    best.get("title_ratio", 0)
                    >= 1.0
                )
                and (
                    best.get("artist_ratio", 0)
                    >= 1.0
                )
            ),
        }

    print()

    print(
        "SoundCloud: ни один из "
        "4 этапов поиска не дал "
        "подходящего трека."
    )

    return None



def download_from_soundcloud(
    soundcloud_url,
    filepath,
    target_duration=None,
    exact_match=False
):
    """
    Скачивает трек с SoundCloud через yt-dlp.

    Использует несколько вариантов формата:
    1. bestaudio/best
    2. best
    3. любой доступный аудиоформат

    Не ограничивается только http_mp3/hls_mp3,
    поскольку SoundCloud может отдавать AAC/Opus/HLS.
    """

    if not soundcloud_url:
        return False

    if not filepath:
        return False

    print(
        "Скачивание с SoundCloud..."
    )

    # SAFE SOUNDCLOUD FINAL FILENAME
    # --------------------------------------------------------
    # Защита итогового имени файла от:
    # - переводов строк;
    # - TAB;
    # - управляющих символов;
    # - запрещённых Windows-символов;
    # - пробелов/точек в конце имени.
    # --------------------------------------------------------

    original_filepath = filepath

    filepath_directory = os.path.dirname(
        os.path.abspath(filepath)
    )

    filepath_name = os.path.basename(
        filepath
    )

    filepath_name = (
        str(filepath_name)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )

    # Удаляем управляющие ASCII-символы.
    filepath_name = re.sub(
        r"[\x00-\x1F\x7F]",
        " ",
        filepath_name
    )

    # Удаляем символы, запрещённые Windows.
    filepath_name = re.sub(
        r'[<>:"/\\|?*]',
        "",
        filepath_name
    )

    # Схлопываем повторные пробелы.
    filepath_name = re.sub(
        r"\s+",
        " ",
        filepath_name
    ).strip()

    # Windows не разрешает точку или пробел
    # в конце имени файла.
    filepath_name = filepath_name.rstrip(
        " ."
    )

    if not filepath_name:
        filepath_name = (
            "soundcloud_track.mp3"
        )

    filepath = os.path.join(
        filepath_directory,
        filepath_name
    )

    if filepath != original_filepath:
        print(
            "SoundCloud: итоговое имя файла "
            "очищено от недопустимых символов."
        )

        print(
            "SoundCloud: новое имя:"
        )

        print(
            os.path.basename(filepath)
        )


    output_dir = os.path.dirname(
        os.path.abspath(filepath)
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    base_without_ext = os.path.join(
        output_dir,
        ".soundcloud_temp_download"
    )

    temp_template = (
        base_without_ext
        + ".soundcloud_temp.%(ext)s"
    )

    format_attempts = (
        "bestaudio/best",
        "best",
    )

    def cleanup_temp():

        directory = os.path.dirname(
            os.path.abspath(filepath)
        )

        if not os.path.isdir(directory):
            return

        prefix = os.path.basename(
            base_without_ext
            + ".soundcloud_temp."
        )

        for name in os.listdir(directory):

            if not name.startswith(prefix):
                continue

            path = os.path.join(
                directory,
                name
            )

            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass

    def find_temp_file():

        directory = os.path.dirname(
            os.path.abspath(filepath)
        )

        prefix = os.path.basename(
            base_without_ext
            + ".soundcloud_temp."
        )

        if not os.path.isdir(directory):
            return None

        candidates = []

        for name in os.listdir(directory):

            if not name.startswith(prefix):
                continue

            path = os.path.join(
                directory,
                name
            )

            if not os.path.isfile(path):
                continue

            try:
                size = os.path.getsize(
                    path
                )
            except Exception:
                continue

            if size < 10 * 1024:
                continue

            candidates.append(
                path
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: os.path.getsize(x),
            reverse=True
        )

        return candidates[0]

    def run_ytdlp(format_spec):

        command = [
            YTDLP,
            "--no-playlist",
            "--no-warnings",
            "--newline",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            "--socket-timeout",
            str(SOUNDCLOUD_DOWNLOAD_TIMEOUT),
            "--format",
            format_spec,
            "--output",
            temp_template,
            soundcloud_url,
        ]

        try:

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=(
                    SOUNDCLOUD_DOWNLOAD_TIMEOUT
                    + 30
                )
            )

        except subprocess.TimeoutExpired:

            print(
                "SoundCloud: "
                "превышено время ожидания загрузки."
            )

            return False

        except Exception as error:

            print(
                "SoundCloud: "
                f"ошибка запуска yt-dlp: "
                f"{type(error).__name__}: {error}"
            )

            return False

        output = (
            (process.stdout or "")
            + "\n"
            + (process.stderr or "")
        ).strip()

        if process.returncode != 0:

            if output:

                print(
                    "SoundCloud yt-dlp: "
                    + output[-1200:]
                )

            return False

        return True

    def convert_to_mp3(source):

        if not source:
            return False

        if not os.path.isfile(source):
            return False

        command = [
            FFMPEG,
            "-y",
            "-i",
            source,
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            filepath,
        ]

        try:

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120
            )

        except Exception as error:

            print(
                "SoundCloud: "
                f"ошибка конвертации: "
                f"{type(error).__name__}: {error}"
            )

            return False

        if process.returncode != 0:

            error_text = (
                process.stderr
                or process.stdout
                or ""
            )

            print(
                "SoundCloud FFmpeg: "
                + error_text[-1200:]
            )

            return False

        if not os.path.isfile(filepath):
            return False

        try:

            if os.path.getsize(filepath) < MIN_FILE_SIZE:
                return False

        except Exception:
            return False

        return True

    def validate_duration():

        if (
            target_duration is None
            or not os.path.isfile(filepath)
        ):
            return True

        try:

            command = [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                filepath,
            ]

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )

            if process.returncode != 0:
                return True

            actual_duration = float(
                process.stdout.strip()
            )

            requested_duration = float(
                target_duration
            )

            difference = abs(
                actual_duration
                - requested_duration
            )

            # Обычные кандидаты сохраняют строгий
            # допуск 10 секунд.
            #
            # Для кандидата с exact_match=True
            # разрешаем до EXACT_MATCH_TOLERANCE.
            #
            # Это не отключает проверку длительности.
            # Она по-прежнему работает, но допускает
            # более длинную версию точно совпавшего трека.

            duration_tolerance = (
                EXACT_MATCH_TOLERANCE
                if exact_match
                else SOUNDCLOUD_DURATION_TOLERANCE
            )

            if difference > duration_tolerance:

                print(
                    "SoundCloud: "
                    f"длительность отличается "
                    f"на {difference:.1f} сек."
                )

                print(
                    "SoundCloud: допустимый предел: "
                    f"{duration_tolerance:.1f} сек."
                )

                return False

            if exact_match and difference > SOUNDCLOUD_DURATION_TOLERANCE:

                print(
                    "SoundCloud: точный кандидат "
                    "принят с расширенным допуском "
                    f"({difference:.1f} сек. из "
                    f"{duration_tolerance:.1f} сек.)."
                )

        except Exception:

            return True

        return True

    cleanup_temp()

    # --------------------------------------------------------
    # Попытки загрузки
    # --------------------------------------------------------

    for format_spec in format_attempts:

        print(
            "SoundCloud: попытка загрузки "
            f"({format_spec})..."
        )

        if not run_ytdlp(
            format_spec
        ):
            cleanup_temp()
            continue

        temp_file = find_temp_file()

        if not temp_file:
            cleanup_temp()
            continue

        # ----------------------------------------------------
        # Если yt-dlp уже получил MP3,
        # просто переносим его.
        # ----------------------------------------------------

        extension = os.path.splitext(
            temp_file
        )[1].lower()

        if extension == ".mp3":

            try:

                if os.path.exists(filepath):
                    os.remove(filepath)

                shutil.move(
                    temp_file,
                    filepath
                )

            except Exception:

                cleanup_temp()
                continue

        else:

            # ------------------------------------------------
            # AAC / M4A / OPUS / другой поток
            # конвертируем через FFmpeg.
            # ------------------------------------------------

            if not convert_to_mp3(
                temp_file
            ):

                cleanup_temp()
                continue

            try:
                os.remove(temp_file)
            except Exception:
                pass

        if not os.path.isfile(filepath):

            cleanup_temp()
            continue

        try:

            if os.path.getsize(
                filepath
            ) < MIN_FILE_SIZE:

                cleanup_temp()
                continue

        except Exception:

            cleanup_temp()
            continue

        if not validate_duration():

            try:
                os.remove(filepath)
            except Exception:
                pass

            cleanup_temp()
            continue

        cleanup_temp()

        print(
            "SoundCloud: загрузка успешно завершена."
        )

        return True

    cleanup_temp()

    print(
        "SoundCloud: "
        "не удалось получить аудиопоток."
    )

    return False

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

def search_mp3party(
    artist,
    title,
    target_duration=None
):
    try:
        response = requests.get(
            "https://mp3party.net/search",
            params={
                "q": f"{artist} {title}"
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
            r'<div class="track__user-panel"[^>]*'
            r'data-js-artist-name="([^"]+)"'
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
                "url": (
                    "https://dl2.mp3party.net/"
                    f"download/{song_id}"
                ),
                "referer": (
                    f"https://mp3party.net/music/"
                    f"{song_id}"
                ),
                "text_score": score
            })

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x["text_score"],
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
                    "url": candidate["url"],
                    "referer": candidate["referer"]
                }

    except Exception:
        pass

    return None

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

    # 1. SoundCloud

    status(
        "Проверка SoundCloud..."
    )

    result = search_soundcloud(
        artist,
        title,
        duration
    )

    if result and download_from_soundcloud(
        result["url"],
        filepath,
        duration,
        result.get(
            "exact_match",
            False
        )
    ):
        return filepath

    # 2. MP3Party

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

    # 3. MP3TM

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

    # 4. AudioStart

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

    # 5. YouTube / yt-dlp

    if (
        source == "youtube"
        and source_url
    ):
        if download_with_ytdlp(
            source_url,
            filepath
        ):
            return filepath

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
        source
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
