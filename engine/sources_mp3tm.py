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


# ------------------------------------------------------------
# MP3TM SETTINGS
# ------------------------------------------------------------

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

TIMEOUT = 20

def search_mp3tm(
    artist,
    title,
    target_duration=None
):
    """
    Поиск трека на MP3TM.

    MP3TM сейчас отдаёт прямой MP3 URL не в href,
    а в data-url атрибуте элемента __adv_stream.

    Дополнительно из HTML извлекаются:
        - исполнитель;
        - название;
        - длительность.

    После текстового отбора обязательно проверяется
    реальная длительность прямого MP3 URL.
    """

    query = (
        f"{artist} {title}"
    )

    # --------------------------------------------------------
    # Формируем hostname MP3TM
    # --------------------------------------------------------

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip("-").lower()

    if not slug:
        return None

    page_url = (
        f"https://{slug}.mp3tm.net/"
    )

    try:
        response = requests.get(
            page_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

    except Exception:
        return None

    if response.status_code != 200:
        return None

    text = html.unescape(
        response.text
    )

    # --------------------------------------------------------
    # Ищем playlist-блоки MP3TM.
    #
    # Внутри блока находится:
    #
    # data-url="...mp3"
    #
    # и отдельно:
    #
    # __adv_artist
    # __adv_name
    # playlist-duration
    # --------------------------------------------------------

    block_pattern = re.compile(
        r'<div\s+class="playlist-btn"'
        r'.*?'
        r'<a[^>]+class="[^"]*playlist-play[^"]*__adv_stream[^"]*"'
        r'[^>]+data-url="([^"]+)"'
        r'.*?'
        r'<div\s+class="playlist-name"'
        r'.*?'
        r'class="[^"]*playlist-name-artist[^"]*"'
        r'.*?'
        r'<a[^>]*>(.*?)</a>'
        r'.*?'
        r'class="[^"]*playlist-name-title[^"]*"'
        r'.*?'
        r'<a[^>]*>(.*?)</a>'
        r'.*?'
        r'<span\s+class="playlist-duration"'
        r'[^>]*>([^<]+)</span>',
        re.I | re.S
    )

    candidates = []

    for match in block_pattern.finditer(text):

        mp3_url = html.unescape(
            match.group(1).strip()
        )

        found_artist = re.sub(
            r"<[^>]+>",
            " ",
            match.group(2)
        )

        found_title = re.sub(
            r"<[^>]+>",
            " ",
            match.group(3)
        )

        found_duration = (
            match.group(4)
            .strip()
        )

        found_artist = html.unescape(
            found_artist
        )

        found_title = html.unescape(
            found_title
        )

        # Убираем HTML и лишние пробелы.
        found_artist = re.sub(
            r"\s+",
            " ",
            found_artist
        ).strip()

        found_title = re.sub(
            r"\s+",
            " ",
            found_title
        ).strip()

        # Убираем <em>, если он каким-то образом остался.
        found_title = re.sub(
            r"</?em[^>]*>",
            "",
            found_title,
            flags=re.I
        ).strip()

        # ----------------------------------------------------
        # Защита от мусора
        # ----------------------------------------------------

        if not mp3_url.lower().endswith(".mp3"):
            continue

        if not found_artist or not found_title:
            continue

        # ----------------------------------------------------
        # Текстовая оценка
        # ----------------------------------------------------

        score = candidate_text_score(
            f"{found_artist} - {found_title}",
            artist,
            title
        )

        if score < 0:
            continue

        # ----------------------------------------------------
        # Версия трека
        #
        # Не отбрасываем её сразу, потому что score уже
        # учитывает совпадение. Но сохраняем информацию
        # для дополнительного ранжирования.
        # ----------------------------------------------------

        lowered_title = found_title.lower()

        modifier_penalty = 0

        modifiers = (
            "slowed",
            "slowed + reverb",
            "slowed reverb",
            "speed up",
            "sped up",
            "nightcore",
            "remix",
            "remastered",
            "remaster",
            "rework",
            "bootleg",
            "edit",
            "live",
            "acoustic",
            "instrumental",
            "mashup",
            "extended",
            "radio edit",
            "version",
            "mix"
        )

        for modifier in modifiers:
            if modifier in lowered_title:
                modifier_penalty += 100

        # ----------------------------------------------------
        # Длительность, указанная самой страницей
        # ----------------------------------------------------

        page_duration = None

        duration_match = re.match(
            r"^\s*(\d+):(\d{1,2})\s*$",
            found_duration
        )

        if duration_match:
            page_duration = (
                int(duration_match.group(1)) * 60
                + int(duration_match.group(2))
            )

        duration_difference = None

        if (
            target_duration is not None
            and page_duration is not None
        ):
            try:
                duration_difference = abs(
                    float(page_duration)
                    - float(target_duration)
                )
            except Exception:
                duration_difference = None

        # Если сама страница показывает явно другую
        # длительность, такой кандидат не должен иметь
        # преимущество перед правильным вариантом.
        duration_penalty = 0

        if duration_difference is not None:
            if duration_difference > 30:
                duration_penalty = 500
            elif duration_difference > 10:
                duration_penalty = 100

        final_score = (
            float(score)
            - modifier_penalty
            - duration_penalty
        )

        candidates.append({
            "url": mp3_url,
            "referer": page_url,
            "artist": found_artist,
            "title": found_title,
            "page_duration": page_duration,
            "duration_difference": duration_difference,
            "score": float(score),
            "final_score": final_score
        })

    # --------------------------------------------------------
    # Fallback:
    # если HTML-структура слегка изменилась, попробуем
    # отдельно найти data-url.
    # --------------------------------------------------------

    if not candidates:

        direct_links = list(
            dict.fromkeys(
                re.findall(
                    r'data-url=["\']([^"\']+\.mp3(?:\?[^"\']*)?)["\']',
                    text,
                    re.I
                )
            )
        )

        for mp3_url in direct_links:

            filename = clean_filename(
                mp3_url.split("/")[-1]
            )

            score = candidate_text_score(
                filename,
                artist,
                title
            )

            if score < 0:
                continue

            candidates.append({
                "url": mp3_url,
                "referer": page_url,
                "artist": "",
                "title": filename,
                "page_duration": None,
                "duration_difference": None,
                "score": float(score),
                "final_score": float(score)
            })

    if not candidates:
        return None

    # --------------------------------------------------------
    # Сортировка кандидатов
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item["final_score"],
            -(
                item["duration_difference"]
                if item["duration_difference"] is not None
                else 999999
            )
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # Проверяем максимум 10 лучших кандидатов.
    # Реальная длительность проверяется через ffprobe.
    # --------------------------------------------------------

    for candidate in candidates[:10]:

        duration = get_duration(
            candidate["url"]
        )

        if not is_duration_acceptable(
            duration,
            target_duration
        ):
            continue

        return {
            "url": candidate["url"],
            "referer": candidate["referer"]
        }

    return None
