import requests
import re
import json
import subprocess
import os
import time


# ============================================================
# НАСТРОЙКИ
# ============================================================

ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

YTDLP = os.path.join(
    ENGINE_FOLDER,
    "yt-dlp.exe"
)

TIMEOUT = 15
DOWNLOAD_TIMEOUT = 120

SEARCH_RESULTS = 10
DURATION_TOLERANCE = 3.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
}


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize(text):

    text = str(text or "").lower()

    text = text.replace("–", "-")
    text = text.replace("—", "-")

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

    candidate_words = normalize_words(
        candidate
    )

    artist_words = normalize_words(
        wanted_artist
    )

    title_words = normalize_words(
        wanted_title
    )

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

    score -= (
        len(extra_words) *
        15
    )

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


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    try:
        seconds = int(
            round(float(seconds))
        )

    except Exception:
        return "??:??"

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )


# ============================================================
# CLIENT_ID
# ============================================================

def get_client_id():

    print()
    print("=" * 60)
    print("1. ПОЛУЧЕНИЕ CLIENT_ID")
    print("=" * 60)

    response = requests.get(
        "https://soundcloud.com/",
        headers=HEADERS,
        timeout=TIMEOUT
    )

    print()
    print(
        "HTTP:",
        response.status_code
    )

    if response.status_code != 200:
        return None

    html = response.text

    patterns = [
        r'client_id["\']?\s*[:=]\s*["\']([A-Za-z0-9]{20,})["\']',
        r'client_id=([A-Za-z0-9]{20,})',
        r'"clientId":"([A-Za-z0-9]{20,})"',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:
            return match.group(1)

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        re.I
    )

    scripts = [
        url
        for url in scripts
        if (
            "sndcdn.com" in url
            or
            "soundcloud.com" in url
        )
    ]

    print(
        "JS-файлов:",
        len(scripts)
    )

    for url in scripts[:20]:

        if url.startswith("//"):
            url = "https:" + url

        elif url.startswith("/"):
            url = (
                "https://soundcloud.com"
                + url
            )

        try:

            js_response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT
            )

            if js_response.status_code != 200:
                continue

            js = js_response.text

            for pattern in patterns:

                match = re.search(
                    pattern,
                    js,
                    re.I
                )

                if match:
                    return match.group(1)

        except Exception:
            continue

    return None


# ============================================================
# ПОИСК
# ============================================================

