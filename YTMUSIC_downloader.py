import requests
import re
import html
import base64
import json
import subprocess
import os
import tempfile
from urllib.parse import unquote


# ============================================================
# НАСТРОЙКИ
# ============================================================

YTDLP = r"C:\Users\Константин\OneDrive\Desktop\Youtube Music Downloader\yt-dlp.exe"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 20

MIN_FILE_SIZE = 10 * 1024


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================

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
        r"\s+",
        " ",
        text
    )

    return text.strip().lower()


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

    text = text.strip()

    return text


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
# YOUTUBE MUSIC — ПОЛУЧЕНИЕ ИНФОРМАЦИИ
# ============================================================

def get_youtube_music_info(url):

    print()
    print("Получение информации из YouTube Music...")
    print()

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

            print("Ошибка yt-dlp:")
            print()

            if result.stderr:
                print(result.stderr)

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

        duration = data.get("duration")

        if not artist or not title:

            print(
                "Не удалось определить "
                "исполнителя или название."
            )

            return None

        return {
            "artist": artist,
            "title": title,
            "duration": duration
        }

    except FileNotFoundError:

        print()
        print("ОШИБКА")
        print("yt-dlp.exe не найден:")
        print(YTDLP)

        return None

    except json.JSONDecodeError:

        print()
        print("ОШИБКА")
        print(
            "yt-dlp не вернул корректные данные."
        )

        return None

    except subprocess.TimeoutExpired:

        print()
        print(
            "ОШИБКА: yt-dlp слишком долго "
            "получает данные."
        )

        return None

    except Exception as e:

        print()
        print("ОШИБКА:")
        print(e)

        return None


# ============================================================
# YOUTUBE MUSIC — ПОЛУЧЕНИЕ ПЛЕЙЛИСТА
# ============================================================

def get_playlist_tracks(url):

    print()
    print("Получение списка треков плейлиста...")
    print()

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

            print("Ошибка yt-dlp:")

            if result.stderr:
                print(result.stderr)

            return None

        data = json.loads(result.stdout)

        entries = data.get("entries") or []

        tracks = []

        for entry in entries:

            if not entry:
                continue

            track_url = (
                entry.get("webpage_url")
                or entry.get("url")
                or entry.get("original_url")
            )

            if not track_url:
                continue

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
# FFPROBE — ПРОВЕРКА АУДИО
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
# ДЛИТЕЛЬНОСТЬ MP3 ПО URL
# ============================================================

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

        if not value:
            return None

        return float(value)

    except Exception:

        return None


# ============================================================
# СКАЧИВАНИЕ С ПРОВЕРКОЙ
# ============================================================

def download_file(url, filename):

    print()
    print("Скачивание...")

    temp_filename = filename + ".tmp"

    try:

        if os.path.exists(temp_filename):
            os.remove(temp_filename)

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=60,
            stream=True,
            allow_redirects=True
        )

        if r.status_code != 200:

            print(
                "Ошибка скачивания. HTTP:",
                r.status_code
            )

            return False

        content_type = r.headers.get(
            "Content-Type",
            ""
        ).lower()

        total = 0

        with open(temp_filename, "wb") as f:

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

        # ----------------------------------------------------
        # Проверяем размер
        # ----------------------------------------------------

        if total < MIN_FILE_SIZE:

            print()
            print(
                "ОШИБКА: сервер вернул "
                "пустой или слишком маленький файл."
            )

            if os.path.exists(temp_filename):
                os.remove(temp_filename)

            return False

        # ----------------------------------------------------
        # Проверяем настоящий аудиофайл
        # ----------------------------------------------------

        print(
            "Проверка аудиофайла..."
        )

        if not validate_audio_file(
            temp_filename
        ):

            print()
            print(
                "ОШИБКА: скачанный файл "
                "не является корректным "
                "воспроизводимым аудио."
            )

            if os.path.exists(temp_filename):
                os.remove(temp_filename)

            return False

        # ----------------------------------------------------
        # Всё хорошо
        # ----------------------------------------------------

        if os.path.exists(filename):
            os.remove(filename)

        os.replace(
            temp_filename,
            filename
        )

        print()
        print("ГОТОВО")
        print("Файл:", filename)
        print(
            "Размер:",
            round(
                total / 1024 / 1024,
                2
            ),
            "МБ"
        )

        return True

    except Exception as e:

        print()
        print(
            "Ошибка скачивания:",
            e
        )

        if os.path.exists(temp_filename):

            try:
                os.remove(temp_filename)
            except Exception:
                pass

        return False


