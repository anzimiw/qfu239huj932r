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
import subprocess
import tempfile
import shutil


def _safe_filename(text):

    text = str(text or "").strip()

    result = []

    for char in text:

        if ord(char) < 32:
            continue

        if char in '<>:"/\\|?*':
            continue

        result.append(char)

    text = "".join(result).rstrip(" .")

    return text or "audio"


def _read_id3(path):

    artist = ""
    title = ""
    album = ""
    duration = None

    try:

        from mutagen.id3 import ID3

        tags = ID3(path)

        frame = tags.get("TPE1")

        if frame and frame.text:
            artist = str(
                frame.text[0]
            )

        frame = tags.get("TIT2")

        if frame and frame.text:
            title = str(
                frame.text[0]
            )

        frame = tags.get("TALB")

        if frame and frame.text:
            album = str(
                frame.text[0]
            )

    except Exception:
        pass

    try:

        from mutagen.mp3 import MP3

        duration = float(
            MP3(path).info.length
        )

    except Exception:
        pass

    return {
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration
    }


def _find_mp3(folder):

    try:

        files = [
            os.path.join(
                folder,
                name
            )
            for name in os.listdir(folder)
            if name.lower().endswith(".mp3")
        ]

        return sorted(
            files,
            key=os.path.getmtime,
            reverse=True
        )

    except Exception:

        return []


