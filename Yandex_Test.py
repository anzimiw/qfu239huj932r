import requests
import re
import html
import base64
import json
import subprocess
import os
import time
import io


# ============================================================
# ПУТИ ПРОЕКТА
# ============================================================

# downloader.py находится:
#
# YTM_Downloader/
#     engine/
#         downloader.py
#         yandex.py
#
# Поэтому:
# ENGINE_FOLDER = .../YTM_Downloader/engine
# PROJECT_FOLDER = .../YTM_Downloader

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
# YANDEX MUSIC
# ============================================================

# yandex.py должен находиться рядом с downloader.py:
#
# engine/
#     downloader.py
#     yandex.py

try:

    from yandex import get_yandex_info

    YANDEX_AVAILABLE = True

except ImportError:

    YANDEX_AVAILABLE = False

    get_yandex_info = None


# ============================================================
# БИБЛИОТЕКИ
# ============================================================

try:

    from mutagen.mp3 import MP3
    from mutagen.id3 import (
        ID3,
        APIC,
        TIT2,
        TPE1,
        TALB
    )

    MUTAGEN_AVAILABLE = True

except ImportError:

    MUTAGEN_AVAILABLE = False


try:

    from PIL import Image

    PIL_AVAILABLE = True

except ImportError:

    PIL_AVAILABLE = False


# ============================================================
# НАСТРОЙКИ
# ============================================================

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

    "Accept-Language":
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",

    "Connection":
        "keep-alive"
}


TIMEOUT = 20

MIN_FILE_SIZE = 10 * 1024

MP3PARTY_RETRIES = 3

DOWNLOAD_LRC = False

LRCLIB_DELAY = 1.0

DURATION_TOLERANCE = 3.0


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def status(message):

    print()
    print(message)


def normalize(text):

    text = html.unescape(
        str(text)
    )

    try:

        from urllib.parse import unquote

        text = unquote(text)

    except Exception:
        pass

    text = text.replace(
        "–",
        "-"
    )

    text = text.replace(
        "—",
        "-"
    )

    text = text.replace(
        "_",
        " "
    )

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

    # OG / OF Buda

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

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize_words(text):

    return {
        word
        for word in normalize(text).split()
        if word
    }


def clean_filename(text):

    try:

        from urllib.parse import unquote

        text = unquote(text)

    except Exception:
        pass

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

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


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


# ============================================================
# ОПРЕДЕЛЕНИЕ ИСТОЧНИКА
# ============================================================

def is_yandex_url(url):

    if not url:
        return False

    url_lower = url.lower()

    return (
        "music.yandex.ru" in url_lower
        or
        "music.yandex.com" in url_lower
        or
        "yandex.ru" in url_lower
    )


def is_youtube_url(url):

    if not url:
        return False

    url_lower = url.lower()

    return (
        "youtube.com" in url_lower
        or
        "youtu.be" in url_lower
    )


def get_source_name(url):

    if is_yandex_url(url):

        return "ЯНДЕКС МУЗЫКА"

    if is_youtube_url(url):

        return "YOUTUBE MUSIC"

    return "НЕИЗВЕСТНЫЙ ИСТОЧНИК"


# ============================================================
# ОЦЕНКА КАНДИДАТА
# ============================================================

