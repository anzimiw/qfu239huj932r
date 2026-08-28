# -*- coding: utf-8 -*-

"""
CENSURU.NET
Быстрый путь YouTube.

Назначение:
    Прямое скачивание исходного YouTube URL.

ВАЖНО:
    Метаданные YouTube Music здесь НЕ получаются.
    Никакого поиска SoundCloud / MP3Party / MP3TM /
    AudioStart здесь нет.

Используется только для режима:
    normal
"""

import os
import subprocess


def download_youtube_fast(
    ytdlp,
    youtube_url,
    filepath,
    timeout=180
):
    print()
    print("=" * 60)
    print("YOUTUBE FAST")
    print("=" * 60)

    print(
        "YouTube Fast: "
        "метаданные предварительно НЕ получаются."
    )

    print(
        "YouTube Fast: "
        "прямое скачивание исходной ссылки."
    )

    temp_template = (
        os.path.splitext(filepath)[0]
        + ".youtube-fast.tmp.%(ext)s"
    )

    command = [
        ytdlp,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "-o",
        temp_template,
        youtube_url
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )

    except subprocess.TimeoutExpired:
        print(
            "YouTube Fast: "
            "скачивание превысило лимит времени."
        )

        return False

    except Exception as error:
        print(
            "YouTube Fast: "
            f"ошибка запуска: {type(error).__name__}: {error}"
        )

        return False

    if result.returncode != 0:

        print(
            "YouTube Fast: "
            "yt-dlp завершился с ошибкой."
        )

        if result.stderr:
            print(
                result.stderr.strip()
            )

        return False

    directory = os.path.dirname(
        filepath
    )

    base = os.path.splitext(
        os.path.basename(filepath)
    )[0]

    prefix = (
        base
        + ".youtube-fast.tmp."
    )

    files = []

    if os.path.isdir(directory):

        for filename in os.listdir(directory):

            if filename.startswith(prefix):

                files.append(
                    os.path.join(
                        directory,
                        filename
                    )
                )

    if not files:

        print(
            "YouTube Fast: "
            "временный MP3-файл не найден."
        )

        return False

    source_file = max(
        files,
        key=os.path.getmtime
    )

    if not os.path.isfile(source_file):

        return False

    if os.path.exists(filepath):

        try:
            os.remove(filepath)
        except Exception:
            pass

    try:

        os.replace(
            source_file,
            filepath
        )

    except Exception as error:

        print(
            "YouTube Fast: "
            f"не удалось переместить файл: {error}"
        )

        return False

    print(
        "YouTube Fast: "
        "MP3 успешно скачан."
    )

    return True
