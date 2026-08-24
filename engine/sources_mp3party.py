# Censuru.net — MP3Party source
# Логика MP3Party, вынесенная из downloader.py.
#
# Модуль автономный и не импортирует downloader.py.


import os
import re
import html
import subprocess

import requests


# ============================================================
# PATHS
# ============================================================

ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)


# ============================================================
# HTTP
# ============================================================

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


# ============================================================
# SETTINGS
# ============================================================

TIMEOUT = 20

DURATION_TOLERANCE = 3.0


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    text = html.unescape(
        str(text)
    )

    text = re.sub(
        r"[\u2013\u2014]",
        "-",
        text
    )

    text = text.replace(
        "_",
        " "
    )

    text = re.sub(
        r"\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.lower()

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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def normalize_words(text):
    return {
        word
        for word in normalize(text).split()
        if word
    }


# ============================================================
# CANDIDATE SCORING
# ============================================================

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

    artist_ratio = (
        len(artist_words & candidate_words)
        / len(artist_words)
    )

    title_ratio = (
        len(title_words & candidate_words)
        / len(title_words)
    )

    if artist_ratio < 0.5 or title_ratio < 0.5:
        return -100000

    score = 0

    score += (
        500
        if artist_ratio == 1
        else 300
        if artist_ratio >= 0.75
        else 100
    )

    score += (
        500
        if title_ratio == 1
        else 300
        if title_ratio >= 0.75
        else 100
    )

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    if (
        wanted_artist
        + " "
        + wanted_title
        in candidate
    ):
        score += 400

    if (
        wanted_title
        + " "
        + wanted_artist
        in candidate
    ):
        score += 350

    score -= (
        len(
            candidate_words
            - (
                artist_words
                | title_words
            )
        )
        * 15
    )

    return score


# ============================================================
# DURATION
# ============================================================

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


# ============================================================
# MP3PARTY SEARCH
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