def candidate_text_score(
    filename,
    artist,
    title
):

    candidate = normalize(
        filename
    )

    wanted_artist = normalize(
        artist
    )

    wanted_title = normalize(
        title
    )

    candidate_words = normalize_words(
        candidate
    )

    artist_words = normalize_words(
        wanted_artist
    )

    title_words = normalize_words(
        wanted_title
    )

    if (
        not artist_words
        or
        not title_words
    ):

        return -100000

    artist_matches = (
        artist_words &
        candidate_words
    )

    title_matches = (
        title_words &
        candidate_words
    )

    artist_ratio = (
        len(artist_matches) /
        len(artist_words)
    )

    title_ratio = (
        len(title_matches) /
        len(title_words)
    )

    if artist_ratio < 0.5:
        return -100000

    if title_ratio < 0.5:
        return -100000

    score = 0

    # --------------------------------------------------------
    # ИСПОЛНИТЕЛЬ
    # --------------------------------------------------------

    if artist_ratio == 1:

        score += 500

    elif artist_ratio >= 0.75:

        score += 300

    else:

        score += 100

    # --------------------------------------------------------
    # НАЗВАНИЕ
    # --------------------------------------------------------

    if title_ratio == 1:

        score += 500

    elif title_ratio >= 0.75:

        score += 300

    else:

        score += 100

    # --------------------------------------------------------
    # ТОЧНЫЕ СОВПАДЕНИЯ
    # --------------------------------------------------------

    if wanted_title in candidate:

        score += 250

    if wanted_artist in candidate:

        score += 250

    exact_1 = (
        wanted_artist
        + " "
        + wanted_title
    )

    exact_2 = (
        wanted_title
        + " "
        + wanted_artist
    )

    if exact_1 in candidate:

        score += 400

    if exact_2 in candidate:

        score += 350

    # --------------------------------------------------------
    # ЛИШНИЕ СЛОВА
    # --------------------------------------------------------

    requested_words = (
        artist_words |
        title_words
    )

    extra_words = (
        candidate_words -
        requested_words
    )

    score -= (
        len(extra_words) *
        15
    )

    # --------------------------------------------------------
    # НЕЖЕЛАТЕЛЬНЫЕ ВЕРСИИ
    # --------------------------------------------------------

    modifiers = {

        "nightcore",
        "remix",
        "slowed",
        "slowed+reverb",
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
    }

    requested = normalize(
        artist
        + " "
        + title
    )

    for modifier in modifiers:

        if (
            modifier in candidate
            and
            modifier not in requested
        ):

            score -= 150

    return score


def duration_score(
    candidate_duration,
    target_duration
):

    if (
        candidate_duration is None
        or
        target_duration is None
    ):

        return 0

    difference = abs(
        candidate_duration -
        target_duration
    )

    if difference <= 1:

        return 500

    if difference <= 2:

        return 350

    if difference <= DURATION_TOLERANCE:

        return 200

    if difference <= 5:

        return 50

    return -500


def is_duration_acceptable(
    candidate_duration,
    target_duration
):

    if (
        candidate_duration is None
        or
        target_duration is None
    ):

        return True

    return (
        abs(
            candidate_duration -
            target_duration
        )
        <= DURATION_TOLERANCE
    )


