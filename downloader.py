import requests
import re
import html
import base64
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

DOWNLOAD_LRC = False
LRCLIB_DELAY = 1.0

# Допуск длительности.
# 3 секунды для коротких треков обычно достаточно.
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

    text = re.sub(r"\(MP3\.tm\)", "", text, flags=re.I)
    text = re.sub(r"\(audiostart\.net\)", "", text, flags=re.I)
    text = re.sub(r"\.mp3$", "", text, flags=re.I)

    text = text.lower()

    # Варианты написания OG/OF Buda
    text = re.sub(r"\bof\s+buda\b", "og buda", text)

    # feat / featuring превращаем в одинаковый вид
    text = re.sub(r"\bfeaturing\b", "feat", text)
    text = re.sub(r"\bft\.?\b", "feat", text)

    # Убираем feat как техническое слово.
    # Сам исполнитель после feat остаётся.
    text = re.sub(r"\bfeat\.?\b", " ", text)

    text = re.sub(r"[,;|/\\]+", " ", text)
    text = re.sub(r"[()[\]{}]", " ", text)

    text = re.sub(r"\s+", " ", text)

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
# РАЗБОР ИМЕНИ КАНДИДАТА
# ============================================================

def candidate_text_score(filename, artist, title):
    """
    Основная система оценки кандидата.

    Важный принцип:
    мы не требуем, чтобы имя файла совпадало строка-в-строку.
    Сравниваем слова независимо от порядка.

    Например:

    ONDA ANDAR - red weather
    red weather ONDA ANDAR

    считаются одним и тем же треком.
    """

    candidate = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    candidate_words = normalize_words(candidate)
    artist_words = normalize_words(wanted_artist)
    title_words = normalize_words(wanted_title)

    if not artist_words or not title_words:
        return -100000

    artist_matches = artist_words & candidate_words
    title_matches = title_words & candidate_words

    artist_ratio = len(artist_matches) / len(artist_words)
    title_ratio = len(title_matches) / len(title_words)

    # Исполнитель должен совпадать хотя бы наполовину.
    if artist_ratio < 0.5:
        return -100000

    # Название тоже должно совпадать хотя бы наполовину.
    if title_ratio < 0.5:
        return -100000

    score = 0

    # ========================================================
    # ИСПОЛНИТЕЛЬ
    # ========================================================

    if artist_ratio == 1:
        score += 500
    elif artist_ratio >= 0.75:
        score += 300
    else:
        score += 100

    # ========================================================
    # НАЗВАНИЕ
    # ========================================================

    if title_ratio == 1:
        score += 500
    elif title_ratio >= 0.75:
        score += 300
    else:
        score += 100

    # ========================================================
    # ТОЧНЫЕ СОВПАДЕНИЯ
    # ========================================================

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    exact_1 = wanted_artist + " " + wanted_title
    exact_2 = wanted_title + " " + wanted_artist

    if exact_1 in candidate:
        score += 400

    if exact_2 in candidate:
        score += 350

    # ========================================================
    # ЛИШНИЕ СЛОВА
    # ========================================================

    requested_words = artist_words | title_words

    extra_words = candidate_words - requested_words

    # Небольшой штраф за дополнительные слова.
    score -= len(extra_words) * 15

    # ========================================================
    # НЕЖЕЛАТЕЛЬНЫЕ ВЕРСИИ
    # ========================================================

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

    for modifier in modifiers:
        if modifier in candidate and modifier not in normalize(artist + " " + title):
            score -= 150

    return score


def duration_score(candidate_duration, target_duration):
    if candidate_duration is None or target_duration is None:
        return 0

    difference = abs(candidate_duration - target_duration)

    if difference <= 1:
        return 500

    if difference <= 2:
        return 350

    if difference <= DURATION_TOLERANCE:
        return 200

    if difference <= 5:
        return 50

    return -500


def is_duration_acceptable(candidate_duration, target_duration):
    if candidate_duration is None or target_duration is None:
        return True

    return abs(candidate_duration - target_duration) <= DURATION_TOLERANCE


