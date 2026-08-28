# -*- coding: utf-8 -*-

from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys


ENGINE = Path(__file__).resolve().parent

DOWNLOADER = ENGINE / "downloader.py"
BOT = ENGINE / "bot.py"

YOUTUBE_FAST = ENGINE / "sources_youtube_fast.py"
YANDEX_FAST = ENGINE / "sources_yandex_fast.py"


YOUTUBE_FAST_CODE = r'''# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile

try:
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
except ImportError:
    ID3 = None
    MP3 = None


def _safe_filename(value):
    text = str(value or "").strip()

    result = []

    for char in text:

        if ord(char) < 32:
            continue

        if char in '<>:"/\\|?*':
            continue

        result.append(char)

    text = "".join(result)

    text = text.rstrip(" .")

    if not text:
        return "audio"

    return text


def _tag_text(tags, key):

    if tags is None:
        return ""

    try:

        frame = tags.get(key)

        if (
            frame
            and getattr(frame, "text", None)
        ):

            return str(
                frame.text[0]
            ).strip()

    except Exception:
        pass

    return ""


def _read_audio_info(path):

    artist = ""
    title = ""
    album = ""
    duration = None

    if ID3 is not None:

        try:

            tags = ID3(path)

            artist = _tag_text(
                tags,
                "TPE1"
            )

            title = _tag_text(
                tags,
                "TIT2"
            )

            album = _tag_text(
                tags,
                "TALB"
            )

        except Exception:
            pass

    if MP3 is not None:

        try:

            duration = float(
                MP3(path).info.length
            )

        except Exception:
            pass

    return {
        "source": "youtube",
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration,
        "cover_url": None,
        "age_restricted": False,
        "fast_path": True
    }


def _find_mp3(directory):

    files = []

    try:

        for name in os.listdir(
            directory
        ):

            if name.lower().endswith(
                ".mp3"
            ):

                files.append(
                    os.path.join(
                        directory,
                        name
                    )
                )

    except Exception:
        return []

    return sorted(
        files,
        key=lambda path: os.path.getmtime(path),
        reverse=True
    )


def _download(
    target,
    output_folder,
    ytdlp_path,
    ffmpeg_path,
    label
):

    if not target:
        return None

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    temp_dir = tempfile.mkdtemp(
        prefix=".censuru_fast_",
        dir=output_folder
    )

    output_template = os.path.join(
        temp_dir,
        "%(id)s.%(ext)s"
    )

    command = [
        ytdlp_path,

        "--no-playlist",

        "--quiet",
        "--no-warnings",

        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",

        "--embed-metadata",
        "--embed-thumbnail",
        "--convert-thumbnails",
        "jpg",

        "-o",
        output_template
    ]

    if ffmpeg_path:

        command.extend([
            "--ffmpeg-location",
            ffmpeg_path
        ])

    command.append(
        target
    )

    print()
    print(
        "БЫСТРЫЙ YOUTUBE: "
        f"{label}"
    )

    print(
        "БЫСТРЫЙ YOUTUBE: "
        "один запуск yt-dlp, "
        "без отдельного получения метаданных."
    )

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180
        )

    except subprocess.TimeoutExpired:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "превышен лимит 180 секунд."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    except Exception as error:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "ошибка запуска:"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    if result.returncode != 0:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "yt-dlp завершился с ошибкой."
        )

        if result.stderr:

            print(
                result.stderr.strip()
            )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    files = _find_mp3(
        temp_dir
    )

    if not files:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "готовый MP3 не найден."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    source_file = files[0]

    info = _read_audio_info(
        source_file
    )

    if not info["title"]:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "yt-dlp не записал "
            "название трека."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    artist = (
        info["artist"]
        or "Unknown Artist"
    )

    title = info["title"]

    filename = (
        f"{_safe_filename(artist)} - "
        f"{_safe_filename(title)}.mp3"
    )

    filepath = os.path.join(
        output_folder,
        filename
    )

    try:

        if os.path.exists(
            filepath
        ):

            os.remove(
                filepath
            )

        os.replace(
            source_file,
            filepath
        )

    except Exception as error:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "не удалось переместить MP3:"
        )

        print(error)

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    shutil.rmtree(
        temp_dir,
        ignore_errors=True
    )

    info["artist"] = artist
    info["title"] = title
    info["filepath"] = filepath

    print()
    print(
        "БЫСТРЫЙ YOUTUBE: "
        "аудиофайл готов."
    )

    print(
        f"Файл: {filepath}"
    )

    return info


def download_youtube_fast(
    youtube_url,
    output_folder,
    ytdlp_path,
    ffmpeg_path=None
):

    return _download(
        youtube_url,
        output_folder,
        ytdlp_path,
        ffmpeg_path,
        "прямой URL"
    )


def search_and_download_youtube_fast(
    artist,
    title,
    output_folder,
    ytdlp_path,
    ffmpeg_path=None
):

    query = (
        f"{artist} {title}"
    ).strip()

    if not query:
        return None

    return _download(
        "ytsearch1:" + query,
        output_folder,
        ytdlp_path,
        ffmpeg_path,
        "поиск по артисту + названию"
    )
'''