# ============================================================
# ОБЛОЖКА И ТЕГИ
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
            "\n[ОШИБКА] mutagen не установлен."
        )

        return

    if not cover_url:

        print(
            "\n[ВНИМАНИЕ] "
            "У трека отсутствует "
            "ссылка на обложку."
        )

        return

    if not PIL_AVAILABLE:

        print(
            "\n[ОШИБКА] Pillow не установлен."
        )

        return

    status(
        "Вшивание обложки и тегов..."
    )

    try:

        hi_res_url = cover_url

        # ----------------------------------------------------
        # YouTube Music
        # ----------------------------------------------------

        if (
            "googleusercontent.com"
            in cover_url
        ):

            hi_res_url = re.sub(
                r"=w\d+-h\d+.*$",
                "=w1200-h1200-l90-rj",
                cover_url
            )

        # ----------------------------------------------------
        # Яндекс Музыка
        #
        # yandex.py уже возвращает
        # m1000x1000.
        # Поэтому URL не меняем.
        # ----------------------------------------------------

        response = requests.get(
            hi_res_url,
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
                "Не удалось скачать обложку "
                f"(код ответа: "
                f"{response.status_code})"
            )

            return

        img = Image.open(
            io.BytesIO(
                response.content
            )
        )

        # ----------------------------------------------------
        # Делаем квадратную обложку.
        #
        # Если источник уже квадратный,
        # ничего не обрезаем.
        #
        # Если нет — берём центральный квадрат.
        # ----------------------------------------------------

        width, height = img.size

        if width != height:

            side = min(
                width,
                height
            )

            left = (
                width -
                side
            ) // 2

            top = (
                height -
                side
            ) // 2

            right = (
                left +
                side
            )

            bottom = (
                top +
                side
            )

            img = img.crop(
                (
                    left,
                    top,
                    right,
                    bottom
                )
            )

        if img.mode != "RGB":

            img = img.convert(
                "RGB"
            )

        output = io.BytesIO()

        img.save(
            output,
            format="JPEG",
            quality=95
        )

        cover_bytes = (
            output.getvalue()
        )

        # ----------------------------------------------------
        # Теги
        # ----------------------------------------------------

        try:

            tags = ID3(
                mp3_filepath
            )

            tags.delete(
                mp3_filepath
            )

        except Exception:
            pass

        tags = ID3()

        tags.add(
            TIT2(
                encoding=3,
                text=[
                    str(title)
                ]
            )
        )

        tags.add(
            TPE1(
                encoding=3,
                text=[
                    str(artist)
                ]
            )
        )

        if album:

            tags.add(
                TALB(
                    encoding=3,
                    text=[
                        str(album)
                    ]
                )
            )

        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=cover_bytes
            )
        )

        tags.save(
            mp3_filepath,
            v2_version=3
        )

        print(
            "Обложка и теги успешно вшиты."
        )

    except Exception as e:

        print(
            "Ошибка при прикреплении "
            "обложки:",
            e
        )


# ============================================================
# YOUTUBE MUSIC
# ============================================================

def get_youtube_music_info(url):

    status(
        "Получение информации "
        "из YouTube Music..."
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
                "\nНе удалось получить "
                "информацию о треке."
            )

            return None

        data = json.loads(
            result.stdout
        )

        artist = (
            data.get("artist")
            or
            data.get("uploader")
            or
            data.get("creator")
        )

        title = (
            data.get("track")
            or
            data.get("title")
        )

        album = (
            data.get("album")
            or
            ""
        )

        duration = data.get(
            "duration"
        )

        cover_url = None

        thumbnails = data.get(
            "thumbnails"
        )

        if thumbnails:

            cover_url = (
                thumbnails[-1].get(
                    "url"
                )
            )

        else:

            cover_url = data.get(
                "thumbnail"
            )

        if (
            not artist
            or
            not title
        ):

            print(
                "\nНе удалось определить "
                "исполнителя или название."
            )

            return None

        return {

            "source":
                "youtube",

            "artist":
                artist,

            "title":
                title,

            "album":
                album,

            "duration":
                duration,

            "cover_url":
                cover_url
        }

    except FileNotFoundError:

        print(
            "\nОШИБКА: yt-dlp.exe "
            "не найден."
        )

        print(
            "Ожидаемый путь:",
            YTDLP
        )

        return None

    except json.JSONDecodeError:

        print(
            "\nОШИБКА: yt-dlp не вернул "
            "корректные данные."
        )

        return None

    except subprocess.TimeoutExpired:

        print(
            "\nОШИБКА: получение данных "
            "заняло слишком много времени."
        )

        return None

    except Exception as e:

        print(
            "\nОШИБКА:",
            e
        )

        return None


# ============================================================
# YANDEX MUSIC
# ============================================================

