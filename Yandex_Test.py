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

    return re.sub(
        r'[<>:"/\\|?*]',
        "",
        str(text)
    ).strip()


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    try:
        seconds = int(round(float(seconds)))

    except Exception:
        return "??:??"

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )


# ============================================================
# ОЦЕНКА КАНДИДАТА
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
    artist_words = normalize_words(wanted_artist)
    title_words = normalize_words(wanted_title)

    if not artist_words or not title_words:
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

    if artist_ratio == 1:
        score += 500

    elif artist_ratio >= 0.75:
        score += 300

    else:
        score += 100

    if title_ratio == 1:
        score += 500

    elif title_ratio >= 0.75:
        score += 300

    else:
        score += 100

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    exact_1 = (
        wanted_artist +
        " " +
        wanted_title
    )

    exact_2 = (
        wanted_title +
        " " +
        wanted_artist
    )

    if exact_1 in candidate:
        score += 400

    if exact_2 in candidate:
        score += 350

    requested_words = (
        artist_words |
        title_words
    )

    extra_words = (
        candidate_words -
        requested_words
    )

    score -= len(extra_words) * 15

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
        artist + " " + title
    )

    for modifier in modifiers:

        if (
            modifier in candidate
            and modifier not in requested
        ):

            score -= 150

    return score