YANDEX_FAST_CODE = r'''# -*- coding: utf-8 -*-

from sources_youtube_fast import (
    search_and_download_youtube_fast
)


def download_yandex_fast(
    artist,
    title,
    output_folder,
    ytdlp_path,
    ffmpeg_path=None
):

    print()
    print(
        "БЫСТРЫЙ YOUTUBE ДЛЯ ЯНДЕКСА:"
    )

    print(
        "Источник метаданных: "
        "Яндекс Музыка."
    )

    print(
        "Поиск аудио: "
        "YouTube."
    )

    return search_and_download_youtube_fast(
        artist,
        title,
        output_folder,
        ytdlp_path,
        ffmpeg_path
    )
'''


def backup_file(path, timestamp):

    backup = path.with_name(
        path.name
        + ".backup_"
        + timestamp
    )

    shutil.copy2(
        path,
        backup
    )

    print(
        f"Резервная копия: {backup.name}"
    )

    return backup


def compile_file(path):

    py_compile.compile(
        str(path),
        doraise=True
    )

    print(
        f"Проверка синтаксиса: "
        f"{path.name}: OK"
    )


def patch_downloader(text):

    import_block = """from sources_audiostart import search_audiostart
"""

    if import_block not in text:

        raise RuntimeError(
            "Не найден импорт sources_audiostart "
            "в downloader.py."
        )

    new_import_block = """from sources_audiostart import search_audiostart

from sources_youtube_fast import (
    download_youtube_fast as _download_youtube_fast
)

from sources_yandex_fast import (
    download_yandex_fast as _download_yandex_fast
)
"""

    if "from sources_youtube_fast import" not in text:

        text = text.replace(
            import_block,
            new_import_block,
            1
        )

    marker = """# FIND AND DOWNLOAD

def find_youtube_fallback_url(
"""

    if marker not in text:

        raise RuntimeError(
            "Не найден блок FIND AND DOWNLOAD "
            "в downloader.py."
        )

    fast_functions = r'''# FAST YOUTUBE DOWNLOAD
#
# Быстрый путь намеренно отделён от
# существующего metadata/fallback pipeline.
#
# YouTube:
#   прямой URL -> yt-dlp -> MP3
#
# Yandex:
#   metadata Yandex -> ytsearch1 -> MP3


def download_youtube_fast(
    youtube_url,
    output_folder
):

    return _download_youtube_fast(
        youtube_url,
        output_folder,
        YTDLP,
        FFMPEG
    )


def download_yandex_fast(
    artist,
    title,
    output_folder
):

    return _download_yandex_fast(
        artist,
        title,
        output_folder,
        YTDLP,
        FFMPEG
    )


# FIND AND DOWNLOAD

def find_youtube_fallback_url(
'''

    if "def download_youtube_fast(" not in text:

        text = text.replace(
            marker,
            fast_functions,
            1
        )

    return text