def get_yandex_music_info(url):

    print()
    print("=" * 60)
    print(
        "ПОЛУЧЕНИЕ ИНФОРМАЦИИ "
        "ИЗ ЯНДЕКС МУЗЫКИ"
    )
    print("=" * 60)

    if not YANDEX_AVAILABLE:

        print()
        print(
            "[ОШИБКА] Не удалось загрузить yandex.py."
        )

        print()
        print(
            "Проверь, что файл находится здесь:"
        )

        print(
            os.path.join(
                ENGINE_FOLDER,
                "yandex.py"
            )
        )

        return None

    try:

        result = get_yandex_info(
            url
        )

        if not result:

            print()
            print(
                "Яндекс Музыка "
                "не вернула данные."
            )

            return None

        # ----------------------------------------------------
        # Приводим результат yandex.py
        # к единому формату downloader.py.
        # ----------------------------------------------------

        artist = (
            result.get("artist")
            or
            ""
        )

        title = (
            result.get("title")
            or
            ""
        )

        album = (
            result.get("album")
            or
            ""
        )

        duration = result.get(
            "duration"
        )

        cover_url = result.get(
            "cover_url"
        )

        if (
            not artist
            or
            not title
        ):

            print()
            print(
                "Яндекс Музыка "
                "не определила исполнителя "
                "или название."
            )

            return None

        print()
        print(
            "Метаданные Яндекс Музыки "
            "получены."
        )

        return {

            "source":
                "yandex",

            "artist":
                artist,

            "title":
                title,

            "album":
                album,

            "duration":
                duration,

            "cover_url":
                cover_url
        }

    except Exception as e:

        print()
        print(
            "Ошибка получения данных "
            "из Яндекс Музыки:"
        )

        print(
            e
        )

        return None


# ============================================================
# ЕДИНЫЙ ПОЛУЧАТЕЛЬ МЕТАДАННЫХ
# ============================================================

def get_track_info(url):

    if is_yandex_url(url):

        return get_yandex_music_info(
            url
        )

    if is_youtube_url(url):

        return get_youtube_music_info(
            url
        )

    print()
    print(
        "Неизвестный источник ссылки."
    )

    print()
    print(
        "Поддерживаются:"
    )

    print(
        "• YouTube Music"
    )

    print(
        "• Яндекс Музыка"
    )

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

    status(
        "Поиск синхронизированного текста..."
    )

    if duration is None:

        print(
            "Недостаточно данных "
            "для точного поиска текста."
        )

        return None

    try:

        params = {

            "track_name":
                title,

            "artist_name":
                artist,

            "album_name":
                album or "",

            "duration":
                int(
                    round(
                        float(duration)
                    )
                )
        }

        response = requests.get(

            "https://lrclib.net/api/get",

            params=params,

            headers={

                "User-Agent":
                    HEADERS["User-Agent"],

                "Accept":
                    "application/json"
            },

            timeout=TIMEOUT
        )

        if response.status_code != 200:

            print(
                "Синхронизированный "
                "текст не найден."
            )

            return None

        lyrics = response.json().get(
            "syncedLyrics"
        )

        if not lyrics:

            print(
                "Синхронизированный "
                "текст не найден."
            )

            return None

        return lyrics.strip()

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

    lrc_filepath = (

        os.path.splitext(
            mp3_filepath
        )[0]

        + ".lrc"
    )

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

        print(
            "\nНе удалось сохранить LRC:",
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

    status(
        "Сохранение LRC..."
    )

    return save_lrc(
        mp3_filepath,
        lyrics
    )


# ============================================================
# PLAYLIST YOUTUBE MUSIC
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
                "\nНе удалось получить плейлист."
            )

            return None

        data = json.loads(
            result.stdout
        )

        entries = data.get(
            "entries"
        ) or []

        tracks = []

        for entry in entries:

            if not entry:

                continue

            track_url = (

                entry.get(
                    "webpage_url"
                )

                or

                entry.get(
                    "original_url"
                )

                or

                entry.get(
                    "url"
                )
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

            "title":
                data.get(
                    "title"
                )
                or
                "YouTube Music",

            "tracks":
                tracks
        }

    except Exception as e:

        print(
            "\nОшибка получения "
            "плейлиста:",
            e
        )

        return None


# ============================================================
# FFMPEG / FFPROBE
# ============================================================

