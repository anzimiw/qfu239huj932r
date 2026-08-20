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
# БИБЛИОТЕКИ
# ============================================================

try:
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

YTDLP = "yt-dlp.exe"

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
MP3TM_RETRIES = 2
AUDIOSTART_RETRIES = 2
YTDLP_RETRIES = 2

DOWNLOAD_LRC = False
LRCLIB_DELAY = 1.0


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

    text = re.sub(r"\(MP3\.tm\)", "", text, flags=re.I)
    text = re.sub(r"\(audiostart\.net\)", "", text, flags=re.I)
    text = re.sub(r"\.mp3$", "", text, flags=re.I)
    text = re.sub(r"[,;|/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


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
    text = re.sub(r"\s+", " ", text)

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

    return f"{seconds // 60}:{seconds % 60:02d}"


# ============================================================
# ОБЛОЖКА + ID3
# ============================================================

def embed_cover(mp3_filepath, cover_url, artist, title, album=""):

    if not MUTAGEN_AVAILABLE:
        print()
        print(
            "[ОШИБКА] Библиотека mutagen не установлена!"
        )
        print("Выполни: pip install mutagen")
        return

    if not cover_url:
        print()
        print(
            "[ВНИМАНИЕ] У трека отсутствует ссылка на обложку."
        )
        return

    if not PIL_AVAILABLE:
        print()
        print(
            "[ОШИБКА] Библиотека Pillow не установлена!"
        )
        print("Выполни: pip install Pillow")
        return

    status("Вшивание обложки и тегов...")

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
                f"Не удалось скачать обложку "
                f"(код ответа: {response.status_code})"
            )
            return

        img = Image.open(
            io.BytesIO(response.content)
        )

        if img.mode != "RGB":
            img = img.convert("RGB")

        output = io.BytesIO()

        img.save(
            output,
            format="JPEG",
            quality=95
        )

        cover_bytes = output.getvalue()

        try:
            tags = ID3(mp3_filepath)
            tags.delete(mp3_filepath)
        except Exception:
            pass

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
            "Обложка и теги успешно вшиты в файл!"
        )

    except Exception as e:
        print(
            "Ошибка при прикреплении обложки:",
            e
        )