def patch_bot(text):

    old_initial = """        if playlist_progress:
            current_index, total_tracks = playlist_progress
            send_message(
                chat_id,
                (
                    f"Обработка трека "
                    f"{current_index}/{total_tracks}...\\n\\n"
                    f"Получаю информацию о треке..."
                )
            )
        else:
            send_message(
                chat_id,
                "Получаю информацию о треке..."
            )
        # ----------------------------------------------------
        # 1. Получение информации
        # ----------------------------------------------------

        print()
        print("Получение информации из downloader.py...")

        if downloader.is_yandex_music_url(url):

            print()
            print("Источник: Яндекс Музыка")
            print("Получение информации из Яндекс Музыки...")

            info = downloader.get_yandex_music_info(
                url
            )

        else:

            print()
            print("Источник: YouTube Music")
            print("Получение информации из YouTube Music...")

            info = downloader.get_youtube_music_info(
                url
            )
"""

    new_initial = """        is_yandex_url = (
            downloader.is_yandex_music_url(url)
        )

        fast_path_used = False
        fast_download_result = None

        if (
            mode == "normal"
            and not is_yandex_url
        ):

            if playlist_progress:

                current_index, total_tracks = (
                    playlist_progress
                )

                send_message(
                    chat_id,
                    (
                        f"Обработка трека "
                        f"{current_index}/{total_tracks}...\\n\\n"
                        f"Быстро скачиваю с YouTube..."
                    )
                )

            else:

                send_message(
                    chat_id,
                    "Быстро скачиваю с YouTube..."
                )

        elif playlist_progress:

            current_index, total_tracks = (
                playlist_progress
            )

            send_message(
                chat_id,
                (
                    f"Обработка трека "
                    f"{current_index}/{total_tracks}...\\n\\n"
                    f"Получаю информацию о треке..."
                )
            )

        else:

            send_message(
                chat_id,
                "Получаю информацию о треке..."
            )

        # ----------------------------------------------------
        # 1. Получение информации / быстрый путь
        # ----------------------------------------------------

        if (
            mode == "normal"
            and not is_yandex_url
        ):

            print()
            print(
                "Обычный режим: "
                "запускаю быстрый путь YouTube."
            )

            fast_download_result = (
                downloader.download_youtube_fast(
                    url,
                    TRACKS_FOLDER
                )
            )

            if fast_download_result:

                info = fast_download_result
                fast_path_used = True

                print()
                print(
                    "Быстрый путь YouTube: "
                    "УСПЕШНО."
                )

            else:

                print()
                print(
                    "Быстрый путь YouTube "
                    "не сработал."
                )

                print(
                    "Переход к существующему "
                    "metadata pipeline."
                )

                info = (
                    downloader.get_youtube_music_info(
                        url
                    )
                )

        elif is_yandex_url:

            print()
            print("Источник: Яндекс Музыка")
            print(
                "Получение информации "
                "из Яндекс Музыки..."
            )

            info = (
                downloader.get_yandex_music_info(
                    url
                )
            )

        else:

            print()
            print("Источник: YouTube Music")
            print(
                "Получение информации "
                "из YouTube Music..."
            )

            info = (
                downloader.get_youtube_music_info(
                    url
                )
            )
"""

    if old_initial not in text:

        raise RuntimeError(
            "Не найден блок получения информации "
            "в bot.py."
        )

    text = text.replace(
        old_initial,
        new_initial,
        1
    )

    marker = """        # ----------------------------------------------------
        # Формат длительности: MM:SS
        # ----------------------------------------------------
"""

    if marker not in text:

        raise RuntimeError(
            "Не найден блок форматирования "
            "длительности в bot.py."
        )

    yandex_fast_block = """        # ----------------------------------------------------
        # Быстрый путь Яндекс -> YouTube
        # ----------------------------------------------------

        if (
            not fast_path_used
            and mode == "normal"
            and source == "yandex"
        ):

            print()
            print(
                "Обычный режим + Яндекс:"
            )

            print(
                "Запускаю быстрый поиск "
                "на YouTube..."
            )

            fast_download_result = (
                downloader.download_yandex_fast(
                    artist,
                    title,
                    TRACKS_FOLDER
                )
            )

            if fast_download_result:

                fast_path_used = True

                print()
                print(
                    "Быстрый путь "
                    "Яндекс -> YouTube: "
                    "УСПЕШНО."
                )

            else:

                print()
                print(
                    "Быстрый путь "
                    "Яндекс -> YouTube "
                    "не сработал."
                )

                print(
                    "Будет использован "
                    "существующий YouTube fallback."
                )

        # ----------------------------------------------------
        # Формат длительности: MM:SS
        # ----------------------------------------------------
"""

    if "Быстрый путь Яндекс -> YouTube" not in text:

        text = text.replace(
            marker,
            yandex_fast_block,
            1
        )

    old_download = """        # ----------------------------------------------------
        # 3. Запуск существующего downloader.py
        # ----------------------------------------------------

        print()
        print("Запуск find_and_download_track()...")

        result = downloader.find_and_download_track(
            artist,
            title,
            duration,
            TRACKS_FOLDER,
            url,
            source,
            youtube_age_restricted,
            mode=mode
        )
"""

    new_download = """        # ----------------------------------------------------
        # 3. Запуск выбранного пути скачивания
        # ----------------------------------------------------

        if fast_path_used:

            print()
            print(
                "Используется быстрый путь."
            )

            result = (
                fast_download_result.get(
                    "filepath"
                )
                if fast_download_result
                else None
            )

        else:

            print()
            print(
                "Запуск "
                "find_and_download_track()..."
            )

            result = (
                downloader.find_and_download_track(
                    artist,
                    title,
                    duration,
                    TRACKS_FOLDER,
                    url,
                    source,
                    youtube_age_restricted,
                    mode=mode
                )
            )
"""

    if old_download not in text:

        raise RuntimeError(
            "Не найден старый запуск "
            "find_and_download_track() "
            "в bot.py."
        )

    text = text.replace(
        old_download,
        new_download,
        1
    )

    old_cover = """        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )
"""

    new_cover = """        print()

        if (
            fast_path_used
            and source == "youtube"
            and not info.get("cover_url")
        ):

            print(
                "Быстрый YouTube: "
                "обложка уже обработана "
                "yt-dlp."
            )

        else:

            print(
                "Добавление обложки в MP3..."
            )

            downloader.embed_cover(
                file_path,
                info.get("cover_url"),
                artist,
                title,
                info.get("album", "")
            )
"""

    if old_cover not in text:

        raise RuntimeError(
            "Не найден блок embed_cover "
            "в bot.py."
        )

    text = text.replace(
        old_cover,
        new_cover,
        1
    )

    return text


