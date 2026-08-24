
from sources_utils import candidate_text_score, is_duration_acceptable, get_duration


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


# ============================================================
# CANDIDATE SCORING
# ============================================================


# ============================================================
# DURATION
# ============================================================


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