def duration_score(
    candidate_duration,
    target_duration
):

    if (
        candidate_duration is None
        or target_duration is None
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
        or target_duration is None
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

        hi_res_url = re.sub(
            r'=w\d+-h\d+.*$',
            '=w1200-h1200-l90-rj',
            cover_url
        )

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
            io.BytesIO(response.content)
        )

        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size

        if width != height:

            side = min(
                width,
                height
            )

            left = (
                width - side
            ) // 2

            top = (
                height - side
            ) // 2

            right = left + side
            bottom = top + side

            img = img.crop(
                (
                    left,
                    top,
                    right,
                    bottom
                )
            )

        output = io.BytesIO()

        img.save(
            output,
            format="JPEG",
            quality=95
        )

        cover_bytes = output.getvalue()

        # ----------------------------------------------------
        # Полностью очищаем старые ID3-теги.
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

        # ----------------------------------------------------
        # Создаём новые ID3-теги.
        # ----------------------------------------------------

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

        duration = data.get(
            "duration"
        )

        cover_url = None

        thumbnails = data.get(
            "thumbnails"
        )

        if thumbnails:

            cover_url = (
                thumbnails[-1].get("url")
            )

        else:

            cover_url = data.get(
                "thumbnail"
            )

        if not artist or not title:

            print(
                "\nНе удалось определить "
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
# ЯНДЕКС МУЗЫКА
# ============================================================

def extract_yandex_ids(url):

    track_match = re.search(
        r"/track/(\d+)",
        url
    )

    album_match = re.search(
        r"/album/(\d+)",
        url
    )

    track_id = (
        track_match.group(1)
        if track_match
        else None
    )

    album_id = (
        album_match.group(1)
        if album_match
        else None
    )

    return (
        track_id,
        album_id
    )


def yandex_duration(value):

    if value is None:
        return None

    try:

        if isinstance(
            value,
            (int, float)
        ):

            return float(value)

        value = str(value).strip()

        if ":" in value:

            parts = value.split(":")

            if len(parts) == 2:

                return (
                    int(parts[0]) * 60
                    + float(parts[1])
                )

        return float(value)

    except Exception:

        return None


def yandex_cover_url(
    cover_uri
):

    if not cover_uri:
        return None

    cover_uri = str(
        cover_uri
    )

    if cover_uri.startswith(
        "http://"
    ) or cover_uri.startswith(
        "https://"
    ):

        url = cover_uri

    else:

        url = (
            "https://"
            +
            cover_uri
            .replace(
                "%%",
                "1000x1000"
            )
        )

    url = url.replace(
        "%%",
        "1000x1000"
    )

    return url


def yandex_artist_name(
    artists
):

    if not artists:
        return ""

    names = []

    if isinstance(
        artists,
        list
    ):

        for artist in artists:

            if isinstance(
                artist,
                dict
            ):

                name = (
                    artist.get("name")
                    or artist.get("title")
                )

                if name:
                    names.append(
                        str(name)
                    )

    elif isinstance(
        artists,
        dict
    ):

        name = (
            artists.get("name")
            or artists.get("title")
        )

        if name:
            names.append(
                str(name)
            )

    return ", ".join(
        names
    )


# ============================================================
# НОВЫЙ ПРЯМОЙ ЗАПРОС ТРЕКА ЯНДЕКСА
# ============================================================

def get_yandex_track_by_id(
    track_id
):

    status(
        "Получение точных метаданных "
        "Яндекс Музыки по ID..."
    )

    if not track_id:

        return None

    try:

        response = requests.post(
            "https://api.music.yandex.net/tracks/",
            data={
                "track-ids":
                    str(track_id)
            },
            headers={
                **HEADERS,
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            timeout=TIMEOUT
        )

        print()
        print(
            "HTTP-код:",
            response.status_code
        )

        print(
            "Размер ответа:",
            len(response.content),
            "байт"
        )

        if response.status_code != 200:

            print(
                "Яндекс API не вернул "
                "данные трека."
            )

            return None

        data = response.json()

        # ----------------------------------------------------
        # Защита от той ошибки, которая была у тебя:
        # result может быть не dict.
        # ----------------------------------------------------

        result = data.get(
            "result"
        )

        if not isinstance(
            result,
            list
        ):

            print(
                "Неожиданный формат "
                "ответа Яндекс API."
            )

            return None

        if not result:

            print(
                "Яндекс API не нашёл "
                "трек по ID."
            )

            return None

        item = result[0]

        if not isinstance(
            item,
            dict
        ):

            print(
                "Яндекс API вернул "
                "трек в неожиданном формате."
            )

            return None

        # ----------------------------------------------------
        # Основные данные
        # ----------------------------------------------------

        found_id = (
            item.get("id")
            or track_id
        )

        title = (
            item.get("title")
            or ""
        )

        artist = yandex_artist_name(
            item.get("artists")
        )

        # ----------------------------------------------------
        # Альбом
        # ----------------------------------------------------

        album_title = ""

        albums = item.get(
            "albums"
        )

        album_id = None

        if isinstance(
            albums,
            list
        ) and albums:

            first_album = albums[0]

            if isinstance(
                first_album,
                dict
            ):

                album_title = (
                    first_album.get(
                        "title"
                    )
                    or ""
                )

                album_id = (
                    first_album.get(
                        "id"
                    )
                )

        if not album_id:

            album = item.get(
                "album"
            )

            if isinstance(
                album,
                dict
            ):

                album_title = (
                    album.get(
                        "title"
                    )
                    or album_title
                )

                album_id = (
                    album.get(
                        "id"
                    )
                )

        # ----------------------------------------------------
        # Длительность
        # ----------------------------------------------------

        duration = None

        if item.get(
            "durationMs"
        ) is not None:

            duration = (
                yandex_duration(
                    item.get(
                        "durationMs"
                    )
                )
                / 1000
            )

        elif item.get(
            "duration"
        ) is not None:

            duration = yandex_duration(
                item.get(
                    "duration"
                )
            )

        # ----------------------------------------------------
        # Обложка
        # ----------------------------------------------------

        cover_uri = (
            item.get(
                "coverUri"
            )
        )

        cover_url = yandex_cover_url(
            cover_uri
        )

        if not artist or not title:

            print(
                "Яндекс API вернул "
                "неполные метаданные."
            )

            return None

        result_data = {
            "source":
                "yandex",

            "artist":
                artist,

            "title":
                title,

            "album":
                album_title,

            "duration":
                duration,

            "track_id":
                str(found_id),

            "album_id":
                (
                    str(album_id)
                    if album_id
                    else None
                ),

            "cover_url":
                cover_url
        }

        print()
        print(
            "Метаданные получены."
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
            "Альбом:",
            album_title
        )

        print(
            "Длительность:",
            format_duration(
                duration
            )
        )

        print(
            "ID трека:",
            found_id
        )

        print(
            "ID альбома:",
            album_id
        )

        print(
            "Обложка:",
            (
                "НАЙДЕНА"
                if cover_url
                else
                "НЕ НАЙДЕНА"
            )
        )

        if album_id:

            result_data["url"] = (
                "https://music.yandex.ru/"
                "album/"
                + str(album_id)
                + "/track/"
                + str(found_id)
            )

        return result_data

    except requests.RequestException as e:

        print(
            "Ошибка запроса к Яндекс API:",
            e
        )

        return None

    except json.JSONDecodeError:

        print(
            "Яндекс API вернул "
            "некорректный JSON."
        )

        return None

    except Exception as e:

        print(
            "Ошибка обработки "
            "данных Яндекс API:",
            e
        )

        return None


# ============================================================
# ПОИСК ЯНДЕКСА — РЕЗЕРВ
# ============================================================

def search_yandex_api(
    artist,
    title,
    duration=None,
    track_id=None,
    album_id=None
):

    status(
        "РЕЗЕРВНЫЙ ПОИСК В ЯНДЕКС МУЗЫКЕ"
    )

    if not artist and not title:

        print(
            "Пустой поисковый запрос "
            "пропущен."
        )

        return None

    query = (
        f"{artist} {title}"
    ).strip()

    print()
    print(
        "Запрос:",
        query
    )

    try:

        response = requests.get(
            "https://api.music.yandex.net/search",
            params={
                "text": query,
                "type": "track",
                "page": 0
            },
            headers={
                **HEADERS,
                "Accept":
                    "application/json"
            },
            timeout=TIMEOUT
        )

        print()
        print(
            "HTTP-код:",
            response.status_code
        )

        print(
            "Размер ответа:",
            len(response.content),
            "байт"
        )

        if response.status_code != 200:

            return None

        data = response.json()

        result = data.get(
            "result"
        )

        # ----------------------------------------------------
        # Защита от "'str' object has no attribute get"
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict
        ):

            print(
                "Яндекс API вернул "
                "неожиданный формат result."
            )

            return None

        tracks_block = result.get(
            "tracks"
        )

        if not isinstance(
            tracks_block,
            dict
        ):

            print(
                "В ответе отсутствует "
                "блок tracks."
            )

            return None

        tracks = tracks_block.get(
            "results",
            []
        )

        if not isinstance(
            tracks,
            list
        ):

            return None

        candidates = []

        for item in tracks:

            if not isinstance(
                item,
                dict
            ):
                continue

            found_id = item.get(
                "id"
            )

            if found_id is None:
                continue

            found_title = (
                item.get("title")
                or ""
            )

            found_artist = (
                yandex_artist_name(
                    item.get("artists")
                )
            )

            albums = item.get(
                "albums"
            )

            found_album = ""

            found_album_id = album_id

            if isinstance(
                albums,
                list
            ) and albums:

                if isinstance(
                    albums[0],
                    dict
                ):

                    found_album = (
                        albums[0].get(
                            "title"
                        )
                        or ""
                    )

                    if albums[0].get(
                        "id"
                    ) is not None:

                        found_album_id = (
                            str(
                                albums[0].get(
                                    "id"
                                )
                            )
                        )

            found_duration = None

            if item.get(
                "durationMs"
            ) is not None:

                found_duration = (
                    yandex_duration(
                        item.get(
                            "durationMs"
                        )
                    )
                    / 1000
                )

            elif item.get(
                "duration"
            ) is not None:

                found_duration = (
                    yandex_duration(
                        item.get(
                            "duration"
                        )
                    )
                )

            cover_url = yandex_cover_url(
                item.get(
                    "coverUri"
                )
            )

            candidate = {
                "source":
                    "yandex",

                "artist":
                    found_artist,

                "title":
                    found_title,

                "album":
                    found_album,

                "duration":
                    found_duration,

                "track_id":
                    str(found_id),

                "album_id":
                    found_album_id,

                "cover_url":
                    cover_url
            }

            score = candidate_text_score(
                found_artist +
                " - " +
                found_title,
                artist,
                title
            )

            score += duration_score(
                found_duration,
                duration
            )

            candidate["score"] = score

            candidates.append(
                candidate
            )

        if not candidates:

            print(
                "Кандидаты не найдены."
            )

            return None

        # ----------------------------------------------------
        # Точный ID имеет абсолютный приоритет
        # ----------------------------------------------------

        if track_id:

            for candidate in candidates:

                if str(
                    candidate["track_id"]
                ) == str(track_id):

                    best = candidate
                    break

            else:

                best = max(
                    candidates,
                    key=lambda x:
                        x["score"]
                )

        else:

            best = max(
                candidates,
                key=lambda x:
                    x["score"]
            )

        if best["score"] < 0:

            return None

        if best["album_id"]:

            best["url"] = (
                "https://music.yandex.ru/"
                "album/"
                + str(
                    best["album_id"]
                )
                + "/track/"
                + str(
                    best["track_id"]
                )
            )

        return best

    except Exception as e:

        print(
            "Ошибка резервного поиска "
            "Яндекс Музыки:",
            e
        )

        return None


# ============================================================
# ПОЛУЧЕНИЕ ИНФОРМАЦИИ ИЗ ЯНДЕКС МУЗЫКИ
# ============================================================

def get_yandex_music_info(url):

    status(
        "ПОЛУЧЕНИЕ ИНФОРМАЦИИ "
        "ИЗ ЯНДЕКС МУЗЫКИ"
    )

    status(
        "АНАЛИЗ ССЫЛКИ ЯНДЕКС МУЗЫКИ"
    )

    track_id, album_id = (
        extract_yandex_ids(url)
    )

    print()
    print(
        "ID трека:",
        track_id
    )

    print(
        "ID альбома:",
        album_id
    )

    if not track_id:

        print()
        print(
            "Не удалось определить "
            "ID трека Яндекс Музыки."
        )

        return None

    # --------------------------------------------------------
    # ГЛАВНОЕ ИСПРАВЛЕНИЕ
    #
    # Не делаем search("", "").
    #
    # Сначала обращаемся непосредственно к API
    # по известному ID трека.
    # --------------------------------------------------------

    result = get_yandex_track_by_id(
        track_id
    )

    if result:

        # Если API не вернул album_id,
        # но он есть в исходной ссылке,
        # используем его.
        if not result.get(
            "album_id"
        ) and album_id:

            result["album_id"] = (
                str(album_id)
            )

            result["url"] = (
                "https://music.yandex.ru/"
                "album/"
                + str(album_id)
                + "/track/"
                + str(track_id)
            )

        return result

    # --------------------------------------------------------
    # РЕЗЕРВ №1
    #
    # Если прямой запрос по ID не сработал,
    # пробуем получить страницу через yt-dlp.
    # --------------------------------------------------------

    print()
    print(
        "Прямой API-запрос не дал данных."
    )

    print(
        "Пробуем получить метаданные "
        "через yt-dlp..."
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

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90
        )

        if process.returncode == 0:

            data = json.loads(
                process.stdout
            )

            artist = (
                data.get("artist")
                or data.get("uploader")
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

            duration = (
                data.get("duration")
            )

            thumbnails = data.get(
                "thumbnails"
            )

            cover_url = None

            if thumbnails:

                cover_url = (
                    thumbnails[-1]
                    .get("url")
                )

            if artist and title:

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

                    "track_id":
                        track_id,

                    "album_id":
                        album_id,

                    "cover_url":
                        cover_url,

                    "url":
                        url
                }

    except Exception:
        pass

    # --------------------------------------------------------
    # РЕЗЕРВ №2
    # --------------------------------------------------------

    print()
    print(
        "Пробуем резервный поиск Яндекс Музыки..."
    )

    # Здесь нельзя искать без artist/title.
    # Поэтому этот резерв возможен только если
    # yt-dlp смог что-то вернуть.
    #
    # На данном этапе это специально не вызывается
    # с пустыми строками.

    print()
    print(
        "Не удалось получить "
        "метаданные Яндекс Музыки."
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
            "track_name": title,
            "artist_name": artist,
            "album_name": album or "",
            "duration":
                int(round(float(duration)))
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
            "title":
                data.get("title")
                or "YouTube Music",

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

    if not os.path.exists(filename):
        return False

    try:

        if (
            os.path.getsize(filename)
            < MIN_FILE_SIZE
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
            data.get("format", {})
            .get("duration")
        )

        if not duration:
            return False

        return float(duration) > 0

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

            headers = {
                "User-Agent":
                    HEADERS["User-Agent"],

                "Accept":
                    "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",

                "Accept-Language":
                    HEADERS["Accept-Language"],

                "Connection":
                    "keep-alive"
            }

            if referer:

                headers["Referer"] = (
                    referer
                )

            session = requests.Session()

            try:

                if referer:

                    session.get(
                        referer,
                        headers=HEADERS,
                        timeout=15,
                        allow_redirects=True
                    )

            except Exception:
                pass

            response = session.get(
                url,
                headers=headers,
                timeout=90,
                stream=True,
                allow_redirects=True
            )

            print()

            print(
                "HTTP-код:",
                response.status_code
            )

            print(
                "Конечный URL:",
                response.url
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

            content_length = (
                response.headers
                .get(
                    "Content-Length"
                )
            )

            if content_length:

                print(
                    "Размер ответа:",
                    content_length,
                    "байт"
                )

            print(
                "Content-Type:",
                content_type
            )

            total = 0

            with open(
                temp_filename,
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=262144
                ):

                    if not chunk:
                        continue

                    file.write(
                        chunk
                    )

                    total += len(
                        chunk
                    )

                    if total >= 1024 * 1024:

                        print(
                            "Получено:",
                            round(
                                total /
                                1024 /
                                1024,
                                2
                            ),
                            "МБ",
                            end="\r"
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

            if total == 0:

                print(
                    "Сервер вернул "
                    "пустой ответ."
                )

                if attempt < retries:

                    time.sleep(1)
                    continue

                return False

            if (
                "text/html"
                in content_type
                or
                "text/plain"
                in content_type
            ):

                print(
                    "Сервер вернул "
                    "не аудиофайл."
                )

                if attempt < retries:

                    time.sleep(1)
                    continue

                return False

            if total < MIN_FILE_SIZE:

                print(
                    "Файл слишком маленький."
                )

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

                print(
                    "Полученный файл "
                    "не является корректным аудио."
                )

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

        except Exception as e:

            print(
                "Ошибка скачивания:",
                e
            )

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
            target_duration
        )
    )

    try:

        query = (
            f"{artist} {title}"
        )

        response = requests.get(
            "https://mp3party.net/search",
            params={
                "q": query
            },
            headers=HEADERS,
            timeout=TIMEOUT
        )

        print()

        print(
            "HTTP-код:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "MP3Party: ошибка HTTP."
            )

            return None

        text = html.unescape(
            response.text
        )

        pattern = re.compile(
            r'<div\s+class=["\']'
            r'track__user-panel'
            r'["\'][^>]*'
            r'data-js-artist-name=["\']'
            r'([^"\']+)'
            r'["\'][^>]*'
            r'data-js-id=["\']'
            r'(\d+)'
            r'["\'][^>]*'
            r'data-js-song-title=["\']'
            r'([^"\']+)'
            r'["\'][^>]*'
            r'data-js-url=["\']'
            r'([^"\']+)'
            r'["\']',
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
                found_artist +
                " - " +
                found_title
            )

            text_score = (
                candidate_text_score(
                    filename,
                    artist,
                    title
                )
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

                "artist":
                    found_artist,

                "title":
                    found_title,

                "text_score":
                    text_score,

                "duration":
                    None,

                "final_score":
                    text_score
            })

        if not candidates:

            print(
                "MP3Party: "
                "подходящий кандидат не найден."
            )

            return None

        print(
            "MP3Party: найдено кандидатов:",
            len(candidates)
        )

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

            print(
                "MP3Party: "
                "подходящий кандидат "
                "по длительности не найден."
            )

            return None

        valid.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        best = valid[0]

        print()
        print(
            "MP3Party: найден подходящий "
            "кандидат."
        )

        print(
            "Исполнитель:",
            best["artist"]
        )

        print(
            "Название:",
            best["title"]
        )

        if best["duration"] is not None:

            print(
                "Длительность:",
                format_duration(
                    best["duration"]
                )
            )

        print(
            "Оценка:",
            best["final_score"]
        )

        print(
            "URL:",
            best["url"]
        )

        return {
            "url":
                best["url"],

            "referer":
                best["referer"]
        }

    except Exception as e:

        print(
            "MP3Party: ошибка:",
            e
        )

        return None


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    print()
    print(
        "2. ПОИСК НА MP3TM"
    )

    query = (
        f"{artist} {title}"
    )

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip("-").lower()

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

            print(
                "MP3TM: "
                "подходящий кандидат не найден."
            )

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
            dict.fromkeys(links)
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

            print(
                "MP3TM: "
                "подходящий кандидат не найден."
            )

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

            print(
                "MP3TM: "
                "подходящий кандидат не найден."
            )

            return None

        valid.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        best = valid[0]

        print(
            "MP3TM: найден подходящий "
            "кандидат."
        )

        return {
            "url":
                best["url"],

            "referer":
                page_url
        }

    except Exception as e:

        print(
            "MP3TM: ошибка:",
            e
        )

        return None


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(
    artist,
    title,
    target_duration=None
):

    print()
    print(
        "3. ПОИСК НА AUDIOSTART"
    )

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

            print(
                "AudioStart: "
                "подходящий кандидат не найден."
            )

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
            dict.fromkeys(links)
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

                if link.startswith("//"):

                    link = (
                        "https:" +
                        link
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

            print(
                "AudioStart: "
                "подходящий кандидат не найден."
            )

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

            print(
                "AudioStart: "
                "подходящий кандидат не найден."
            )

            return None

        valid.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        best = valid[0]

        print(
            "AudioStart: найден подходящий "
            "кандидат."
        )

        return {
            "url":
                best["url"],

            "referer":
                "https://audiostart.net/"
        }

    except Exception as e:

        print(
            "AudioStart: ошибка:",
            e
        )

        return None


# ============================================================
# РЕЗЕРВНЫЙ YT-DLP
# ============================================================

def download_with_ytdlp(
    source_url,
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
        source_url
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

        possible_files = []

        for filename in os.listdir(
            directory
        ):

            if filename.startswith(
                base +
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

    # --------------------------------------------------------
    # 1. MP3PARTY
    # --------------------------------------------------------

    result = search_mp3party(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=MP3PARTY_RETRIES
        ):

            return filepath

        print()
        print(
            "MP3Party: кандидат найден, "
            "но скачать его не удалось."
        )

    # --------------------------------------------------------
    # 2. MP3TM
    # --------------------------------------------------------

    result = search_mp3tm(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=2
        ):

            return filepath

    # --------------------------------------------------------
    # 3. AUDIOSTART
    # --------------------------------------------------------

    result = search_audiostart(
        artist,
        title,
        duration
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=2
        ):

            return filepath

    # --------------------------------------------------------
    # 4. РЕЗЕРВ YT-DLP
    # --------------------------------------------------------

    if source == "youtube":

        if download_with_ytdlp(
            source_url,
            filepath
        ):

            return filepath

    else:

        print()
        print(
            "Резервный yt-dlp для "
            "Яндекс Музыки не используется."
        )

    print()
    print(
        "Не удалось скачать "
        "подходящий аудиофайл."
    )

    return None


# ============================================================
# ОДИНОЧНЫЙ YOUTUBE MUSIC
# ============================================================

def process_youtube_track(
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
    cover_url = info.get(
        "cover_url"
    )

    print()
    print("=" * 50)
    print(
        "ИНФОРМАЦИЯ О ТРЕКЕ"
    )
    print("=" * 50)
    print()

    print(
        "Источник: youtube"
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
        format_duration(duration)
    )

    print(
        "Обложка:",
        (
            "НАЙДЕНА"
            if cover_url
            else
            "НЕ НАЙДЕНА"
        )
    )

    filepath = find_and_download_track(
        artist,
        title,
        duration,
        output_folder,
        url,
        "youtube"
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
# ОДИНОЧНЫЙ YANDEX MUSIC
# ============================================================

def process_yandex_track(
    url,
    output_folder
):

    info = get_yandex_music_info(
        url
    )

    if not info:
        return False

    artist = info["artist"]
    title = info["title"]
    album = info.get(
        "album",
        ""
    )
    duration = info.get(
        "duration"
    )
    cover_url = info.get(
        "cover_url"
    )

    print()
    print("=" * 50)
    print(
        "ИНФОРМАЦИЯ О ТРЕКЕ"
    )
    print("=" * 50)
    print()

    print(
        "Источник: yandex"
    )

    print(
        "Исполнитель:",
        artist
    )

    print(
        "Название:   ",
        title
    )

    print(
        "Альбом:     ",
        album
    )

    print(
        "Длительность:",
        format_duration(duration)
    )

    print(
        "Обложка:",
        (
            "НАЙДЕНА"
            if cover_url
            else
            "НЕ НАЙДЕНА"
        )
    )

    filepath = find_and_download_track(
        artist,
        title,
        duration,
        output_folder,
        info.get(
            "url",
            url
        ),
        "yandex"
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

    tracks = playlist["tracks"]

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
        print("#" * 60)

        print(
            f"ТРЕК {index}/{len(tracks)}"
        )

        print("#" * 60)

        if process_youtube_track(
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
# ОПРЕДЕЛЕНИЕ ИСТОЧНИКА
# ============================================================

def is_yandex_music_url(url):

    return (
        "music.yandex." in url
        and (
            "/track/" in url
            or
            "/album/" in url
        )
    )


def is_youtube_music_url(url):

    return (
        (
            "music.youtube.com" in url
            or
            "youtube.com" in url
        )
        and
        (
            "/watch" in url
            or
            "youtu.be/" in url
        )
    )


def is_playlist_url(url):

    return (
        "list=" in url
        and (
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
    # ЯНДЕКС МУЗЫКА
    # --------------------------------------------------------

    if is_yandex_music_url(
        url
    ):

        print()
        print("=" * 60)
        print(
            "ИСТОЧНИК: ЯНДЕКС МУЗЫКА"
        )
        print("=" * 60)

        success = process_yandex_track(
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

        return

    # --------------------------------------------------------
    # PLAYLIST YOUTUBE MUSIC
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
    # YOUTUBE MUSIC
    # --------------------------------------------------------

    if is_youtube_music_url(
        url
    ):

        success = process_youtube_track(
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

        return

    # --------------------------------------------------------
    # НЕИЗВЕСТНАЯ ССЫЛКА
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "НЕИЗВЕСТНЫЙ ИСТОЧНИК"
    )
    print("=" * 60)

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

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":

    main()