# ============================================================
# YOUTUBE MUSIC INFO
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

            print()
            print(
                "Не удалось получить информацию о треке."
            )

            if result.stderr.strip():
                print(result.stderr.strip())

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

        album = data.get("album") or ""

        duration = data.get("duration")

        cover_url = None

        thumbnails = data.get("thumbnails")

        if thumbnails:

            valid_thumbnails = [
                item
                for item in thumbnails
                if item.get("url")
            ]

            if valid_thumbnails:
                cover_url = (
                    valid_thumbnails[-1]["url"]
                )

        if not cover_url:
            cover_url = data.get(
                "thumbnail"
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
            "cover_url": cover_url
        }

    except FileNotFoundError:

        print()
        print(
            "ОШИБКА: yt-dlp.exe "
            "не найден рядом со скриптом."
        )

        return None

    except json.JSONDecodeError:

        print()
        print(
            "ОШИБКА: yt-dlp не вернул "
            "корректные данные."
        )

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
        print(
            "ОШИБКА:",
            e
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
            "duration": int(
                round(float(duration))
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
                "Синхронизированный текст "
                "не найден."
            )

            return None

        lyrics = (
            response.json()
            .get("syncedLyrics")
        )

        if not lyrics:

            print(
                "Синхронизированный текст "
                "не найден."
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


def save_lrc(mp3_filepath, lyrics):

    lrc_filepath = (
        os.path.splitext(mp3_filepath)[0]
        + ".lrc"
    )

    try:

        with open(
            lrc_filepath,
            "w",
            encoding="utf-8-sig",
            newline="\n"
        ) as file:

            file.write(lyrics)

        print("LRC готов.")

        return True

    except Exception as e:

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

    status(
        "Сохранение LRC..."
    )

    return save_lrc(
        mp3_filepath,
        lyrics
    )


# ============================================================
# ПЛЕЙЛИСТ
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

            print()
            print(
                "Не удалось получить плейлист."
            )

            if result.stderr.strip():
                print(
                    result.stderr.strip()
                )

            return None

        data = json.loads(
            result.stdout
        )

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

        return {
            "title":
                data.get("title")
                or "YouTube Music",

            "tracks":
                tracks
        }

    except Exception as e:

        print()
        print(
            "Ошибка получения плейлиста:",
            e
        )

        return None


# ============================================================
# ПРОВЕРКА MP3
# ============================================================

def validate_audio_file(filename):

    if not os.path.exists(filename):
        return False

    try:

        size = os.path.getsize(filename)

        if size < MIN_FILE_SIZE:
            return False

        command = [
            "ffprobe",
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
            data
            .get("format", {})
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
            "ffprobe",
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
# УНИВЕРСАЛЬНОЕ СКАЧИВАНИЕ
# ============================================================

def download_file(
    url,
    filename,
    referer=None,
    retries=2
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

                try:
                    os.remove(
                        temp_filename
                    )
                except Exception:
                    pass

            headers = dict(HEADERS)

            headers["Accept"] = (
                "audio/mpeg,audio/*;"
                "q=0.9,*/*;q=0.8"
            )

            headers["Range"] = "bytes=0-"

            if referer:
                headers["Referer"] = referer

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

                    print(
                        f"HTTP-код: "
                        f"{response.status_code}"
                    )

                    if attempt < retries:

                        status(
                            "Повторная попытка "
                            "скачивания..."
                        )

                        time.sleep(1)

                        continue

                    return False

                total = 0

                with open(
                    temp_filename,
                    "wb"
                ) as file:

                    for chunk in response.iter_content(
                        chunk_size=262144
                    ):

                        if chunk:

                            file.write(chunk)

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

                # ------------------------------------------------
                # ВАЖНО:
                # Проверяем файл ДО его переименования.
                # Если 0 МБ / слишком маленький —
                # удаляем и пробуем ещё раз.
                # ------------------------------------------------

                if total < MIN_FILE_SIZE:

                    try:
                        os.remove(
                            temp_filename
                        )
                    except Exception:
                        pass

                    if attempt < retries:

                        status(
                            "Получен некорректный файл. "
                            "Повторная попытка..."
                        )

                        time.sleep(1)

                        continue

                    return False

                status(
                    "Проверка аудиофайла..."
                )

                if not validate_audio_file(
                    temp_filename
                ):

                    try:
                        os.remove(
                            temp_filename
                        )
                    except Exception:
                        pass

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
                print(
                    "Аудиофайл готов."
                )

                return True

        except Exception as e:

            try:

                if os.path.exists(
                    temp_filename
                ):
                    os.remove(
                        temp_filename
                    )

            except Exception:
                pass

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
# MP3PARTY
# ============================================================

def search_mp3party(
    artist,
    title
):

    status(
        "Поиск подходящего аудиофайла..."
    )

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

        wanted_artist = normalize(
            artist
        )

        wanted_title = normalize(
            title
        )

        for (
            found_artist,
            song_id,
            found_title,
            _
        ) in pattern.findall(text):

            if (
                normalize(found_artist)
                == wanted_artist
                and
                normalize(found_title)
                == wanted_title
            ):

                return {
                    "url":
                        "https://dl2.mp3party.net/download/"
                        + song_id,

                    "referer":
                        "https://mp3party.net/"
                }

    except Exception:
        pass

    return None


# ============================================================
# MP3TM
# ============================================================

def score_mp3tm_candidate(
    filename,
    artist,
    title
):

    name = normalize(
        filename
    )

    wanted_artist = normalize(
        artist
    )

    wanted_title = normalize(
        title
    )

    name_words = normalize_words(
        name
    )

    artist_words = normalize_words(
        artist
    )

    title_words = normalize_words(
        title
    )

    score = 0

    artist_matches = (
        artist_words & name_words
    )

    if artist_words:

        ratio = (
            len(artist_matches)
            /
            len(artist_words)
        )

        if ratio == 1:
            score += 300

        elif ratio >= 0.5:
            score += 120

        else:
            return -10000

    title_matches = (
        title_words & name_words
    )

    if title_words:

        ratio = (
            len(title_matches)
            /
            len(title_words)
        )

        if ratio == 1:
            score += 300

        elif ratio >= 0.5:
            score += 120

        else:
            return -10000

    if wanted_artist in name:
        score += 200

    if wanted_title in name:
        score += 200

    if (
        wanted_artist
        + " - "
        + wanted_title
    ) in name:

        score += 500

    if (
        wanted_title
        + " - "
        + wanted_artist
    ) in name:

        score += 350

    if name == (
        wanted_artist
        + " "
        + wanted_title
    ):

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

    score -= (
        len(extra_words)
        * 20
    )

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
            and modifier not in requested_text
        ):

            score -= 100

    return score


def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    status(
        "Проверка дополнительных вариантов..."
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
            return None

        text = html.unescape(
            response.text
        )

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
                "score": score,
                "duration": None
            })

        if not candidates:
            return None

        candidates.sort(
            key=lambda item:
                item["score"],
            reverse=True
        )

        top_score = (
            candidates[0]["score"]
        )

        top_candidates = [
            item
            for item in candidates
            if item["score"] == top_score
        ]

        for candidate in top_candidates[:10]:

            candidate["duration"] = (
                get_duration(
                    candidate["url"]
                )
            )

        if target_duration is not None:

            valid = [
                item
                for item in top_candidates
                if item["duration"] is not None
            ]

            if valid:

                best = min(
                    valid,
                    key=lambda item:
                        abs(
                            item["duration"]
                            -
                            target_duration
                        )
                )

            else:

                best = top_candidates[0]

        else:

            best = top_candidates[0]

        return {
            "url": best["url"],
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
    title
):

    status(
        "Проверка ещё одного источника..."
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
            return None

        text = html.unescape(
            response.text
        )

        links = re.findall(
            r'href=["\']([^"\']*?/getmp3/[^"\']+)["\']',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(links)
        )

        wanted_artist = normalize(
            artist
        )

        wanted_title = normalize(
            title
        )

        for link in links:

            try:

                encoded = (
                    link.split(
                        "/getmp3/",
                        1
                    )[1]
                )

                decoded = (
                    base64
                    .b64decode(encoded)
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                )

                decoded = normalize(
                    unquote(decoded)
                )

                if (
                    wanted_artist in decoded
                    and
                    wanted_title in decoded
                ):

                    if link.startswith("//"):
                        link = "https:" + link

                    return {
                        "url": link,
                        "referer":
                            "https://audiostart.net/"
                    }

            except Exception:
                continue

    except Exception:
        pass

    return None


# ============================================================
# YT-DLP FALLBACK
# ============================================================

def download_with_ytdlp(
    url,
    filepath,
    artist,
    title,
    album
):

    status(
        "Переход к резервному скачиванию через yt-dlp..."
    )

    temp_template = (
        os.path.splitext(filepath)[0]
        + ".ytdlp_temp.%(ext)s"
    )

    command = [
        YTDLP,

        "--no-playlist",

        "--quiet",
        "--no-warnings",

        "--retries",
        str(YTDLP_RETRIES),

        "--fragment-retries",
        str(YTDLP_RETRIES),

        "--extractor-retries",
        str(YTDLP_RETRIES),

        "--file-access-retries",
        str(YTDLP_RETRIES),

        "--no-part",

        "-f",
        "bestaudio/best",

        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",

        "-o",
        temp_template,

        url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300
        )

        # ----------------------------------------------------
        # Ищем созданный файл независимо от расширения
        # ----------------------------------------------------

        base = os.path.splitext(
            temp_template
        )[0]

        possible_files = []

        folder = os.path.dirname(
            temp_template
        )

        if os.path.isdir(folder):

            prefix = os.path.basename(
                base
            )

            for name in os.listdir(folder):

                if name.startswith(prefix):

                    full = os.path.join(
                        folder,
                        name
                    )

                    if os.path.isfile(full):
                        possible_files.append(full)

        if not possible_files:

            print()
            print(
                "yt-dlp не создал аудиофайл."
            )

            if result.stderr.strip():

                print(
                    result.stderr.strip()
                )

            return False

        source_file = max(
            possible_files,
            key=os.path.getsize
        )

        if not validate_audio_file(
            source_file
        ):

            print()
            print(
                "yt-dlp создал некорректный "
                "аудиофайл."
            )

            try:
                os.remove(source_file)
            except Exception:
                pass

            return False

        if os.path.exists(filepath):

            try:
                os.remove(filepath)
            except Exception:
                pass

        os.replace(
            source_file,
            filepath
        )

        print()
        print(
            "Аудиофайл успешно скачан "
            "через yt-dlp."
        )

        return True

    except subprocess.TimeoutExpired:

        print()
        print(
            "yt-dlp не завершил скачивание "
            "за отведённое время."
        )

        return False

    except Exception as e:

        print()
        print(
            "Ошибка yt-dlp:",
            e
        )

        return False


# ============================================================
# ПОИСК И СКАЧИВАНИЕ ТРЕКА
# ============================================================

def find_and_download_track(
    artist,
    title,
    duration,
    output_folder,
    original_url
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
        f"{safe_filename(artist)}"
        f" - "
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
        title
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
            "MP3Party не дал корректный файл."
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
            retries=MP3TM_RETRIES
        ):

            return filepath

        print()
        print(
            "MP3TM не дал корректный файл."
        )

    # --------------------------------------------------------
    # 3. AUDIOSTART
    # --------------------------------------------------------

    result = search_audiostart(
        artist,
        title
    )

    if result:

        if download_file(
            result["url"],
            filepath,
            referer=result["referer"],
            retries=AUDIOSTART_RETRIES
        ):

            return filepath

        print()
        print(
            "AudioStart не дал корректный файл."
        )

    # --------------------------------------------------------
    # 4. YT-DLP
    # --------------------------------------------------------

    print()
    print(
        "Все дополнительные источники "
        "не дали корректный файл."
    )

    if download_with_ytdlp(
        original_url,
        filepath,
        artist,
        title,
        album=""
    ):

        return filepath

    print()
    print(
        "Не удалось скачать трек "
        "ни одним из доступных способов."
    )

    return None


# ============================================================
# ОДИНОЧНЫЙ ТРЕК
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
    cover_url = info.get("cover_url")

    print()
    print("=" * 50)
    print(
        "ИНФОРМАЦИЯ О ТРЕКЕ"
    )
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
        duration,
        output_folder,
        url
    )

    if not filepath:
        return False

    # --------------------------------------------------------
    # ОБЛОЖКА
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
# ПРОВЕРКА URL ПЛЕЙЛИСТА
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
        print("#" * 60)
        print(
            f"ТРЕК {index}/{len(tracks)}"
        )
        print("#" * 60)

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

        print()
        print(
            "Введите 1 или 2."
        )

    print()

    url = input(
        "Ссылка на трек или плейлист "
        "YouTube Music: "
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

    # --------------------------------------------------------
    # ПЛЕЙЛИСТ
    # --------------------------------------------------------

    if is_playlist_url(url):

        process_playlist(
            url
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # ОДИНОЧНЫЙ ТРЕК
    # --------------------------------------------------------

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