# ============================================================
# ОБЛОЖКА И ТЕГИ
# ============================================================

def embed_cover(mp3_filepath, cover_url, artist, title, album=""):

    if not MUTAGEN_AVAILABLE:
        print(
            "\n[ОШИБКА] mutagen не установлен."
            "\nВыполни: pip install mutagen"
        )
        return

    if not cover_url:
        print("\n[ВНИМАНИЕ] У трека отсутствует ссылка на обложку.")
        return

    if not PIL_AVAILABLE:
        print(
            "\n[ОШИБКА] Pillow не установлен."
            "\nВыполни: pip install Pillow"
        )
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
        else:
            cover_url = data.get("thumbnail")

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
        print("ОШИБКА:", e)
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
            "Недостаточно данных "
            "для точного поиска текста."
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
            print("Синхронизированный текст не найден.")
            return None

        lyrics = response.json().get(
            "syncedLyrics"
        )

        if not lyrics:
            print("Синхронизированный текст не найден.")
            return None

        return lyrics.strip()

    except requests.RequestException:
        print("Не удалось получить текст.")
        return None

    except Exception:
        print("Не удалось обработать текст.")
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
# PLAYLIST
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
            "title": data.get("title")
            or "YouTube Music",
            "tracks": tracks
        }

    except Exception as e:
        print()
        print(
            "Ошибка получения плейлиста:",
            e
        )
        return None


# ============================================================
# FFMPEG / FFPROBE
# ============================================================

def validate_audio_file(filename):

    if not os.path.exists(filename):
        return False

    try:

        if os.path.getsize(filename) < MIN_FILE_SIZE:
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

        data = json.loads(result.stdout)

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

        return float(value) if value else None

    except Exception:
        return None


# ============================================================
# СКАЧИВАНИЕ
# ============================================================