def search_soundcloud(
    client_id,
    artist,
    title,
    duration
):

    print()
    print("=" * 60)
    print("2. ПОИСК SOUNDCLOUD API")
    print("=" * 60)

    query = (
        f"{artist} {title}"
    )

    response = requests.get(
        "https://api-v2.soundcloud.com/search/tracks",
        params={
            "q": query,
            "client_id": client_id,
            "limit": SEARCH_RESULTS,
            "offset": 0,
            "linked_partitioning": "1"
        },
        headers=HEADERS,
        timeout=TIMEOUT
    )

    print()
    print(
        "HTTP:",
        response.status_code
    )

    if response.status_code != 200:
        return None

    data = response.json()

    entries = (
        data.get("collection")
        or []
    )

    print(
        "Результатов:",
        len(entries)
    )

    candidates = []

    for entry in entries:

        if not isinstance(
            entry,
            dict
        ):
            continue

        user = (
            entry.get("user")
            or {}
        )

        found_artist = (
            user.get("username")
            or ""
        )

        found_title = (
            entry.get("title")
            or ""
        )

        url = (
            entry.get("permalink_url")
        )

        if not url:
            continue

        candidate_duration = (
            entry.get("duration")
        )

        if candidate_duration is not None:

            try:

                candidate_duration = (
                    float(candidate_duration)
                    / 1000.0
                )

            except Exception:

                candidate_duration = None

        text_score = candidate_text_score(
            (
                found_artist +
                " " +
                found_title
            ),
            artist,
            title
        )

        if text_score < 0:
            continue

        final_score = (
            text_score
            +
            duration_score(
                candidate_duration,
                duration
            )
        )

        if not is_duration_acceptable(
            candidate_duration,
            duration
        ):

            final_score -= 1000

        candidates.append({
            "url": url,
            "artist": found_artist,
            "title": found_title,
            "duration": candidate_duration,
            "score": final_score
        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    print()
    print(
        "КАНДИДАТЫ:"
    )

    for index, candidate in enumerate(
        candidates,
        1
    ):

        print()
        print(
            f"{index}. "
            f"{candidate['artist']} — "
            f"{candidate['title']}"
        )

        print(
            "   Длительность:",
            format_duration(
                candidate["duration"]
            )
        )

        print(
            "   Оценка:",
            candidate["score"]
        )

        print(
            "   URL:",
            candidate["url"]
        )

    return candidates[0]


# ============================================================
# СКАЧИВАНИЕ ЧЕРЕЗ YT-DLP
# ============================================================

def download_track(
    soundcloud_url,
    output_file
):

    print()
    print("=" * 60)
    print("3. СКАЧИВАНИЕ ЧЕРЕЗ YT-DLP")
    print("=" * 60)

    print()
    print(
        "URL:",
        soundcloud_url
    )

    print()
    print(
        "Запуск yt-dlp..."
    )

    temp_template = (
        os.path.splitext(
            output_file
        )[0]
        + ".test.%(ext)s"
    )

    command = [
        YTDLP,

        "--no-playlist",

        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",

        "--no-part",

        "-o",
        temp_template,

        soundcloud_url
    ]

    start = time.time()

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DOWNLOAD_TIMEOUT
        )

    except subprocess.TimeoutExpired:

        print()
        print(
            "ОШИБКА: скачивание "
            "превысило лимит времени."
        )

        return False

    except Exception as e:

        print()
        print(
            "ОШИБКА:",
            e
        )

        return False

    elapsed = (
        time.time() -
        start
    )

    print()
    print(
        f"Время: {elapsed:.2f} сек."
    )

    print(
        "Код:",
        result.returncode
    )

    if result.returncode != 0:

        print()
        print("STDERR:")

        print(
            result.stderr
        )

        return False

    directory = os.path.dirname(
        output_file
    )

    base = os.path.splitext(
        os.path.basename(output_file)
    )[0]

    possible_files = []

    for filename in os.listdir(
        directory
    ):

        if filename.startswith(
            base + ".test."
        ):

            possible_files.append(
                os.path.join(
                    directory,
                    filename
                )
            )

    if not possible_files:

        print()
        print(
            "Файл после скачивания "
            "не найден."
        )

        return False

    possible_files.sort(
        key=lambda x:
            os.path.getmtime(x),
        reverse=True
    )

    source_file = (
        possible_files[0]
    )

    if not os.path.isfile(
        source_file
    ):

        return False

    if (
        os.path.getsize(source_file)
        < 10 * 1024
    ):

        print(
            "Файл слишком маленький."
        )

        return False

    if os.path.exists(
        output_file
    ):

        os.remove(
            output_file
        )

    os.replace(
        source_file,
        output_file
    )

    print()
    print(
        "Файл скачан:"
    )

    print(
        output_file
    )

    print()
    print(
        "Размер:",
        round(
            os.path.getsize(
                output_file
            ) /
            1024 /
            1024,
            2
        ),
        "МБ"
    )

    return True


# ============================================================
# FFPROBE
# ============================================================

def get_duration_ffprobe(
    filename
):

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filename
    ]

    try:

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

        if not value:
            return None

        return float(value)

    except Exception:
        return None


# ============================================================
# MAIN
# ============================================================

print("=" * 60)
print("ТЕСТ 6 — ПОЛНАЯ ЦЕПОЧКА SOUNDCLOUD")
print("=" * 60)

print()
print(
    "Схема:"
)

print(
    "SoundCloud API → поиск → "
    "выбор → yt-dlp → MP3"
)

print()
print(
    "scsearch НЕ используется."
)

print()

