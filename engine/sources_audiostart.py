# -*- coding: utf-8 -*-

"""
CENSURU.NET — ИСТОЧНИК AUDIOSTART

Поиск и выбор треков AudioStart.

Логика вынесена из downloader.py.
"""

from urllib.parse import unquote

# ============================================================
# ОБЩИЕ ФУНКЦИИ, НЕОБХОДИМЫЕ AUDIOSTART
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

    artist_ratio = len(artist_words & candidate_words) / len(artist_words)
    title_ratio = len(title_words & candidate_words) / len(title_words)

    if artist_ratio < 0.5 or title_ratio < 0.5:
        return -100000

    score = 0
    score += 500 if artist_ratio == 1 else 300 if artist_ratio >= 0.75 else 100
    score += 500 if title_ratio == 1 else 300 if title_ratio >= 0.75 else 100

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    if wanted_artist + " " + wanted_title in candidate:
        score += 400

    if wanted_title + " " + wanted_artist in candidate:
        score += 350

    score -= len(candidate_words - (artist_words | title_words)) * 15

    return score

# ============================================================
# AUDIOSTART SEARCH
# ============================================================

def search_audiostart(
    artist,
    title,
    target_duration=None
):
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
            return None

        links = list(
            dict.fromkeys(
                re.findall(
                    r'href=["\']'
                    r'([^"\']*?/getmp3/[^"\']+)'
                    r'["\']',
                    html.unescape(
                        response.text
                    ),
                    re.I
                )
            )
        )

        candidates = []

        for link in links:
            try:
                encoded = link.split(
                    "/getmp3/",
                    1
                )[1]

                decoded = unquote(
                    base64.b64decode(
                        encoded
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )
                )

                score = candidate_text_score(
                    decoded,
                    artist,
                    title
                )

                if score >= 0:
                    if link.startswith("//"):
                        link = (
                            "https:"
                            + link
                        )

                    elif link.startswith("/"):
                        link = (
                            "https://audiostart.net"
                            + link
                        )

                    candidates.append(
                        (score, link)
                    )

            except Exception:
                continue

        candidates.sort(
            reverse=True
        )

        for _, link in candidates:
            duration = get_duration(
                link
            )

            if is_duration_acceptable(
                duration,
                target_duration
            ):
                return {
                    "url": link,
                    "referer": (
                        "https://audiostart.net/"
                    )
                }

    except Exception:
        pass

    return None