def main():

    print("=" * 70)
    print(
        "CENSURU.NET — PATCH "
        "FAST DOWNLOAD V2"
    )
    print("=" * 70)

    if not DOWNLOADER.exists():
        raise FileNotFoundError(
            DOWNLOADER
        )

    if not BOT.exists():
        raise FileNotFoundError(
            BOT
        )

    timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    backups = []

    try:

        print()
        print("Создание резервных копий...")

        backups.append(
            (
                DOWNLOADER,
                backup_file(
                    DOWNLOADER,
                    timestamp
                )
            )
        )

        backups.append(
            (
                BOT,
                backup_file(
                    BOT,
                    timestamp
                )
            )
        )

        print()
        print(
            "1/5: создание "
            "sources_youtube_fast.py..."
        )

        YOUTUBE_FAST.write_text(
            YOUTUBE_FAST_CODE,
            encoding="utf-8",
            newline="\n"
        )

        print("OK")

        print()
        print(
            "2/5: создание "
            "sources_yandex_fast.py..."
        )

        YANDEX_FAST.write_text(
            YANDEX_FAST_CODE,
            encoding="utf-8",
            newline="\n"
        )

        print("OK")

        print()
        print(
            "3/5: патч downloader.py..."
        )

        downloader_text = (
            DOWNLOADER.read_text(
                encoding="utf-8"
            )
        )

        downloader_text = patch_downloader(
            downloader_text
        )

        DOWNLOADER.write_text(
            downloader_text,
            encoding="utf-8",
            newline="\n"
        )

        print("OK")

        print()
        print(
            "4/5: патч bot.py..."
        )

        bot_text = (
            BOT.read_text(
                encoding="utf-8"
            )
        )

        bot_text = patch_bot(
            bot_text
        )

        BOT.write_text(
            bot_text,
            encoding="utf-8",
            newline="\n"
        )

        print("OK")

        print()
        print(
            "5/5: проверка синтаксиса..."
        )

        compile_file(
            YOUTUBE_FAST
        )

        compile_file(
            YANDEX_FAST
        )

        compile_file(
            DOWNLOADER
        )

        compile_file(
            BOT
        )

        print()
        print("=" * 70)
        print(
            "ПАТЧ УСПЕШНО ПРИМЕНЁН."
        )
        print("=" * 70)

        print()
        print(
            "Добавлены:"
        )

        print(
            "  sources_youtube_fast.py"
        )

        print(
            "  sources_yandex_fast.py"
        )

        print()
        print(
            "Изменены:"
        )

        print(
            "  downloader.py"
        )

        print(
            "  bot.py"
        )

        print()
        print(
            "Старые backup-файлы сохранены."
        )

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "ОШИБКА ПАТЧА."
        )
        print("=" * 70)

        print()
        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        print()
        print(
            "Восстанавливаю резервные копии..."
        )

        for original, backup in backups:

            try:

                if backup.exists():

                    shutil.copy2(
                        backup,
                        original
                    )

                    print(
                        f"Восстановлен: "
                        f"{original.name}"
                    )

            except Exception as restore_error:

                print(
                    "ОШИБКА восстановления:"
                )

                print(
                    f"{type(restore_error).__name__}: "
                    f"{restore_error}"
                )

        for path in (
            YOUTUBE_FAST,
            YANDEX_FAST
        ):

            try:

                if path.exists():
                    path.unlink()

            except Exception:
                pass

        print()
        print(
            "Изменения откатились."
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
