import requests
import re
import html
import json
import subprocess
import os
import time
import io
from urllib.parse import unquote, urljoin

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
        "AppleWebKit/537.36 (KHTML, like Gecko) "
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

FFPROBE = "ffprobe.exe"


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
    text = re.sub(r"\(MP3\.tm\)\.mp3$", "", text, flags=re.I)
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
        print(
            "\n[ОШИБКА] Не установлен mutagen.\n"
            "Выполни: pip install mutagen"
        )
        return

    if not PIL_AVAILABLE:
        print(
            "\n[ОШИБКА] Не установлен Pillow.\n"
            "Выполни: pip install Pillow"
        )
        return

    if not cover_url:
        print("\n[ВНИМАНИЕ] Обложка не найдена.")
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
                "Не удалось скачать обложку.",
                response.status_code
            )
            return

        img = Image.open(io.BytesIO(response.content))

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

        print("Обложка и теги успешно вшиты.")

    except Exception as e:
        print("Ошибка при прикреплении обложки:", e)


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

        album = data.get("album") or ""
        duration = data.get("duration")

        cover_url = None

        thumbnails = data.get("thumbnails")

        if thumbnails:
            cover_url = thumbnails[-1].get("url")

        if not cover_url:
            cover_url = data.get("thumbnail")

        if not artist or not title:
            print()
            print("Не удалось определить исполнителя или название.")
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
        print("ОШИБКА: yt-dlp.exe не найден рядом со скриптом.")

        return None

    except json.JSONDecodeError:

        print()
        print("ОШИБКА: yt-dlp не вернул корректные данные.")

        return None

    except subprocess.TimeoutExpired:

        print()
        print("ОШИБКА: получение данных заняло слишком много времени.")

        return None

    except Exception as e:

        print()
        print("ОШИБКА:", e)

        return None


# ============================================================
# LRC
# ============================================================

def search_lrclib(
    artist,
    title,
    album=None,
    duration=None
):

    status("Поиск синхронизированного текста...")

    if duration is None:
        print("Недостаточно данных для поиска текста.")
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
            print("Синхронизированный текст не найден.")
            return None

        lyrics = response.json().get("syncedLyrics")

        if not lyrics:
            print("Синхронизированный текст не найден.")
            return None

        return lyrics.strip()

    except Exception:
        print("Не удалось получить текст.")
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

        print()
        print("Не удалось сохранить LRC:", e)

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
# ПЛЕЙЛИСТ
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

        return {
            "title": data.get("title") or "YouTube Music",
            "tracks": tracks
        }

    except Exception as e:

        print()
        print("Ошибка получения плейлиста:", e)

        return None


# ============================================================
# ПРОВЕРКА MP3
# ============================================================

def validate_audio_file(filename):

    if not os.path.exists(filename):
        return False

    try:

        if os.path.getsize(filename) < MIN_FILE_SIZE:
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

        fmt = data.get("format", {})

        duration = fmt.get("duration")

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

        return float(value) if value else None

    except Exception:
        return None


# ============================================================
# СКАЧИВАНИЕ HTTP
# ============================================================

def download_file(
    url,
    filename,
    referer=None,
    retries=2,
    source_name="Источник"
):

    status(
        f"Скачивание аудиофайла ({source_name})..."
    )

    temp_filename = filename + ".tmp"

    for attempt in range(1, retries + 1):

        try:

            if os.path.exists(temp_filename):

                try:
                    os.remove(temp_filename)
                except Exception:
                    pass

            headers = dict(HEADERS)

            headers["Accept"] = (
                "audio/mpeg,audio/*;q=0.9,*/*;q=0.8"
            )

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

                content_type = (
                    response.headers
                    .get("Content-Type", "")
                    .lower()
                )

                if response.status_code not in (200, 206):

                    print(
                        f"HTTP {response.status_code}"
                    )

                    if attempt < retries:
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

                print(
                    "Получено:",
                    round(
                        total / 1024 / 1024,
                        2
                    ),
                    "МБ"
                )

                # ------------------------------------------------
                # ОТБРАСЫВАЕМ HTML / ЗАЩИТУ / ПУСТОЙ ОТВЕТ
                # ------------------------------------------------

                if total < MIN_FILE_SIZE:

                    print(
                        "Ответ слишком маленький."
                    )

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                if (
                    "text/html" in content_type
                    and "audio" not in content_type
                ):

                    print(
                        "Источник вернул HTML вместо аудио."
                    )

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                # ------------------------------------------------
                # ПРОВЕРКА FFMPEG
                # ------------------------------------------------

                status("Проверка аудиофайла...")

                if not validate_audio_file(
                    temp_filename
                ):

                    print(
                        "Файл не является корректным аудио."
                    )

                    if attempt < retries:
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

                print("Аудиофайл готов.")

                return True

        except Exception as e:

            if attempt < retries:

                print(
                    "Ошибка соединения. "
                    "Повторная попытка..."
                )

                time.sleep(1)

                continue

            print(
                "Ошибка скачивания:",
                e
            )

            return False

    return False


