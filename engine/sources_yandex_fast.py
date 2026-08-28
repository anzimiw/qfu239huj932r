# -*- coding: utf-8 -*-

"""
CENSURU.NET
Быстрый путь Яндекс Музыка -> YouTube.

Назначение:
    Получив уже готовые метаданные Яндекс Музыки,
    быстро найти соответствующий трек на YouTube.

SoundCloud / MP3Party / MP3TM / AudioStart
здесь НЕ используются.
"""

import json
import os
import subprocess


def find_youtube_fast(
    ytdlp,
    artist,
    title,
    target_duration=None
):
    print()
    print("=" * 60)
    print("YANDEX -> YOUTUBE FAST")
    print("=" * 60)

    query = (
        f"{artist} {title}"
    ).strip()

    if not query:
        print(
            "Yandex Fast: "
            "пустой поисковый запрос."
        )

        return None

    command = [
        ytdlp,
        "--dump-single-json",
        "--flat-playlist",
        "--playlist-end",
        "5",
        "--quiet",
        "--no-warnings",
        "ytsearch5:" + query
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

    except subprocess.TimeoutExpired:

        print(
            "Yandex Fast: "
            "поиск YouTube превысил лимит времени."
        )

        return None

    except Exception as error:

        print(
            "Yandex Fast: "
            f"ошибка поиска: {type(error).__name__}: {error}"
        )

        return None

    if result.returncode != 0:

        print(
            "Yandex Fast: "
            "yt-dlp не смог выполнить поиск."
        )

        if result.stderr:
            print(
                result.stderr.strip()
            )

        return None

    try:

        data = json.loads(
            result.stdout
        )

    except Exception:

        print(
            "Yandex Fast: "
            "не удалось разобрать результат поиска."
        )

        return None

    entries = (
        data.get("entries")
        if isinstance(data, dict)
        else None
    )

    if not isinstance(
        entries,
        list
    ):
        return None

    try:
        target = (
            float(target_duration)
            if target_duration is not None
            else None
        )
    except Exception:
        target = None

    best_url = None
    best_difference = None

    for entry in entries:

        if not isinstance(
            entry,
            dict
        ):
            continue

        video_id = entry.get(
            "id"
        )

        if not video_id:
            continue

        video_url = (
            entry.get("webpage_url")
            or
            f"https://www.youtube.com/watch?v={video_id}"
        )

        candidate_duration = entry.get(
            "duration"
        )

        try:

            candidate_duration = (
                float(candidate_duration)
                if candidate_duration is not None
                else None
            )

        except Exception:

            candidate_duration = None

        if (
            target is not None
            and candidate_duration is not None
        ):

            difference = abs(
                candidate_duration
                - target
            )

            if difference > 20:
                continue

        else:

            difference = 999999

        if (
            best_url is None
            or difference < best_difference
        ):

            best_url = video_url
            best_difference = difference

    if not best_url:

        print(
            "Yandex Fast: "
            "подходящий YouTube-кандидат не найден."
        )

        return None

    print(
        "Yandex Fast: "
        f"найден YouTube URL: {best_url}"
    )

    if best_difference is not None:
        print(
            "Yandex Fast: "
            f"разница длительности: "
            f"{best_difference:.1f} сек."
        )

    return best_url
