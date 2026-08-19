import requests
import re
import html
import base64
import json
import subprocess
from urllib.parse import unquote


# ============================================================
# НАСТРОЙКИ
# ============================================================

YTDLP = r"C:\Users\Константин\OneDrive\Desktop\Youtube Music Downloader\yt-dlp.exe"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 20


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
        text
    )

    return text.strip()


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    seconds = int(round(float(seconds)))

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


# ============================================================
# YOUTUBE MUSIC
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

            print("Не удалось определить исполнителя или название.")

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
        print("yt-dlp не вернул корректные данные.")

        return None

    except subprocess.TimeoutExpired:

        print()
        print("ОШИБКА: yt-dlp слишком долго получает данные.")

        return None

    except Exception as e:

        print()
        print("ОШИБКА:")
        print(e)

        return None


# ============================================================
# ДЛИТЕЛЬНОСТЬ MP3
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
# СКАЧИВАНИЕ
# ============================================================

def download_file(url, filename):

    print()
    print("Скачивание...")

    try:

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

        if (
            "audio" not in content_type
            and "octet-stream" not in content_type
        ):

            print(
                "Ошибка: сервер не вернул аудиофайл."
            )

            print(
                "Content-Type:",
                content_type
            )

            return False

        total = 0

        with open(filename, "wb") as f:

            for chunk in r.iter_content(
                chunk_size=262144
            ):

                if chunk:

                    f.write(chunk)
                    total += len(chunk)

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

        print("Ошибка:", e)

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

    # --------------------------------------------------------
    # Исполнитель
    # --------------------------------------------------------

    if wanted_artist in name:
        score += 100
    else:
        return -10000

    # --------------------------------------------------------
    # Название
    # --------------------------------------------------------

    if wanted_title in name:
        score += 100
    else:
        return -10000

    # --------------------------------------------------------
    # Точное сочетание
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Проверяем лишний текст
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Полное совпадение
    # --------------------------------------------------------

    expected = (
        wanted_artist
        + " "
        + wanted_title
    )

    if normalize(name) == normalize(expected):
        score += 500

    # --------------------------------------------------------
    # Дополнительные версии
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Находим группу лучших кандидатов
        # ----------------------------------------------------

        top_score = candidates[0]["score"]

        top_candidates = [
            c
            for c in candidates
            if c["score"] == top_score
        ]

        # ----------------------------------------------------
        # Проверяем длительность лучших
        # ----------------------------------------------------

        for candidate in top_candidates[:10]:

            candidate["duration"] = get_duration(
                candidate["url"]
            )

        # ----------------------------------------------------
        # Если есть целевая длительность,
        # выбираем ближайший вариант.
        # --------------------------------------------------------

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
        # Вывод кандидатов
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
        # Близкие варианты
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
                format_duration(difference)
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
# ПОИСК ТРЕКА
# ============================================================

def find_track(
    artist,
    title,
    duration
):

    # --------------------------------------------------------
    # MP3PARTY
    # --------------------------------------------------------

    url = search_mp3party(
        artist,
        title
    )

    if url:

        return (
            url,
            "MP3PARTY"
        )

    # --------------------------------------------------------
    # MP3TM
    # --------------------------------------------------------

    url = search_mp3tm(
        artist,
        title,
        duration
    )

    if url:

        return (
            url,
            "MP3TM"
        )

    # --------------------------------------------------------
    # AUDIOSTART
    # --------------------------------------------------------

    url = search_audiostart(
        artist,
        title
    )

    if url:

        return (
            url,
            "AUDIOSTART"
        )

    return (
        None,
        None
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 50)
    print("YTMUSIC DOWNLOADER")
    print("=" * 50)
    print()

    url = input(
        "Ссылка на трек YouTube Music: "
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
    # Получаем данные YouTube Music
    # --------------------------------------------------------

    info = get_youtube_music_info(
        url
    )

    if not info:

        input(
            "\nНажмите Enter для выхода..."
        )

        return

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

    print()
    print("=" * 50)
    print(
        "Ищем:",
        artist,
        "—",
        title
    )
    print("=" * 50)

    # --------------------------------------------------------
    # Ищем MP3
    # --------------------------------------------------------

    download_url, source = find_track(
        artist,
        title,
        duration
    )

    if not download_url:

        print()
        print("=" * 50)
        print(
            "ТРЕК НЕ НАЙДЕН"
        )
        print("=" * 50)

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # Имя файла
    # --------------------------------------------------------

    filename = (
        f"{safe_filename(artist)} - "
        f"{safe_filename(title)}.mp3"
    )

    # --------------------------------------------------------
    # Источник
    # --------------------------------------------------------

    print()
    print("=" * 50)

    print(
        "ВЫБРАН ИСТОЧНИК:",
        source
    )

    print("=" * 50)

    print(
        "URL:",
        download_url
    )

    # --------------------------------------------------------
    # Скачивание
    # --------------------------------------------------------

    download_file(
        download_url,
        filename
    )

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