# ============================================================
# MP3PARTY
# ============================================================

def score_candidate(
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
        artist_words & name_words
    )

    title_matches = (
        title_words & name_words
    )

    if artist_words:

        ratio = (
            len(artist_matches)
            / len(artist_words)
        )

        if ratio == 1:
            score += 300

        elif ratio >= 0.5:
            score += 120

        else:
            return -10000

    if title_words:

        ratio = (
            len(title_matches)
            / len(title_words)
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

    modifiers = [
        "nightcore",
        "remix",
        "slowed",
        "sped",
        "speed",
        "bass",
        "type beat",
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


def search_mp3party(
    artist,
    title
):

    status("MP3Party: поиск трека...")

    session = requests.Session()

    try:

        query = f"{artist} {title}"

        response = session.get(
            "https://mp3party.net/search",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return []

        text = html.unescape(
            response.text
        )

        candidates = []

        # --------------------------------------------------------
        # Ищем страницы /music/...
        # --------------------------------------------------------

        links = re.findall(
            r'href=["\']([^"\']*/music/\d+[^"\']*)',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(
                urljoin(
                    "https://mp3party.net/",
                    x
                )
                for x in links
            )
        )

        # --------------------------------------------------------
        # Также ищем data-js-id
        # --------------------------------------------------------

        ids = re.findall(
            r'data-js-id=["\'](\d+)["\']',
            text,
            re.I
        )

        for song_id in ids:

            page = (
                "https://mp3party.net/music/"
                + song_id
            )

            if page not in links:
                links.append(page)

        wanted_artist = normalize(artist)
        wanted_title = normalize(title)

        # --------------------------------------------------------
        # Анализируем страницы результатов
        # --------------------------------------------------------

        for page_url in links[:20]:

            try:

                page_response = session.get(
                    page_url,
                    headers={
                        **HEADERS,
                        "Referer":
                            "https://mp3party.net/"
                    },
                    timeout=TIMEOUT
                )

                if page_response.status_code != 200:
                    continue

                page_text = html.unescape(
                    page_response.text
                )

                # ------------------------------------------------
                # Ищем названия на странице
                # ------------------------------------------------

                combined = normalize(
                    page_text
                )

                score = 0

                if wanted_artist in combined:
                    score += 250

                if wanted_title in combined:
                    score += 250

                # ------------------------------------------------
                # Ищем реальные download-ссылки
                # ------------------------------------------------

                download_links = re.findall(
                    r'(?:href|data-url|data-download-url)'
                    r'=["\']([^"\']+)["\']',
                    page_text,
                    re.I
                )

                for link in download_links:

                    full_url = urljoin(
                        page_url,
                        html.unescape(link)
                    )

                    low = full_url.lower()

                    if (
                        "download" not in low
                        and ".mp3" not in low
                    ):
                        continue

                    candidates.append({
                        "url": full_url,
                        "referer": page_url,
                        "score": score + 100
                    })

            except Exception:
                continue

        # --------------------------------------------------------
        # Старый вариант data-js-artist-name
        # --------------------------------------------------------

        pattern = re.compile(
            r'data-js-artist-name="([^"]+)"'
            r'[^>]*'
            r'data-js-id="(\d+)"'
            r'[^>]*'
            r'data-js-song-title="([^"]+)"',
            re.I
        )

        for (
            found_artist,
            song_id,
            found_title
        ) in pattern.findall(text):

            found_score = score_candidate(
                f"{found_artist} - {found_title}",
                artist,
                title
            )

            if found_score <= -1000:
                continue

            # Страница, а не предполагаемый CDN URL.
            candidates.append({
                "url":
                    "https://mp3party.net/music/"
                    + song_id,
                "referer":
                    "https://mp3party.net/",
                "score":
                    found_score
            })

        # --------------------------------------------------------
        # Убираем дубли
        # --------------------------------------------------------

        unique = {}

        for candidate in candidates:

            key = candidate["url"]

            if (
                key not in unique
                or candidate["score"]
                > unique[key]["score"]
            ):

                unique[key] = candidate

        result = list(
            unique.values()
        )

        result.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return result[:10]

    except Exception:
        return []


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    status("MP3TM: поиск трека...")

    query = f"{artist} {title}"

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
            return []

        text = html.unescape(
            response.text
        )

        links = re.findall(
            r'https?://[^"\'>\s]+\.mp3'
            r'(?:\?[^"\'>\s]*)?',
            text,
            re.I
        )

        # --------------------------------------------------------
        # Иногда URL закодирован
        # --------------------------------------------------------

        encoded_links = re.findall(
            r'https?[^"\']+fine\.sunproxy\.net'
            r'[^"\']+',
            text,
            re.I
        )

        links.extend(encoded_links)

        links = list(
            dict.fromkeys(
                links
            )
        )

        candidates = []

        for link in links:

            link = html.unescape(
                link
            )

            filename = clean_filename(
                link.split("/")[-1]
            )

            score = score_candidate(
                filename,
                artist,
                title
            )

            if score <= -1000:
                continue

            candidates.append({
                "url": link,
                "referer": page_url,
                "score": score,
                "duration": None
            })

        if not candidates:
            return []

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # --------------------------------------------------------
        # Проверяем длительность только лучших кандидатов
        # --------------------------------------------------------

        top_score = candidates[0]["score"]

        top_candidates = [
            x
            for x in candidates
            if x["score"] == top_score
        ]

        if target_duration is not None:

            for candidate in top_candidates[:10]:

                candidate["duration"] = (
                    get_duration(
                        candidate["url"]
                    )
                )

            valid = [
                x
                for x in top_candidates
                if x["duration"] is not None
            ]

            if valid:

                valid.sort(
                    key=lambda x:
                    abs(
                        x["duration"]
                        - target_duration
                    )
                )

                return valid

        return top_candidates

    except Exception:
        return []


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(
    artist,
    title
):

    status("AudioStart: поиск трека...")

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
            return []

        text = html.unescape(
            response.text
        )

        links = re.findall(
            r'(?:href|data-url|data-link)'
            r'=["\']([^"\']*?/getmp3/[^"\']+)["\']',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(
                links
            )
        )

        results = []

        wanted_artist = normalize(
            artist
        )

        wanted_title = normalize(
            title
        )

        for link in links:

            if link.startswith("//"):
                link = "https:" + link

            elif link.startswith("/"):
                link = (
                    "https://audiostart.net"
                    + link
                )

            decoded_text = ""

            # ----------------------------------------------------
            # Пытаемся прочитать название из base64,
            # но не используем это для обхода защиты.
            # ----------------------------------------------------

            try:

                encoded = (
                    link.split(
                        "/getmp3/",
                        1
                    )[1]
                )

                import base64

                decoded = base64.b64decode(
                    encoded
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                decoded_text = normalize(
                    unquote(decoded)
                )

            except Exception:
                pass

            score = 0

            if wanted_artist in decoded_text:
                score += 300

            if wanted_title in decoded_text:
                score += 300

            results.append({
                "url": link,
                "referer":
                    "https://audiostart.net/",
                "score": score
            })

        results.sort(
            key=lambda x:
            x["score"],
            reverse=True
        )

        return results[:10]

    except Exception:
        return []


# ============================================================
# YT-DLP FALLBACK
# ============================================================

def download_with_ytdlp(
    url,
    filepath
):

    status(
        "Резервное скачивание через yt-dlp..."
    )

    temp_template = (
        os.path.splitext(filepath)[0]
        + ".yt-dlp.%(ext)s"
    )

    command = [
        YTDLP,

        "--no-playlist",

        "-f",
        "bestaudio/best",

        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",

        "--no-continue",
        "--no-part",

        "-o",
        temp_template,

        url
    ]

    for attempt in range(
        1,
        YTDLP_RETRIES + 1
    ):

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )

            if result.returncode == 0:

                possible_files = []

                base = os.path.splitext(
                    filepath
                )[0]

                for ext in (
                    ".mp3",
                    ".m4a",
                    ".webm",
                    ".opus"
                ):

                    candidate = (
                        base
                        + ".yt-dlp"
                        + ext
                    )

                    if os.path.exists(
                        candidate
                    ):

                        possible_files.append(
                            candidate
                        )

                for source_file in possible_files:

                    if ext := os.path.splitext(
                        source_file
                    )[1].lower():

                        if ext != ".mp3":

                            converted = (
                                filepath
                            )

                            ffmpeg_command = [
                                "ffmpeg",
                                "-y",
                                "-i",
                                source_file,
                                "-vn",
                                "-codec:a",
                                "libmp3lame",
                                "-q:a",
                                "0",
                                converted
                            ]

                            conversion = (
                                subprocess.run(
                                    ffmpeg_command,
                                    capture_output=True,
                                    text=True,
                                    encoding="utf-8",
                                    errors="replace",
                                    timeout=300
                                )
                            )

                            if (
                                conversion.returncode == 0
                                and validate_audio_file(
                                    converted
                                )
                            ):

                                try:
                                    os.remove(
                                        source_file
                                    )
                                except Exception:
                                    pass

                                return True

                        else:

                            if validate_audio_file(
                                source_file
                            ):

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

                                return True

            if attempt < YTDLP_RETRIES:

                status(
                    "yt-dlp: повторная попытка..."
                )

                time.sleep(2)

        except Exception as e:

            if attempt >= YTDLP_RETRIES:

                print(
                    "Ошибка yt-dlp:",
                    e
                )

    return False


# ============================================================
# СКАЧИВАНИЕ С ИСТОЧНИКАМИ
# ============================================================

def try_source_candidates(
    candidates,
    filepath,
    source_name,
    retries
):

    for index, candidate in enumerate(
        candidates,
        1
    ):

        print()
        print(
            f"{source_name}: "
            f"кандидат {index}/{len(candidates)}"
        )

        if download_file(
            candidate["url"],
            filepath,
            referer=candidate.get(
                "referer"
            ),
            retries=retries,
            source_name=source_name
        ):

            return True

    return False


def find_and_download_track(
    youtube_url,
    artist,
    title,
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

    # ========================================================
    # 1. MP3PARTY
    # ========================================================

    candidates = search_mp3party(
        artist,
        title
    )

    if candidates:

        if try_source_candidates(
            candidates,
            filepath,
            "MP3Party",
            MP3PARTY_RETRIES
        ):

            return filepath

    print()
    print("MP3Party: рабочий файл не получен.")

    # ========================================================
    # 2. MP3TM
    # ========================================================

    candidates = search_mp3tm(
        artist,
        title,
        duration
    )

    if candidates:

        if try_source_candidates(
            candidates,
            filepath,
            "MP3TM",
            MP3TM_RETRIES
        ):

            return filepath

    print()
    print("MP3TM: рабочий файл не получен.")

    # ========================================================
    # 3. AUDIOSTART
    # ========================================================

    candidates = search_audiostart(
        artist,
        title
    )

    if candidates:

        if try_source_candidates(
            candidates,
            filepath,
            "AudioStart",
            AUDIOSTART_RETRIES
        ):

            return filepath

    print()
    print("AudioStart: рабочий файл не получен.")

    # ========================================================
    # 4. YT-DLP
    # ========================================================

    print()
    print(
        "Все внешние источники не смогли "
        "отдать рабочий MP3."
    )

    if download_with_ytdlp(
        youtube_url,
        filepath
    ):

        return filepath

    print()
    print("Ни один способ скачивания не сработал.")

    return None


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
    cover_url = info.get(
        "cover_url"
    )

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
        url,
        artist,
        title,
        duration,
        output_folder
    )

    if not filepath:
        return False

    # ========================================================
    # ОБЛОЖКА
    # ========================================================

    embed_cover(
        filepath,
        cover_url,
        artist,
        title,
        album
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
# PLAYLIST URL
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
# ПЛЕЙЛИСТ
# ============================================================

def process_playlist(url):

    playlist = get_playlist_tracks(
        url
    )

    if not playlist:

        print()
        print("=" * 60)
        print("НЕ УДАЛОСЬ ПОЛУЧИТЬ ПЛЕЙЛИСТ")
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
    print("ПЛЕЙЛИСТ ЗАВЕРШЁН")
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
    print("YTMUSIC DOWNLOADER")
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
        print("Введите 1 или 2.")

    print()

    url = input(
        "Ссылка на трек или плейлист "
        "YouTube Music: "
    ).strip()

    if not url:

        print()
        print("Ссылка не указана.")

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    if is_playlist_url(url):

        process_playlist(url)

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
        print("ТРЕК УСПЕШНО СКАЧАН")
        print("=" * 60)

        print()
        print(
            "Папка:",
            tracks_folder
        )

    else:

        print("=" * 60)
        print("ТРЕК НЕ СКАЧАН")
        print("=" * 60)

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
