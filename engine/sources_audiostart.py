# -*- coding: utf-8 -*-

"""
CENSURU.NET — ИСТОЧНИК AUDIOSTART

Поиск и выбор треков AudioStart.

Логика вынесена из downloader.py.
"""

import requests
import re
import html
import base64

from sources_utils import candidate_text_score, is_duration_acceptable, get_duration



from urllib.parse import unquote

# ============================================================
# ОБЩИЕ ФУНКЦИИ, НЕОБХОДИМЫЕ AUDIOSTART
# ============================================================


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
