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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

TIMEOUT = 20


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

        text = html.unescape(response.text)

        candidates = []

        # Ищем каждый блок трека, содержащий кнопку скачивания.
        blocks = re.findall(
            r'(<div[^>]+class="[^"]*track[^"]*"[^>]*>.*?'
            r'<a[^>]+class="[^"]*btn-dl-track[^"]*"[^>]+href="'
            r'([^"]*?/getmp3/[^"]+)"[^>]*>.*?</div>)',
            text,
            re.I | re.S
        )

        # Если структура блока изменилась, используем более
        # простой поиск ссылок и анализируем окружающий HTML.
        if not blocks:
            for match in re.finditer(
                r'<a[^>]+class="[^"]*btn-dl-track[^"]*"[^>]+href="'
                r'([^"]*?/getmp3/[^"]+)"',
                text,
                re.I
            ):
                start = max(0, match.start() - 2500)
                end = min(len(text), match.end() + 2500)

                blocks.append((
                    text[start:end],
                    match.group(1)
                ))

        for block, raw_link in blocks:

            try:
                # -------------------------------------------------
                # Нормализация ссылки
                # -------------------------------------------------
                link = html.unescape(raw_link)

                if link.startswith("//"):
                    link = "https:" + link
                elif link.startswith("/"):
                    link = "https://audiostart.net" + link

                # -------------------------------------------------
                # Исполнитель
                # -------------------------------------------------
                artist_match = re.search(
                    r'<div[^>]+class="[^"]*artist[^"]*"[^>]*>.*?'
                    r'<a[^>]*>(.*?)</a>',
                    block,
                    re.I | re.S
                )

                found_artist = ""
                if artist_match:
                    found_artist = re.sub(
                        r"<[^>]+>",
                        " ",
                        artist_match.group(1)
                    )
                    found_artist = html.unescape(
                        found_artist
                    ).strip()

                # -------------------------------------------------
                # Название
                # -------------------------------------------------
                title_match = re.search(
                    r'<div[^>]+class="[^"]*track-name[^"]*"[^>]*>.*?'
                    r'<a[^>]*>(.*?)</a>',
                    block,
                    re.I | re.S
                )

                found_title = ""
                if title_match:
                    found_title = re.sub(
                        r"<[^>]+>",
                        " ",
                        title_match.group(1)
                    )
                    found_title = html.unescape(
                        found_title
                    ).strip()

                # -------------------------------------------------
                # Запасной вариант: ищем itemprop=name
                # -------------------------------------------------
                if not found_title:
                    name_match = re.search(
                        r'<[^>]+itemprop=["\']name["\'][^>]*>'
                        r'(.*?)</',
                        block,
                        re.I | re.S
                    )

                    if name_match:
                        found_title = re.sub(
                            r"<[^>]+>",
                            " ",
                            name_match.group(1)
                        )
                        found_title = html.unescape(
                            found_title
                        ).strip()

                # -------------------------------------------------
                # Длительность со страницы
                # -------------------------------------------------
                duration = None

                duration_match = re.search(
                    r'class=["\'][^"\']*track-meta[^"\']*["\'][^>]*>'
                    r'(?:.*?)(\d{1,2}):(\d{2})',
                    block,
                    re.I | re.S
                )

                if duration_match:
                    minutes = int(
                        duration_match.group(1)
                    )
                    seconds = int(
                        duration_match.group(2)
                    )

                    duration = (
                        minutes * 60
                        + seconds
                    )

                # -------------------------------------------------
                # Если HTML блока не дал название,
                # пробуем декодировать getmp3 для дополнительной
                # информации.
                # -------------------------------------------------
                decoded = ""

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
                except Exception:
                    pass

                comparison_text = (
                    f"{found_artist} {found_title}"
                ).strip()

                if not comparison_text:
                    comparison_text = decoded

                # -------------------------------------------------
                # Оценка совпадения
                # -------------------------------------------------
                score = candidate_text_score(
                    comparison_text,
                    artist,
                    title
                )

                if score < 0:
                    continue

                # -------------------------------------------------
                # Проверка длительности
                # -------------------------------------------------
                if not is_duration_acceptable(
                    duration,
                    target_duration
                ):
                    continue

                candidates.append({
                    "url": link,
                    "referer": (
                        "https://audiostart.net/"
                    ),
                    "score": score,
                    "duration": duration,
                    "artist": found_artist,
                    "title": found_title
                })

            except Exception:
                continue

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best = candidates[0]

        return {
            "url": best["url"],
            "referer": best["referer"]
        }

    except Exception:
        return None
