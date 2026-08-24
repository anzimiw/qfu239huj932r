# -*- coding: utf-8 -*-

"""
CENSURU.NET — ИСТОЧНИК MP3TM

Поиск и выбор треков MP3TM.

Логика вынесена из downloader.py.
"""

import requests
import re
import html

from sources_utils import clean_filename, candidate_text_score, is_duration_acceptable, get_duration



# ============================================================
# ОБЩИЕ ФУНКЦИИ, НЕОБХОДИМЫЕ MP3TM
# ============================================================


# ============================================================
# MP3TM SEARCH
# ============================================================

def search_mp3tm(
    artist,
    title,
    target_duration=None
):
    query = (
        f"{artist} {title}"
    )

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip(
        "-"
    ).lower()

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

        links = list(
            dict.fromkeys(
                re.findall(
                    r'https?://[^"\']+\.mp3'
                    r'(?:\?[^"\']*)?',
                    html.unescape(
                        response.text
                    ),
                    re.I
                )
            )
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

            if score >= 0:
                candidates.append(
                    (score, link)
                )

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
                    "referer": page_url
                }

    except Exception:
        pass

    return None