# ============================================================
# MP3PARTY
# ============================================================

def search_mp3party(artist, title):

    print()
    print("[1/3] MP3Party")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://mp3party.net/search",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print(
                "HTTP:",
                r.status_code
            )

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

        print(
            "Найдено результатов:",
            len(results)
        )

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
                == wanted_artist
                and
                normalize(found_title)
                == wanted_title
            ):

                url = (
                    "https://dl2.mp3party.net/download/"
                    + song_id
                )

                print()
                print("ТОЧНОЕ СОВПАДЕНИЕ")
                print(
                    "Исполнитель:",
                    found_artist
                )
                print(
                    "Название:   ",
                    found_title
                )
                print(
                    "ID:",
                    song_id
                )
                print(
                    "Ссылка:",
                    url
                )

                return url

        print(
            "Точное совпадение не найдено."
        )

    except Exception as e:

        print(
            "Ошибка MP3Party:",
            e
        )

    return None


# ============================================================
# ОЦЕНКА MP3TM
# ============================================================

def score_mp3tm_candidate(
    filename,
    artist,
    title
):

    name = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    score = 0

    if wanted_artist in name:

        score += 100

    else:

        return -10000

    if wanted_title in name:

        score += 100

    else:

        return -10000

    exact_phrase = (
        wanted_artist
        + " - "
        + wanted_title
    )

    if exact_phrase in name:

        score += 300

    reverse_phrase = (
        wanted_title
        + " - "
        + wanted_artist
    )

    if reverse_phrase in name:

        score += 200

    remaining = name

    remaining = remaining.replace(
        wanted_artist,
        "",
        1
    )

    remaining = remaining.replace(
        wanted_title,
        "",
        1
    )

    remaining = re.sub(
        r"\s*-\s*",
        " ",
        remaining
    )

    remaining = re.sub(
        r"\s+",
        " ",
        remaining
    ).strip()

    score -= len(remaining) * 2

    expected = (
        wanted_artist
        + " "
        + wanted_title
    )

    if normalize(name) == normalize(expected):

        score += 500

    modifiers = [
        "nightcore",
        "remix",
        "slowed",
        "sped up",
        "speed up",
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
        "phonk"
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

            score -= 80

    return score


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):

    print()
    print("[2/3] MP3TM")

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

            print(
                "HTTP:",
                r.status_code
            )

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

        print(
            "Найдено MP3-ссылок:",
            len(links)
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

            print(
                "Точное совпадение не найдено."
            )

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

        # ----------------------------------------------------
        # Проверяем длительность кандидатов
        # ----------------------------------------------------

        for candidate in top_candidates[:10]:

            candidate["duration"] = get_duration(
                candidate["url"]
            )

        # ----------------------------------------------------
        # Выбираем по длительности
        # ----------------------------------------------------

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
                        - target_duration
                    )
                )

                best = valid[0]

            else:

                best = top_candidates[0]

        else:

            best = top_candidates[0]

        # ----------------------------------------------------
        # Вывод одинаковых кандидатов
        # ----------------------------------------------------

        if len(top_candidates) > 1:

            print()
            print(
                "НАЙДЕНО ВАРИАНТОВ "
                "С ОДИНАКОВЫМ СОВПАДЕНИЕМ:",
                len(top_candidates)
            )

            for i, candidate in enumerate(
                top_candidates[:10],
                1
            ):

                duration_text = format_duration(
                    candidate["duration"]
                )

                print(
                    f"{i}. "
                    f"{candidate['filename']} "
                    f"[{duration_text}]"
                )

        # ----------------------------------------------------
        # Близкие по длительности
        # ----------------------------------------------------

        if target_duration is not None:

            valid_all = [
                c
                for c in candidates
                if c["duration"] is not None
            ]

            close = []

            for candidate in valid_all:

                difference = abs(
                    candidate["duration"]
                    - target_duration
                )

                if difference <= 10:

                    close.append(
                        candidate
                    )

            close.sort(
                key=lambda c:
                abs(
                    c["duration"]
                    - target_duration
                )
            )

            if close:

                print()
                print(
                    "ВАРИАНТЫ С БЛИЗКИМ "
                    "СОВПАДЕНИЕМ:"
                )

                for i, candidate in enumerate(
                    close[:10],
                    1
                ):

                    print(
                        f"{i}. "
                        f"{candidate['filename']} "
                        f"["
                        f"{format_duration(candidate['duration'])}"
                        f"]"
                    )

        # ----------------------------------------------------
        # Лучший кандидат
        # ----------------------------------------------------

        print()
        print(
            "НАЙДЕН НАИЛУЧШИЙ КАНДИДАТ"
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
            "Длительность:",
            format_duration(
                best["duration"]
            )
        )

        if target_duration is not None:

            difference = abs(
                best["duration"]
                - target_duration
            )

            print(
                "Разница:",
                format_duration(
                    difference
                )
            )

        print(
            "URL:",
            best["url"]
        )

        return best["url"]

    except Exception as e:

        print(
            "Ошибка MP3TM:",
            e
        )

    return None


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(
    artist,
    title
):

    print()
    print("[3/3] AudioStart")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://audiostart.net/",
            params={"song": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print(
                "HTTP:",
                r.status_code
            )

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

        print(
            "Найдено ссылок:",
            len(links)
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
                    in decoded_normalized
                    and
                    wanted_title
                    in decoded_normalized
                ):

                    if link.startswith("//"):

                        link = (
                            "https:"
                            + link
                        )

                    print()
                    print(
                        "ТОЧНОЕ СОВПАДЕНИЕ"
                    )

                    print(
                        "Исполнитель:",
                        artist
                    )

                    print(
                        "Название:   ",
                        title
                    )

                    return link

            except Exception:

                continue

        print(
            "Точное совпадение не найдено."
        )

    except Exception as e:

        print(
            "Ошибка AudioStart:",
            e
        )

    return None


# ============================================================
# ПОИСК И СКАЧИВАНИЕ ОДНОГО ТРЕКА
# ============================================================

def find_and_download_track(
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

    # --------------------------------------------------------
    # 1. MP3PARTY
    # --------------------------------------------------------

    url = search_mp3party(
        artist,
        title
    )

    if url:

        print()
        print("=" * 50)
        print(
            "ВЫБРАН ИСТОЧНИК: MP3PARTY"
        )
        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filepath
        ):

            return True

        print()
        print(
            "MP3Party вернул некорректный "
            "файл."
        )

        print(
            "Переходим к следующему источнику..."
        )

    # --------------------------------------------------------
    # 2. MP3TM
    # --------------------------------------------------------

    url = search_mp3tm(
        artist,
        title,
        duration
    )

    if url:

        print()
        print("=" * 50)
        print(
            "ВЫБРАН ИСТОЧНИК: MP3TM"
        )
        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filepath
        ):

            return True

        print()
        print(
            "MP3TM вернул некорректный "
            "файл."
        )

        print(
            "Переходим к следующему источнику..."
        )

    # --------------------------------------------------------
    # 3. AUDIOSTART
    # --------------------------------------------------------

    url = search_audiostart(
        artist,
        title
    )

    if url:

        print()
        print("=" * 50)
        print(
            "ВЫБРАН ИСТОЧНИК: AUDIOSTART"
        )
        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filepath
        ):

            return True

        print()
        print(
            "AudioStart вернул некорректный "
            "файл."
        )

    # --------------------------------------------------------
    # НЕ НАЙДЕНО / НЕ СКАЧАНО
    # --------------------------------------------------------

    print()
    print("=" * 50)
    print(
        "ТРЕК НЕ СКАЧАН"
    )
    print("=" * 50)

    return False


# ============================================================
# ОПРЕДЕЛЕНИЕ: ТРЕК ИЛИ ПЛЕЙЛИСТ
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
    duration = info["duration"]

    print()
    print("=" * 50)
    print("ТРЕК YOUTUBE MUSIC")
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

    print(
        "Длительность:",
        format_duration(duration)
    )

    return find_and_download_track(
        artist,
        title,
        duration,
        output_folder
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

    desktop = os.path.dirname(
        os.path.abspath(__file__)
    )

    output_folder = os.path.join(
        desktop,
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

    print(
        "Папка:",
        output_folder
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

    print("=" * 60)
    print("YTMUSIC DOWNLOADER")
    print("=" * 60)
    print()

    url = input(
        "Ссылка на трек или плейлист YouTube Music: "
    ).strip()

    if not url:

        print(
            "Ссылка не указана."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

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
    # ОДИН ТРЕК
    # --------------------------------------------------------

    desktop = os.path.dirname(
        os.path.abspath(__file__)
    )

    output_folder = desktop

    success = process_single_track(
        url,
        output_folder
    )

    print()

    if success:

        print("=" * 60)
        print(
            "ТРЕК УСПЕШНО СКАЧАН"
        )
        print("=" * 60)

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