if not os.path.isfile(YTDLP):

    print(
        "yt-dlp.exe не найден:"
    )

    print(
        YTDLP
    )

    input(
        "\nНажмите Enter для выхода..."
    )

    raise SystemExit


artist = input(
    "Исполнитель: "
).strip()

title = input(
    "Название трека: "
).strip()

duration_input = input(
    "Ожидаемая длительность "
    "(секунды, например 90.285): "
).strip()

try:

    target_duration = float(
        duration_input
    )

except Exception:

    print()
    print(
        "Некорректная длительность."
    )

    input(
        "\nНажмите Enter для выхода..."
    )

    raise SystemExit


# ============================================================
# CLIENT ID
# ============================================================

client_id = get_client_id()

if not client_id:

    print()
    print(
        "CLIENT_ID не найден."
    )

    input(
        "\nНажмите Enter для выхода..."
    )

    raise SystemExit

print()
print(
    "CLIENT_ID получен."
)


# ============================================================
# ПОИСК
# ============================================================

candidate = search_soundcloud(
    client_id,
    artist,
    title,
    target_duration
)

if not candidate:

    print()
    print("=" * 60)
    print(
        "ПОДХОДЯЩИЙ ТРЕК НЕ НАЙДЕН"
    )
    print("=" * 60)

    input(
        "\nНажмите Enter для выхода..."
    )

    raise SystemExit


# ============================================================
# ПОДТВЕРЖДЕНИЕ
# ============================================================

print()
print("=" * 60)
print("ВЫБРАННЫЙ ТРЕК")
print("=" * 60)

print()

print(
    "Исполнитель:",
    candidate["artist"]
)

print(
    "Название:",
    candidate["title"]
)

print(
    "Длительность:",
    format_duration(
        candidate["duration"]
    )
)

print(
    "URL:",
    candidate["url"]
)

print(
    "Оценка:",
    candidate["score"]
)


# ============================================================
# ФАЙЛ
# ============================================================

safe_artist = re.sub(
    r'[<>:"/\\|?*]',
    "",
    artist
).strip()

safe_title = re.sub(
    r'[<>:"/\\|?*]',
    "",
    title
).strip()

output_file = os.path.join(
    ENGINE_FOLDER,
    f"TEST - {safe_artist} - {safe_title}.mp3"
)


# ============================================================
# СКАЧИВАНИЕ
# ============================================================

success = download_track(
    candidate["url"],
    output_file
)

if not success:

    print()
    print("=" * 60)
    print(
        "ТЕСТ НЕ ПРОЙДЕН"
    )
    print("=" * 60)

    input(
        "\nНажмите Enter для выхода..."
    )

    raise SystemExit


# ============================================================
# ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================

print()
print("=" * 60)
print("4. ФИНАЛЬНАЯ ПРОВЕРКА")
print("=" * 60)

actual_duration = (
    get_duration_ffprobe(
        output_file
    )
)

print()

print(
    "Длительность исходного:",
    format_duration(
        target_duration
    )
)

print(
    "Длительность файла:",
    format_duration(
        actual_duration
    )
)

if is_duration_acceptable(
    actual_duration,
    target_duration
):

    print()
    print(
        "Длительность совпадает."
    )

else:

    print()
    print(
        "ВНИМАНИЕ: длительность "
        "не совпадает."
    )


# ============================================================
# УСПЕХ
# ============================================================

print()
print("=" * 60)
print("ТЕСТ ЗАВЕРШЁН")
print("=" * 60)

print()
print(
    "SoundCloud API:",
    "РАБОТАЕТ"
)

print(
    "Поиск:",
    "РАБОТАЕТ"
)

print(
    "Выбор кандидата:",
    "РАБОТАЕТ"
)

print(
    "yt-dlp:",
    "РАБОТАЕТ"
)

print(
    "MP3:",
    "ПОЛУЧЕН"
)

print()
print(
    "Файл:"
)

print(
    output_file
)

input(
    "\nНажмите Enter для выхода..."
)  