def _download(
    target,
    output_folder,
    ytdlp,
    ffmpeg,
    description
):

    if not target:
        return None

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    temp_dir = tempfile.mkdtemp(
        prefix=".fast_youtube_",
        dir=output_folder
    )

    output_template = os.path.join(
        temp_dir,
        "%(id)s.%(ext)s"
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

        "--embed-metadata",
        "--embed-thumbnail",

        "-o",
        output_template
    ]

    if ffmpeg:

        command.extend([
            "--ffmpeg-location",
            ffmpeg
        ])

    command.append(
        target
    )

    print()
    print("=" * 60)
    print(
        "БЫСТРЫЙ YOUTUBE"
    )
    print("=" * 60)

    print(
        f"Режим: {description}"
    )

    print(
        "Метаданные отдельным запросом "
        "не получаются."
    )

    print(
        "Один запуск yt-dlp: "
        "поиск/URL → MP3."
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
            "тайм-аут 180 секунд."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    except Exception as error:

        print(
            "БЫСТРЫЙ YOUTUBE: "
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
            "MP3 не найден."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    source_file = files[0]

    metadata = _read_id3(
        source_file
    )

    artist = metadata["artist"]
    title = metadata["title"]

    if not artist or not title:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "yt-dlp не записал "
            "необходимые ID3-теги."
        )

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return None

    filename = (
        f"{_safe_filename(artist)} - "
        f"{_safe_filename(title)}.mp3"
    )

    filepath = os.path.join(
        output_folder,
        filename
    )

    try:

        if os.path.exists(filepath):
            os.remove(filepath)

        os.replace(
            source_file,
            filepath
        )

    except Exception as error:

        print(
            "БЫСТРЫЙ YOUTUBE: "
            "ошибка переноса MP3:"
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

    result_info = {
        "source": "youtube",
        "artist": artist,
        "title": title,
        "album": metadata["album"],
        "duration": metadata["duration"],
        "cover_url": None,
        "youtube_age_restricted": False,
        "age_restricted": False,
        "filepath": filepath,
        "fast_path": True
    }

    print()
    print(
        "БЫСТРЫЙ YOUTUBE: "
        "УСПЕШНО."
    )

    print(
        f"Файл: {filepath}"
    )

    return result_info


def download_youtube_fast(
    youtube_url,
    output_folder,
    ytdlp,
    ffmpeg=None
):

    return _download(
        youtube_url,
        output_folder,
        ytdlp,
        ffmpeg,
        "прямой URL YouTube"
    )


def search_youtube_fast(
    artist,
    title,
    output_folder,
    ytdlp,
    ffmpeg=None
):

    query = (
        f"{artist} {title}"
    ).strip()

    if not query:
        return None

    return _download(
        "ytsearch1:" + query,
        output_folder,
        ytdlp,
        ffmpeg,
        "YouTube: artist + title"
    )
'''


YANDEX_FAST_CODE = r'''# -*- coding: utf-8 -*-

from sources_youtube_fast import (
    search_youtube_fast
)


def download_yandex_fast(
    artist,
    title,
    output_folder,
    ytdlp,
    ffmpeg=None
):

    print()
    print("=" * 60)
    print(
        "БЫСТРЫЙ ПУТЬ ЯНДЕКС → YOUTUBE"
    )
    print("=" * 60)

    print(
        f"Исполнитель: {artist}"
    )

    print(
        f"Название: {title}"
    )

    return search_youtube_fast(
        artist,
        title,
        output_folder,
        ytdlp,
        ffmpeg
    )
'''


def backup(path, timestamp):

    backup_path = path.with_name(
        path.name
        + ".backup_"
        + timestamp
    )

    shutil.copy2(
        path,
        backup_path
    )

    print(
        f"Резервная копия: "
        f"{backup_path.name}"
    )

    return backup_path


def compile_file(path):

    py_compile.compile(
        str(path),
        doraise=True
    )

    print(
        f"{path.name}: синтаксис OK"
    )


def add_downloader_imports(text):

    marker = (
        "from sources_audiostart "
        "import search_audiostart"
    )

    if marker not in text:

        raise RuntimeError(
            "Не найден импорт "
            "sources_audiostart."
        )

    if (
        "from sources_youtube_fast "
        "import download_youtube_fast"
        in text
    ):

        return text

    replacement = """from sources_audiostart import search_audiostart

from sources_youtube_fast import (
    download_youtube_fast as _fast_youtube_download,
    search_youtube_fast as _fast_youtube_search
)

from sources_yandex_fast import (
    download_yandex_fast as _fast_yandex_download
)
"""

    return text.replace(
        marker,
        replacement,
        1
    )


def add_downloader_wrappers(text):

    marker = (
        "# FIND AND DOWNLOAD\n\n"
        "def find_youtube_fallback_url("
    )

    if marker not in text:

        raise RuntimeError(
            "Не найден блок "
            "FIND AND DOWNLOAD "
            "в downloader.py."
        )

    if (
        "def download_youtube_fast("
        in text
    ):

        return text

    wrapper = r'''# FAST DOWNLOAD ROUTES
#
# Отдельный быстрый путь.
#
# Он НЕ вызывает:
#   get_youtube_music_info()
#   get_track_info()
#
# YouTube:
#   прямой URL -> yt-dlp -> MP3
#
# Yandex:
#   уже полученные metadata ->
#   ytsearch1 -> yt-dlp -> MP3


def download_youtube_fast(
    youtube_url,
    output_folder
):

    return _fast_youtube_download(
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

    return _fast_yandex_download(
        artist,
        title,
        output_folder,
        YTDLP,
        FFMPEG
    )


# FIND AND DOWNLOAD

def find_youtube_fallback_url(
'''

    return text.replace(
        marker,
        wrapper,
        1
    )


def patch_downloader(text):

    text = add_downloader_imports(
        text
    )

    text = add_downloader_wrappers(
        text
    )

    return text


def find_function_bounds(
    text,
    function_name
):

    marker = (
        f"def {function_name}("
    )

    start = text.find(
        marker
    )

    if start < 0:

        raise RuntimeError(
            f"Функция {function_name} "
            f"не найдена."
        )

    next_def = text.find(
        "\ndef ",
        start + len(marker)
    )

    if next_def < 0:

        end = len(text)

    else:

        end = next_def + 1

    return start, end


def replace_process_track(
    text
):

    start, end = find_function_bounds(
        text,
        "process_track"
    )

    old_function = text[
        start:end
    ]

    if (
        "fast_path_used"
        in old_function
    ):

        return text

    new_function = r'''def process_track(
    chat_id,
    url,
    playlist_progress=None,
    mode="uncensored",
    with_lrc=None
):

    try:

        # ----------------------------------------------------
        # НОВЫЙ БЫСТРЫЙ МАРШРУТ
        # ----------------------------------------------------

        is_yandex = (
            downloader.is_yandex_music_url(
                url
            )
        )

        fast_path_used = False
        fast_result = None

        # ====================================================
        # 1. YOUTUBE + NORMAL
        #
        # Никакого предварительного получения metadata.
        # Сразу пробуем скачать URL.
        # ====================================================

        if (
            mode == "normal"
            and not is_yandex
        ):

            print()
            print("=" * 70)
            print(
                "БЫСТРЫЙ РЕЖИМ: "
                "YOUTUBE"
            )
            print("=" * 70)

            send_message(
                chat_id,
                "Быстро скачиваю трек с YouTube..."
            )

            fast_result = (
                downloader.download_youtube_fast(
                    url,
                    TRACKS_FOLDER
                )
            )

            if fast_result:

                fast_path_used = True

                info = fast_result

                print(
                    "Быстрый YouTube: "
                    "успешно."
                )

            else:

                print(
                    "Быстрый YouTube: "
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

        # ====================================================
        # 2. YANDEX
        #
        # Metadata Яндекса оставляем.
        # После metadata:
        #
        # NORMAL:
        #   сразу YouTube.
        #
        # UNCENSORED:
        #   старый каскад.
        # ====================================================

        elif is_yandex:

            print()
            print(
                "Источник: Яндекс Музыка"
            )

            print(
                "Получение информации "
                "из Яндекс Музыки..."
            )

            info = (
                downloader.get_yandex_music_info(
                    url
                )
            )

            if (
                info
                and mode == "normal"
            ):

                yandex_artist = info.get(
                    "artist",
                    ""
                )

                yandex_title = info.get(
                    "title",
                    ""
                )

                print()
                print("=" * 70)
                print(
                    "БЫСТРЫЙ РЕЖИМ: "
                    "ЯНДЕКС → YOUTUBE"
                )
                print("=" * 70)

                fast_result = (
                    downloader.download_yandex_fast(
                        yandex_artist,
                        yandex_title,
                        TRACKS_FOLDER
                    )
                )

                if fast_result:

                    fast_path_used = True

                    info = fast_result

                    print(
                        "Быстрый "
                        "Яндекс → YouTube: "
                        "успешно."
                    )

                else:

                    print(
                        "Быстрый "
                        "Яндекс → YouTube "
                        "не сработал."
                    )

                    print(
                        "Переход к существующему "
                        "YouTube fallback."
                    )

        # ====================================================
        # 3. YOUTUBE + UNCENSORED
        #
        # Старый путь полностью сохраняется.
        # ====================================================

        else:

            print()
            print(
                "Источник: YouTube Music"
            )

            print(
                "Режим без цензуры: "
                "используется существующий "
                "metadata pipeline."
            )

            info = (
                downloader.get_youtube_music_info(
                    url
                )
            )

        # ----------------------------------------------------
        # Проверка metadata.
        # ----------------------------------------------------

        if not info:

            send_message(
                chat_id,
                "Не удалось получить информацию о треке."
            )

            print(
                "ОШИБКА: получение информации "
                "вернуло пустой результат."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        print()
        print(
            "Информация получена:"
        )
        print(
            info
        )

        artist = info.get(
            "artist",
            ""
        )

        title = info.get(
            "title",
            ""
        )

        duration = info.get(
            "duration",
            0
        )

        source = info.get(
            "source",
            "youtube"
        )

        youtube_age_restricted = info.get(
            "youtube_age_restricted",
            info.get(
                "age_restricted",
                False
            )
        )

        if (
            not artist
            or not title
            or not duration
        ):

            send_message(
                chat_id,
                (
                    "Не удалось определить "
                    "исполнителя, название "
                    "или длительность."
                )
            )

            print(
                "ОШИБКА: неполные metadata."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        # ----------------------------------------------------
        # Формат длительности.
        # ----------------------------------------------------

        try:

            duration_seconds = int(
                float(duration)
            )

            minutes = (
                duration_seconds // 60
            )

            seconds = (
                duration_seconds % 60
            )

            duration_text = (
                f"{minutes}:{seconds:02d}"
            )

        except Exception:

            duration_text = str(
                duration
            )

        # ----------------------------------------------------
        # Сообщение пользователю.
        # ----------------------------------------------------

        if playlist_progress:

            current_index, total_tracks = (
                playlist_progress
            )

            status_text = (
                f"Обработка трека "
                f"{current_index}/{total_tracks}\n\n"
                f"{artist} — {title}\n"
                f"Длительность: "
                f"{duration_text}\n\n"
                f"Начинаю обработку..."
            )

        else:

            status_text = (
                f"Трек найден:\n\n"
                f"Исполнитель: {artist}\n"
                f"Название: {title}\n"
                f"Длительность: "
                f"{duration_text}\n\n"
                f"Обрабатываю MP3..."
            )

        send_message(
            chat_id,
            status_text
        )

        # ----------------------------------------------------
        # 3. Запуск скачивания.
        #
        # Если быстрый путь уже создал файл,
        # find_and_download_track() НЕ вызывается.
        #
        # Иначе используется старый pipeline.
        # ----------------------------------------------------

        if fast_path_used:

            result = fast_result.get(
                "filepath"
            )

            print()
            print(
                "Используется MP3 "
                "быстрого пути:"
            )

            print(
                repr(result)
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

        print()
        print(
            "Результат downloader.py:"
        )
        print(
            repr(result)
        )

        if not result:

            send_message(
                chat_id,
                (
                    "Не удалось скачать "
                    "аудиофайл.\n\n"
                    f"{artist} — {title}"
                )
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        # ----------------------------------------------------
        # 4. Проверка файла.
        # ----------------------------------------------------

        file_path = str(
            result
        )

        if not os.path.isfile(
            file_path
        ):

            send_message(
                chat_id,
                (
                    "downloader.py завершился, "
                    "но MP3-файл не найден."
                )
            )

            print(
                f"Файл не найден: "
                f"{file_path}"
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        file_size = os.path.getsize(
            file_path
        )

        print()
        print(
            "MP3 создан:"
        )
        print(
            f"  {file_path}"
        )
        print(
            f"  Размер: "
            f"{file_size:,} байт"
        )

        # ----------------------------------------------------
        # Embedded cover / ID3.
        #
        # Быстрый yt-dlp уже пытается
        # добавить metadata/thumbnail.
        #
        # Но существующий embed_cover()
        # всё равно вызываем — если cover_url
        # есть, старый механизм его обработает.
        # ----------------------------------------------------

        print()
        print(
            "Проверка / добавление "
            "обложки..."
        )

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )

        # ----------------------------------------------------
        # LRC.
        # ----------------------------------------------------

        effective_with_lrc = (
            downloader.DOWNLOAD_LRC
            if with_lrc is None
            else bool(with_lrc)
        )

        print(
            "LRC: "
            f"{'ВКЛЮЧЕН' if effective_with_lrc else 'ОТКЛЮЧЕН'}"
        )

        if effective_with_lrc:

            time.sleep(
                downloader.LRCLIB_DELAY
            )

            downloader.process_lrc(
                artist,
                title,
                info.get("album", ""),
                duration,
                file_path
            )

        # ----------------------------------------------------
        # Проверка embedded cover.
        # ----------------------------------------------------

        try:

            from mutagen.id3 import ID3

            tags = ID3(
                file_path
            )

            apic_count = len(
                tags.getall(
                    "APIC:"
                )
            )

            print(
                f"Embedded cover APIC: "
                f"{apic_count}"
            )

            if apic_count > 0:

                print(
                    "OK: обложка "
                    "присутствует."
                )

            else:

                print(
                    "ВНИМАНИЕ: "
                    "APIC отсутствует."
                )

        except Exception as cover_check_error:

            print(
                "Не удалось проверить "
                "embedded cover:",
                cover_check_error
            )

        # ----------------------------------------------------
        # Статус.
        # ----------------------------------------------------

        send_message(
            chat_id,
            (
                "Трек скачан.\n\n"
                f"{artist} — {title}"
            )
        )

        print()
        print(
            "ЭТАП СКАЧИВАНИЯ "
            "УСПЕШНО ЗАВЕРШЁН."
        )

        # ----------------------------------------------------
        # Telegram MP3.
        # ----------------------------------------------------

        print()
        print(
            "Отправка MP3 в Telegram..."
        )

        upload_result = send_audio(
            chat_id,
            file_path
        )

        if upload_result.get(
            "ok"
        ):

            print(
                "MP3 успешно отправлен "
                "в Telegram."
            )

            lrc_path = (
                os.path.splitext(
                    file_path
                )[0]
                + ".lrc"
            )

            if os.path.isfile(
                lrc_path
            ):

                print()
                print(
                    "LRC-файл найден:"
                )

                print(
                    f"  {lrc_path}"
                )

                print()
                print(
                    "Отправка LRC "
                    "в Telegram..."
                )

                lrc_result = (
                    send_document(
                        chat_id,
                        lrc_path
                    )
                )

                if lrc_result.get(
                    "ok"
                ):

                    print(
                        "LRC успешно "
                        "отправлен."
                    )

                else:

                    print(
                        "Не удалось "
                        "отправить LRC."
                    )

        else:

            print(
                "Не удалось отправить "
                "MP3 в Telegram."
            )

        globals().get(
            "_STATUS_MESSAGES",
            {}
        ).pop(
            chat_id,
            None
        )

        return True

    except Exception as e:

        print()
        print(
            "=" * 70
        )
        print(
            "ОШИБКА ОБРАБОТКИ ТРЕКА"
        )
        print(
            "=" * 70
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        try:

            send_message(
                chat_id,
                "Произошла ошибка "
                "при обработке трека."
            )

        except Exception as telegram_error:

            print(
                "Не удалось отправить "
                "сообщение об ошибке:"
            )

            print(
                f"{type(telegram_error).__name__}: "
                f"{telegram_error}"
            )

        globals().get(
            "_STATUS_MESSAGES",
            {}
        ).pop(
            chat_id,
            None
        )

        return False

'''

    return (
        text[:start]
        + new_function
        + text[end:]
    )


def patch_bot(text):

    return replace_process_track(
        text
    )


def main():

    print(
        "=" * 70
    )

    print(
        "CENSURU.NET"
    )

    print(
        "FAST DOWNLOAD PATCH"
    )

    print(
        "=" * 70
    )

    timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    backups = []

    try:

        print()
        print(
            "Создание резервных копий..."
        )

        backups.append(
            (
                DOWNLOADER,
                backup(
                    DOWNLOADER,
                    timestamp
                )
            )
        )

        backups.append(
            (
                BOT,
                backup(
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

        print(
            "OK"
        )

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

        print(
            "OK"
        )

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

        print(
            "OK"
        )

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

        print(
            "OK"
        )

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
        print(
            "=" * 70
        )

        print(
            "ПАТЧ УСПЕШНО ПРИМЕНЁН."
        )

        print(
            "=" * 70
        )

        print()
        print(
            "Новые файлы:"
        )

        print(
            "  sources_youtube_fast.py"
        )

        print(
            "  sources_yandex_fast.py"
        )

        print()
        print(
            "Изменённые файлы:"
        )

        print(
            "  downloader.py"
        )

        print(
            "  bot.py"
        )

    except Exception as error:

        print()
        print(
            "=" * 70
        )

        print(
            "ОШИБКА ПАТЧА."
        )

        print(
            "=" * 70
        )

        print()
        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        print()
        print(
            "Восстанавливаю резервные копии..."
        )

        for original, backup_path in backups:

            try:

                if backup_path.exists():

                    shutil.copy2(
                        backup_path,
                        original
                    )

                    print(
                        f"Восстановлен: "
                        f"{original.name}"
                    )

            except Exception as restore_error:

                print(
                    "Ошибка восстановления:"
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
