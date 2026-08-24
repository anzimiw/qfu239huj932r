# -*- coding: utf-8 -*-

"""
CENSURU.NET — ОБЩИЕ ФУНКЦИИ ИСТОЧНИКОВ

Общая логика для:
    sources_mp3party.py
    sources_mp3tm.py
    sources_audiostart.py

Источник-специфичная логика поиска находится
в соответствующем sources_*.py.
"""

import html
import os
import re
import subprocess

from urllib.parse import unquote


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
# SETTINGS
# ============================================================

DURATION_TOLERANCE = 3.0


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    text = html.unescape(
        str(text)
    )

    text = unquote(
        text
    )

    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
        .replace("_", " ")
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
# FILENAME
# ============================================================

def clean_filename(text):
    text = unquote(
        text
    )

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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================================
# CANDIDATE SCORING
# ============================================================

def candidate_text_score(
    filename,
    artist,
    title
):
    """
    Общая оценка кандидата для:

        MP3Party
        MP3TM
        AudioStart

    SoundCloud использует отдельную
    soundcloud_candidate_score().
    """

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
        or not title_words
    ):
        return -100000

    artist_ratio = (
        len(
            artist_words
            & candidate_words
        )
        / len(artist_words)
    )

    title_ratio = (
        len(
            title_words
            & candidate_words
        )
        / len(title_words)
    )

    if (
        artist_ratio < 0.5
        or title_ratio < 0.5
    ):
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