def download_file(
    url,
    filename,
    referer=None,
    retries=1,
    source_name=""
):

    status(
        f"Скачивание аудиофайла"
        + (f" ({source_name})..." if source_name else "...")
    )

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
                "audio/mpeg,audio/*;q=0.9,*/*;q=0.8"
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

                    if attempt < retries:
                        status(
                            "Повторная попытка скачивания..."
                        )
                        time.sleep(1)
                        continue

                    return False

                content_type = (
                    response.headers
                    .get("Content-Type", "")
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

                # HTML вместо MP3
                if (
                    "text/html" in content_type
                    or "text/plain" in content_type
                ):

                    print(
                        "Источник вернул HTML "
                        "вместо аудио."
                    )

                    if attempt < retries:
                        time.sleep(1)
                        continue

                    return False

                if total < MIN_FILE_SIZE:

                    if attempt < retries:
                        status(
                            "Получен слишком маленький файл. "
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
# MP3PARTY
# ============================================================

def search_mp3party(
    artist,
    title,
    target_duration=None
):

    status("MP3Party: поиск трека...")

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
            print(
                "MP3Party: ошибка HTTP",
                response.status_code
            )
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
                "https://dl2.mp3party.net/download/"
                + song_id
            )

            candidate = {
                "artist": found_artist,
                "title": found_title,
                "page_url": page_url,
                "url": download_url,
                "referer": page_url,
                "text_score": text_score,
                "duration": None,
                "final_score": text_score
            }

            candidates.append(candidate)

        if not candidates:
            print(
                "MP3Party: подходящие кандидаты "
                "не найдены."
            )
            return None

        # Ограничиваем количество кандидатов
        # наиболее похожими.
        candidates.sort(
            key=lambda x: x["text_score"],
            reverse=True
        )

        candidates = candidates[:10]

        print(
            "MP3Party: кандидатов:",
            len(candidates)
        )

        # Проверяем длительность кандидатов.
        for index, candidate in enumerate(
            candidates,
            1
        ):

            print(
                f"\nMP3Party: кандидат "
                f"{index}/{len(candidates)}"
            )

            print(
                "Название:",
                candidate["artist"],
                "—",
                candidate["title"]
            )

            if target_duration is not None:

                candidate_duration = get_duration(
                    candidate["url"]
                )

                candidate["duration"] = (
                    candidate_duration
                )

                print(
                    "Длительность:",
                    format_duration(
                        candidate_duration
                    )
                )

                if candidate_duration is None:
                    candidate["final_score"] -= 100
                    continue

                dscore = duration_score(
                    candidate_duration,
                    target_duration
                )

                candidate["final_score"] += dscore

                if not is_duration_acceptable(
                    candidate_duration,
                    target_duration
                ):

                    print(
                        "Длительность не совпадает."
                    )

                    candidate["final_score"] -= 1000

                else:

                    print(
                        "Длительность совпадает."
                    )

        # Удаляем явно неподходящие варианты.
        valid_candidates = [
            candidate
            for candidate in candidates
            if candidate["final_score"] > 0
        ]

        if not valid_candidates:
            print(
                "MP3Party: подходящего кандидата "
                "по параметрам нет."
            )
            return None

        valid_candidates.sort(
            key=lambda x: x["final_score"],
            reverse=True
        )

        best = valid_candidates[0]

        print()
        print(
            "MP3Party: выбран кандидат:"
        )
        print(
            best["artist"],
            "—",
            best["title"]
        )

        if best["duration"] is not None:
            print(
                "Длительность:",
                format_duration(
                    best["duration"]
                )
            )

        return {
            "url": best["url"],
            "referer": best["referer"]
        }

    except Exception as e:

        print(
            "MP3Party: ошибка поиска:",
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
            print(
                "MP3TM: страница не найдена."
            )
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

            score = candidate_text_score(
                filename,
                artist,
                title
            )

            if score < 0:
                continue

            candidates.append({
                "url": link,
                "filename": filename,
                "text_score": score,
                "duration": None,
                "final_score": score
            })

        if not candidates:
            print(
                "MP3TM: подходящих кандидатов "
                "не найдено."
            )
            return None

        candidates.sort(
            key=lambda x: x["text_score"],
            reverse=True
        )

        print(
            "MP3TM: найдено кандидатов:",
            len(candidates)
        )

        for index, candidate in enumerate(
            candidates,
            1
        ):

            print(
                f"\nMP3TM: кандидат "
                f"{index}/{len(candidates)}"
            )

            print(
                "Файл:",
                candidate["filename"]
            )

            if target_duration is not None:

                candidate_duration = get_duration(
                    candidate["url"]
                )

                candidate["duration"] = (
                    candidate_duration
                )

                print(
                    "Длительность:",
                    format_duration(
                        candidate_duration
                    )
                )

                if candidate_duration is not None:

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

                        print(
                            "Длительность "
                            "не совпадает."
                        )

                        candidate["final_score"] -= 1000

                    else:

                        print(
                            "Длительность совпадает."
                        )

        valid = [
            candidate
            for candidate in candidates
            if candidate["final_score"] > 0
        ]

        if not valid:
            print(
                "MP3TM: подходящего кандидата "
                "не осталось."
            )
            return None

        valid.sort(
            key=lambda x: x["final_score"],
            reverse=True
        )

        best = valid[0]

        print()
        print(
            "MP3TM: выбран:"
        )
        print(
            best["filename"]
        )

        return {
            "url": best["url"],
            "referer": page_url
        }

    except Exception as e:

        print(
            "MP3TM: ошибка поиска:",
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

    status("AudioStart: поиск трека...")

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
            print(
                "AudioStart: ошибка HTTP",
                response.status_code
            )
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

        candidates = []

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

                score = candidate_text_score(
                    decoded,
                    artist,
                    title
                )

                if score < 0:
                    continue

                if link.startswith("//"):
                    link = "https:" + link

                candidates.append({
                    "url": link,
                    "filename": decoded,
                    "text_score": score,
                    "duration": None,
                    "final_score": score
                })

            except Exception:
                continue

        if not candidates:
            print(
                "AudioStart: подходящих "
                "кандидатов не найдено."
            )
            return None

        candidates.sort(
            key=lambda x: x["text_score"],
            reverse=True
        )

        print(
            "AudioStart: найдено кандидатов:",
            len(candidates)
        )

        for index, candidate in enumerate(
            candidates,
            1
        ):

            print(
                f"\nAudioStart: кандидат "
                f"{index}/{len(candidates)}"
            )

            if target_duration is not None:

                candidate_duration = get_duration(
                    candidate["url"]
                )

                candidate["duration"] = (
                    candidate_duration
                )

                print(
                    "Длительность:",
                    format_duration(
                        candidate_duration
                    )
                )

                if candidate_duration is not None:

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

                        print(
                            "Длительность "
                            "не совпадает."
                        )

                    else:

                        print(
                            "Длительность совпадает."
                        )

        valid = [
            candidate
            for candidate in candidates
            if candidate["final_score"] > 0
        ]

        if not valid:
            print(
                "AudioStart: подходящего "
                "кандидата не осталось."
            )
            return None

        valid.sort(
            key=lambda x: x["final_score"],
            reverse=True
        )

        best = valid[0]

        print()
        print(
            "AudioStart: выбран кандидат:"
        )
        print(
            best["filename"]
        )

        return {
            "url": best["url"],
            "referer": "https://audiostart.net/"
        }

    except Exception as e:

        print(
            "AudioStart: ошибка поиска:",
            e
        )

        return None


# ============================================================
# РЕЗЕРВНЫЙ YT-DLP
# ============================================================

def download_with_ytdlp(
    youtube_url,
    filepath
):

    status(
        "Резервное скачивание через yt-dlp..."
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
            print(
                "yt-dlp не смог скачать трек."
            )

            if result.stderr:
                print(
                    result.stderr[-1000:]
                )

            return False

        directory = os.path.dirname(filepath)
        base = os.path.splitext(
            os.path.basename(filepath)
        )[0]

        possible_files = []

        for filename in os.listdir(directory):

            if filename.startswith(
                base + ".yt-dlp.tmp."
            ):
                possible_files.append(
                    os.path.join(
                        directory,
                        filename
                    )
                )

        if not possible_files:
            print(
                "yt-dlp не создал аудиофайл."
            )
            return False

        source_file = possible_files[0]

        if not validate_audio_file(
            source_file
        ):
            print(
                "Файл yt-dlp не прошёл проверку."
            )

            try:
                os.remove(source_file)
            except Exception:
                pass

            return False

        if os.path.exists(filepath):
            os.remove(filepath)

        os.replace(
            source_file,
            filepath
        )

        print(
            "Резервный файл yt-dlp готов."
        )

        return True

    except Exception as e:

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
    youtube_url
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
            retries=MP3PARTY_RETRIES,
            source_name="MP3Party"
        ):
            return filepath

        print(
            "\nMP3Party: рабочий файл "
            "не получен."
        )

    else:

        print(
            "\nMP3Party: подходящий "
            "кандидат не найден."
        )

    # ========================================================
    # 2. MP3TM
    # ========================================================

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
            retries=2,
            source_name="MP3TM"
        ):
            return filepath

        print(
            "\nMP3TM: рабочий файл "
            "не получен."
        )

    else:

        print(
            "\nMP3TM: подходящий "
            "кандидат не найден."
        )

    # ========================================================
    # 3. AUDIOSTART
    # ========================================================

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
            retries=2,
            source_name="AudioStart"
        ):
            return filepath

        print(
            "\nAudioStart: рабочий файл "
            "не получен."
        )

    else:

        print(
            "\nAudioStart: подходящий "
            "кандидат не найден."
        )

    # ========================================================
    # 4. YT-DLP
    # ========================================================

    print()
    print(
        "Все внешние источники "
        "не дали рабочий файл."
    )

    if download_with_ytdlp(
        youtube_url,
        filepath
    ):
        return filepath

    # ========================================================

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
        duration,
        output_folder,
        url
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
# URL
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
        print(
            "Введите 1 или 2."
        )

    print()

    url = input(
        "Ссылка на трек или "
        "плейлист YouTube Music: "
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
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