def validate_audio_file(
    filename
):

    if not os.path.exists(
        filename
    ):

        return False

    try:

        if (
            os.path.getsize(
                filename
            )
            <
            MIN_FILE_SIZE
        ):

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

        data = json.loads(
            result.stdout
        )

        duration = (

            data.get(
                "format",
                {}
            )
            .get(
                "duration"
            )
        )

        if not duration:

            return False

        return (
            float(duration)
            > 0
        )

    except Exception:

        return False


def get_duration(url):

    try:

        command = [

            FFPROBE,

            "-v",
            "error",

            "-show_entries",
            "format=duration",

            "-of",
            "default="
            "noprint_wrappers=1:"
            "nokey=1",

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

        value = (
            result.stdout.strip()
        )

        return (

            float(value)

            if value

            else None
        )

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

    status(
        "Скачивание аудиофайла..."
    )

    temp_filename = (
        filename +
        ".tmp"
    )

    for attempt in range(
        1,
        retries + 1
    ):

        try:

            if os.path.exists(
                temp_filename
            ):

                try:

                    os.remove(
                        temp_filename
                    )

                except Exception:

                    pass

            headers = dict(
                HEADERS
            )

            headers["Accept"] = (
                "audio/mpeg,"
                "audio/*;q=0.9,"
                "*/*;q=0.8"
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

                ) as file:

                    for chunk in response.iter_content(

                        chunk_size=262144

                    ):

                        if chunk:

                            file.write(
                                chunk
                            )

                            total += len(
                                chunk
                            )

                print()

                print(
                    "Получено:",
                    round(
                        total /
                        1024 /
                        1024,
                        2
                    ),
                    "МБ"
                )

                if (
                    "text/html"
                    in content_type
                    or
                    "text/plain"
                    in content_type
                ):

                    if attempt < retries:

                        time.sleep(1)

                        continue

                    return False

                if total < MIN_FILE_SIZE:

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

                    try:

                        os.remove(
                            filename
                        )

                    except Exception:

                        pass

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

        candidates = []

        for (

            found_artist,
            song_id,
            found_title,
            found_url

        ) in pattern.findall(text):

            filename = (

                found_artist
                + " - "
                + found_title
            )

            text_score = candidate_text_score(

                filename,

                artist,

                title
            )

            if text_score < 0:

                continue

            page_url = (

                "https://mp3party.net/music/"
                + song_id
            )

            download_url = (

                "https://dl2.mp3party.net/"
                "download/"
                + song_id
            )

            candidates.append({

                "url":
                    download_url,

                "referer":
                    page_url,

                "text_score":
                    text_score,

                "duration":
                    None,

                "final_score":
                    text_score
            })

        if not candidates:

            return None

        candidates.sort(

            key=lambda x:
                x["text_score"],

            reverse=True
        )

        candidates = candidates[:10]

        for candidate in candidates:

            if target_duration is None:

                continue

            candidate_duration = (

                get_duration(
                    candidate["url"]
                )
            )

            candidate["duration"] = (
                candidate_duration
            )

            if candidate_duration is None:

                candidate["final_score"] -= 100

                continue

            candidate["final_score"] += (

                duration_score(

                    candidate_duration,

                    target_duration
                )
            )

            if not is_duration_acceptable(

                candidate_duration,

                target_duration

            ):

                candidate["final_score"] -= 1000

        valid = [

            candidate

            for candidate in candidates

            if candidate["final_score"] > 0
        ]

        if not valid:

            return None

        valid.sort(

            key=lambda x:
                x["final_score"],

            reverse=True
        )

        return {

            "url":
                valid[0]["url"],

            "referer":
                valid[0]["referer"]
        }

    except Exception:

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

        text = html.unescape(
            response.text
        )

        links = re.findall(

            r'https?://[^"\']+\.mp3'
            r'(?:\?[^"\']*)?',

            text,

            re.I
        )

        links = list(
            dict.fromkeys(
                links
            )
        )

        candidates = []

        for link in links:

            filename = clean_filename(

                link.split(
                    "/"
                )[-1]
            )

            score = candidate_text_score(

                filename,

                artist,

                title
            )

            if score < 0:

                continue

            candidates.append({

                "url":
                    link,

                "filename":
                    filename,

                "text_score":
                    score,

                "duration":
                    None,

                "final_score":
                    score
            })

        if not candidates:

            return None

        candidates.sort(

            key=lambda x:
                x["text_score"],

            reverse=True
        )

        for candidate in candidates:

            if target_duration is None:

                continue

            candidate_duration = (

                get_duration(
                    candidate["url"]
                )
            )

            candidate["duration"] = (
                candidate_duration
            )

            if candidate_duration is None:

                continue

            candidate["final_score"] += (

                duration_score(

                    candidate_duration,

                    target_duration
                )
            )

            if not is_duration_acceptable(

                candidate_duration,

                target_duration

            ):

                candidate["final_score"] -= 1000

        valid = [

            candidate

            for candidate in candidates

            if candidate["final_score"] > 0
        ]

        if not valid:

            return None

        valid.sort(

            key=lambda x:
                x["final_score"],

            reverse=True
        )

        return {

            "url":
                valid[0]["url"],

            "referer":
                page_url
        }

    except Exception:

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

        text = html.unescape(
            response.text
        )

        links = re.findall(

            r'href=["\']'
            r'([^"\']*?/getmp3/[^"\']+)'
            r'["\']',

            text,

            re.I
        )

        links = list(
            dict.fromkeys(
                links
            )
        )

        candidates = []

        for link in links:

            try:

                encoded = link.split(
                    "/getmp3/",
                    1
                )[1]

                decoded = (

                    base64.b64decode(
                        encoded
                    )
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                )

                from urllib.parse import unquote

                decoded = unquote(
                    decoded
                )

                score = candidate_text_score(

                    decoded,

                    artist,

                    title
                )

                if score < 0:

                    continue

                if link.startswith(
                    "//"
                ):

                    link = (
                        "https:"
                        + link
                    )

                candidates.append({

                    "url":
                        link,

                    "filename":
                        decoded,

                    "text_score":
                        score,

                    "duration":
                        None,

                    "final_score":
                        score
                })

            except Exception:

                continue

        if not candidates:

            return None

        candidates.sort(

            key=lambda x:
                x["text_score"],

            reverse=True
        )

        for candidate in candidates:

            if target_duration is None:

                continue

            candidate_duration = (

                get_duration(
                    candidate["url"]
                )
            )

            candidate["duration"] = (
                candidate_duration
            )

            if candidate_duration is None:

                continue

            candidate["final_score"] += (

                duration_score(

                    candidate_duration,

                    target_duration
                )
            )

            if not is_duration_acceptable(

                candidate_duration,

                target_duration

            ):

                candidate["final_score"] -= 1000

        valid = [

            candidate

            for candidate in candidates

            if candidate["final_score"] > 0
        ]

        if not valid:

            return None

        valid.sort(

            key=lambda x:
                x["final_score"],

            reverse=True
        )

        return {

            "url":
                valid[0]["url"],

            "referer":
                "https://audiostart.net/"
        }

    except Exception:

        return None


# ============================================================
# РЕЗЕРВНЫЙ YT-DLP
# ============================================================

def download_with_ytdlp(
    youtube_url,
    filepath
):

    status(
        "Резервное скачивание..."
    )

    temp_template = (

        os.path.splitext(
            filepath
        )[0]

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

            os.path.basename(
                filepath
            )
        )[0]

        possible_files = []

        for filename in os.listdir(
            directory
        ):

            if filename.startswith(

                base
                +
                ".yt-dlp.tmp."
            ):

                possible_files.append(

                    os.path.join(

                        directory,

                        filename
                    )
                )

        if not possible_files:

            return False

        source_file = (
            possible_files[0]
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
            "Резервный файл готов."
        )

        return True

    except Exception:

        return False


# ============================================================
# ПОИСК И СКАЧИВАНИЕ
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

    print(
        "ПОИСК АУДИО"
    )

    print("=" * 60)

    print()

    print(
        "Источник метаданных:",
        source
    )

    print(
        "Исполнитель:",
        artist
    )

    print(
        "Название:",
        title
    )

    print(
        "Длительность:",
        format_duration(
            duration
        )
    )

    print()
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
    # 1. MP3PARTY
    # --------------------------------------------------------

    print()
    print(
        "1. ПОИСК НА MP3PARTY"
    )

    print()

    print(
        "Исполнитель:",
        artist
    )

    print(
        "Название:",
        title
    )

    print(
        "Длительность:",
        format_duration(
            duration
        )
    )

    result = search_mp3party(

        artist,

        title,

        duration
    )

    if result:

        print()
        print(
            "MP3Party: найден подходящий "
            "кандидат."
        )

        if download_file(

            result["url"],

            filepath,

            referer=result["referer"],

            retries=MP3PARTY_RETRIES

        ):

            return filepath

    else:

        print()
        print(
            "MP3Party: подходящий кандидат "
            "не найден."
        )

    # --------------------------------------------------------
    # 2. MP3TM
    # --------------------------------------------------------

    print()
    print(
        "=" * 60
    )

    print(
        "2. ПОИСК НА MP3TM"
    )

    print()

    result = search_mp3tm(

        artist,

        title,

        duration
    )

    if result:

        print(
            "MP3TM: найден подходящий "
            "кандидат."
        )

        if download_file(

            result["url"],

            filepath,

            referer=result["referer"],

            retries=2

        ):

            return filepath

    else:

        print(
            "MP3TM: подходящий кандидат "
            "не найден."
        )

    # --------------------------------------------------------
    # 3. AUDIOSTART
    # --------------------------------------------------------

    print()
    print(
        "=" * 60
    )

    print(
        "3. ПОИСК НА AUDIOSTART"
    )

    print()

    result = search_audiostart(

        artist,

        title,

        duration
    )

    if result:

        print(
            "AudioStart: найден подходящий "
            "кандидат."
        )

        if download_file(

            result["url"],

            filepath,

            referer=result["referer"],

            retries=2

        ):

            return filepath

    else:

        print(
            "AudioStart: подходящий "
            "кандидат не найден."
        )

    # --------------------------------------------------------
    # 4. РЕЗЕРВНЫЙ YT-DLP
    #
    # Только для YouTube.
    # --------------------------------------------------------

    if source == "youtube":

        print()
        print(
            "=" * 60
        )

        print(
            "4. РЕЗЕРВНЫЙ YT-DLP"
        )

        print()

        if download_with_ytdlp(

            source_url,

            filepath

        ):

            return filepath

    else:

        print()
        print(
            "Резервный yt-dlp "
            "для Яндекс Музыки "
            "не используется."
        )

    print()
    print(
        "Не удалось скачать "
        "подходящий аудиофайл."
    )

    return None


# ============================================================
# ОДИНОЧНЫЙ ТРЕК
# ============================================================

def process_single_track(

    url,

    output_folder
):

    # --------------------------------------------------------
    # Определяем источник
    # --------------------------------------------------------

    if is_yandex_url(url):

        source = "yandex"

    elif is_youtube_url(url):

        source = "youtube"

    else:

        print()
        print(
            "Ссылка не распознана."
        )

        return False

    print()
    print("=" * 60)

    print(
        "ИСТОЧНИК:",
        get_source_name(url)
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Получаем метаданные
    # --------------------------------------------------------

    info = get_track_info(
        url
    )

    if not info:

        return False

    artist = (
        info["artist"]
    )

    title = (
        info["title"]
    )

    album = (
        info.get("album")
        or
        ""
    )

    duration = info.get(
        "duration"
    )

    cover_url = info.get(
        "cover_url"
    )

    # --------------------------------------------------------
    # Информация
    # --------------------------------------------------------

    print()
    print("=" * 50)

    print(
        "ИНФОРМАЦИЯ О ТРЕКЕ"
    )

    print("=" * 50)

    print()

    print(
        "Источник:",
        source
    )

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
        format_duration(
            duration
        )
    )

    print(
        "Обложка:",
        "НАЙДЕНА"
        if cover_url
        else
        "НЕТ"
    )

    # --------------------------------------------------------
    # Поиск и скачивание аудио
    # --------------------------------------------------------

    filepath = find_and_download_track(

        artist,

        title,

        duration,

        output_folder,

        url,

        source
    )

    if not filepath:

        return False

    # --------------------------------------------------------
    # Обложка + ID3
    # --------------------------------------------------------

    embed_cover(

        filepath,

        cover_url,

        artist,

        title,

        album
    )

    # --------------------------------------------------------
    # LRC
    # --------------------------------------------------------

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
# PLAYLIST
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

    output_folder = os.path.join(

        PROJECT_FOLDER,

        playlist_title
    )

    os.makedirs(

        output_folder,

        exist_ok=True
    )

    tracks = playlist[
        "tracks"
    ]

    print()
    print("=" * 60)

    print(
        "ПЛЕЙЛИСТ"
    )

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

        if process_single_track(

            track_url,

            output_folder

        ):

            downloaded += 1

        else:

            failed += 1

    print()
    print()
    print("=" * 60)

    print(
        "ПЛЕЙЛИСТ ЗАВЕРШЁН"
    )

    print("=" * 60)

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
# URL
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
# ПРОВЕРКА СТРУКТУРЫ
# ============================================================

def check_environment():

    errors = []

    if not os.path.isfile(
        YTDLP
    ):

        errors.append(

            "Не найден yt-dlp.exe:\n"
            + YTDLP
        )

    if not os.path.isfile(
        FFMPEG
    ):

        errors.append(

            "Не найден ffmpeg.exe:\n"
            + FFMPEG
        )

    if not os.path.isfile(
        FFPROBE
    ):

        errors.append(

            "Не найден ffprobe.exe:\n"
            + FFPROBE
        )

    if not YANDEX_AVAILABLE:

        errors.append(

            "Не удалось импортировать "
            "yandex.py.\n"
            "Файл должен находиться здесь:\n"
            + os.path.join(
                ENGINE_FOLDER,
                "yandex.py"
            )
        )

    if errors:

        print()
        print("=" * 60)

        print(
            "ОШИБКА СТРУКТУРЫ ПРОЕКТА"
        )

        print("=" * 60)

        for error in errors:

            print()
            print(error)

        print()
        print(
            "Ожидаемая структура:"
        )

        print()

        print(
            "YTM_Downloader\\"
        )

        print(
            "├── start.bat"
        )

        print(
            "├── tracks\\"
        )

        print(
            "└── engine\\"
        )

        print(
            "    ├── downloader.py"
        )

        print(
            "    ├── yandex.py"
        )

        print(
            "    ├── yt-dlp.exe"
        )

        print(
            "    └── ffmpeg\\"
        )

        print(
            "        └── bin\\"
        )

        print(
            "            ├── ffmpeg.exe"
        )

        print(
            "            └── ffprobe.exe"
        )

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

    print(
        "YTMUSIC DOWNLOADER"
    )

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

        print()

        print(
            "Введите 1 или 2."
        )

    print()

    url = input(

        "Ссылка на трек или "
        "плейлист YouTube Music / "
        "Яндекс Музыки: "

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

    # --------------------------------------------------------
    # YouTube Music playlist
    # --------------------------------------------------------

    if is_playlist_url(
        url
    ):

        process_playlist(
            url
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # Одиночный трек
    # --------------------------------------------------------

    success = process_single_track(

        url,

        TRACKS_FOLDER
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
            TRACKS_FOLDER
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
