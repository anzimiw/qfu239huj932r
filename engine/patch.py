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


def backup_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(
        f"{path.name}.backup_{timestamp}"
    )

    shutil.copy2(
        path,
        backup
    )

    print(
        f"Резервная копия: {backup.name}"
    )

    return backup


def write_file(path, content):
    path.write_text(
        content,
        encoding="utf-8"
    )


def check_file(path):
    py_compile.compile(
        str(path),
        doraise=True
    )


# ============================================================
# SOURCES YOUTUBE FAST
# ============================================================

YOUTUBE_FAST_CODE = r'''# -*- coding: utf-8 -*-

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
'''


# ============================================================
# SOURCES YANDEX FAST
# ============================================================

YANDEX_FAST_CODE = r'''# -*- coding: utf-8 -*-

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
'''


def patch_downloader(text):

    # --------------------------------------------------------
    # 1. Добавляем импорты fast-модулей
    # --------------------------------------------------------

    import_marker = (
        "from sources_audiostart import search_audiostart\n"
    )

    if import_marker not in text:
        raise RuntimeError(
            "downloader.py: "
            "не найден импорт sources_audiostart."
        )

    fast_imports = (
        "\n"
        "from sources_youtube_fast import "
        "download_youtube_fast\n"
        "\n"
        "from sources_yandex_fast import "
        "find_youtube_fast\n"
    )

    if "from sources_youtube_fast import download_youtube_fast" not in text:

        text = text.replace(
            import_marker,
            import_marker + fast_imports,
            1
        )

    # --------------------------------------------------------
    # 2. Добавляем отдельную функцию быстрого YouTube
    # --------------------------------------------------------

    marker = (
        "# FIND AND DOWNLOAD\n"
    )

    if marker not in text:
        raise RuntimeError(
            "downloader.py: "
            "не найден блок FIND AND DOWNLOAD."
        )

    fast_functions = r'''

# ============================================================
# FAST DOWNLOAD PATHS
# ============================================================

def download_youtube_fast_track(
    youtube_url,
    filepath
):
    """
    Быстрый путь обычного YouTube-трека.

    Никаких метаданных до скачивания.
    Никаких SoundCloud / MP3Party / MP3TM / AudioStart.
    """

    return download_youtube_fast(
        YTDLP,
        youtube_url,
        filepath
    )


def download_yandex_fast_track(
    artist,
    title,
    duration,
    filepath
):
    """
    Быстрый путь Яндекс Музыка -> YouTube.

    Метаданные Яндекса уже получены вызывающим кодом.
    Здесь выполняется только поиск YouTube и скачивание.
    """

    youtube_url = find_youtube_fast(
        YTDLP,
        artist,
        title,
        duration
    )

    if not youtube_url:

        return False

    return download_youtube_fast(
        YTDLP,
        youtube_url,
        filepath
    )

'''

    if "def download_youtube_fast_track(" not in text:

        text = text.replace(
            marker,
            fast_functions + marker,
            1
        )

    return text


def patch_bot(text):

    # --------------------------------------------------------
    # Находим точный актуальный блок process_track()
    # --------------------------------------------------------

    start_marker = (
        "def process_track(\n"
        "    chat_id,\n"
        "    url,\n"
        "    playlist_progress=None,\n"
        "    mode=\"uncensored\",\n"
        "    with_lrc=None\n"
        "):"
    )

    start = text.find(
        start_marker
    )

    if start < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден актуальный process_track()."
        )

    info_marker = (
        "        # ----------------------------------------------------\n"
        "        # 1. Получение информации\n"
        "        # ----------------------------------------------------\n"
    )

    info_start = text.find(
        info_marker,
        start
    )

    if info_start < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден блок получения информации "
            "в актуальном process_track()."
        )

    # Следующий блок начинается с "if not info:"
    info_end_marker = (
        "        if not info:\n"
    )

    info_end = text.find(
        info_end_marker,
        info_start
    )

    if info_end < 0:
        raise RuntimeError(
            "bot.py: "
            "не найдено завершение блока получения информации."
        )

    # --------------------------------------------------------
    # Новый блок.
    #
    # ВАЖНО:
    # normal + YouTube:
    #     вообще не получаем metadata.
    #
    # normal + Yandex:
    #     metadata получаем.
    #
    # uncensored:
    #     metadata получаем всегда.
    # --------------------------------------------------------

    new_info_block = r'''        # ----------------------------------------------------
        # 1. Получение информации
        # ----------------------------------------------------
        #
        # БЫСТРЫЙ ПУТЬ:
        #
        # YouTube + normal:
        #     metadata НЕ получаем.
        #     Сразу передаём исходный URL в downloader.py.
        #
        # Yandex + normal:
        #     metadata получаем, потому что они нужны
        #     для поиска соответствующего YouTube-трека.
        #
        # uncensored:
        #     metadata получаем всегда.
        # ----------------------------------------------------

        fast_youtube_normal = (
            mode == "normal"
            and downloader.is_youtube_music_url(url)
            and not downloader.is_yandex_music_url(url)
        )

        if fast_youtube_normal:

            print()
            print(
                "БЫСТРЫЙ ПУТЬ YOUTUBE."
            )
            print(
                "Метаданные YouTube "
                "перед скачиванием НЕ получаются."
            )

            info = {
                "artist": "",
                "title": "",
                "duration": 0,
                "album": "",
                "cover_url": None,
                "source": "youtube",
                "youtube_age_restricted": False,
                "fast_youtube": True
            }

        elif downloader.is_yandex_music_url(url):

            print()
            print(
                "Источник: Яндекс Музыка"
            )
            print(
                "Получение информации "
                "из Яндекс Музыки..."
            )

            info = downloader.get_yandex_music_info(
                url
            )

        else:

            print()
            print(
                "Источник: YouTube Music"
            )
            print(
                "Получение информации "
                "из YouTube Music..."
            )

            info = downloader.get_youtube_music_info(
                url
            )

'''

    text = (
        text[:info_start]
        + new_info_block
        + text[info_end:]
    )

    # --------------------------------------------------------
    # Теперь заменяем блок проверки метаданных.
    #
    # Для fast_youtube normal metadata намеренно отсутствуют.
    # Поэтому нельзя выполнять старую проверку:
    #
    #     if not artist or not title or not duration
    #
    # --------------------------------------------------------

    check_marker = (
        "        if not artist or not title or not duration:\n"
    )

    check_start = text.find(
        check_marker,
        start
    )

    if check_start < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден блок проверки метаданных."
        )

    check_end_marker = (
        "        # ----------------------------------------------------\n"
        "        # Формат длительности: MM:SS\n"
        "        # ----------------------------------------------------\n"
    )

    check_end = text.find(
        check_end_marker,
        check_start
    )

    if check_end < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден конец проверки метаданных."
        )

    new_check = r'''        if (
            not info.get("fast_youtube", False)
            and (
                not artist
                or not title
                or not duration
            )
        ):

            send_message(
                chat_id,
                "Не удалось определить исполнителя, название или длительность."
            )

            print(
                "ОШИБКА: неполные метаданные."
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

    text = (
        text[:check_start]
        + new_check
        + text[check_end:]
    )

    # --------------------------------------------------------
    # Заменяем вызов downloader.find_and_download_track()
    # на выбор fast/full пути.
    # --------------------------------------------------------

    call_marker = (
        "        result = downloader.find_and_download_track(\n"
    )

    call_start = text.find(
        call_marker,
        start
    )

    if call_start < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден вызов find_and_download_track()."
        )

    # Конец вызова определяется по "        )"
    call_end = text.find(
        "        )",
        call_start
    )

    if call_end < 0:
        raise RuntimeError(
            "bot.py: "
            "не найден конец вызова find_and_download_track()."
        )

    call_end += len(
        "        )"
    )

    new_call = r'''        # ----------------------------------------------------
        # 3. Выбор пути скачивания
        # ----------------------------------------------------

        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "Запуск YouTube Fast..."
            )

            filename = (
                f"{downloader.safe_filename(url.split('/')[-1])}.mp3"
            )

            # Имя файла здесь нельзя строить из metadata:
            # metadata специально НЕ получались.
            #
            # downloader.py сам определяет корректное имя
            # непосредственно из URL только после успешного
            # скачивания.

            result = downloader.download_youtube_fast_direct(
                url,
                TRACKS_FOLDER
            )

        else:

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
'''

    text = (
        text[:call_start]
        + new_call
        + text[call_end:]
    )

    return text


def add_direct_fast_function(text):

    marker = (
        "# FIND AND DOWNLOAD\n"
    )

    if marker not in text:
        raise RuntimeError(
            "downloader.py: "
            "не найден FIND AND DOWNLOAD."
        )

    function = r'''

# ============================================================
# DIRECT YOUTUBE FAST
# ============================================================

def download_youtube_fast_direct(
    youtube_url,
    output_folder
):
    """
    Полностью быстрый YouTube путь.

    До начала скачивания:
        - metadata НЕ запрашиваются;
        - artist/title/duration НЕ запрашиваются;
        - SoundCloud НЕ используется;
        - MP3Party НЕ используется;
        - MP3TM НЕ используется;
        - AudioStart НЕ используется.

    После успешного скачивания:
        yt-dlp уже создаёт MP3,
        после чего вызывающий bot.py продолжает
        стандартную обработку файла.
    """

    temp_name = (
        "youtube_fast_"
        + str(abs(hash(youtube_url)))
        + ".mp3"
    )

    filepath = os.path.join(
        output_folder,
        temp_name
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    success = download_youtube_fast_track(
        youtube_url,
        filepath
    )

    if not success:
        return None

    if not os.path.isfile(filepath):
        return None

    return filepath

'''

    if "def download_youtube_fast_direct(" not in text:

        text = text.replace(
            marker,
            function + marker,
            1
        )

    return text


def main():

    print()
    print("=" * 70)
    print("CENSURU.NET — FAST DOWNLOAD PATCH")
    print("=" * 70)
    print()

    if not DOWNLOADER.is_file():
        raise RuntimeError(
            f"Не найден: {DOWNLOADER}"
        )

    if not BOT.is_file():
        raise RuntimeError(
            f"Не найден: {BOT}"
        )

    # --------------------------------------------------------
    # Резервные копии
    # --------------------------------------------------------

    print(
        "Создание резервных копий..."
    )

    downloader_backup = backup_file(
        DOWNLOADER
    )

    bot_backup = backup_file(
        BOT
    )

    try:

        # ----------------------------------------------------
        # 1. sources_youtube_fast.py
        # ----------------------------------------------------

        print()
        print(
            "1/5: создание sources_youtube_fast.py..."
        )

        write_file(
            YOUTUBE_FAST,
            YOUTUBE_FAST_CODE
        )

        check_file(
            YOUTUBE_FAST
        )

        print("OK")

        # ----------------------------------------------------
        # 2. sources_yandex_fast.py
        # ----------------------------------------------------

        print()
        print(
            "2/5: создание sources_yandex_fast.py..."
        )

        write_file(
            YANDEX_FAST,
            YANDEX_FAST_CODE
        )

        check_file(
            YANDEX_FAST
        )

        print("OK")

        # ----------------------------------------------------
        # 3. downloader.py
        # ----------------------------------------------------

        print()
        print(
            "3/5: патч downloader.py..."
        )

        downloader_text = DOWNLOADER.read_text(
            encoding="utf-8"
        )

        downloader_text = patch_downloader(
            downloader_text
        )

        downloader_text = add_direct_fast_function(
            downloader_text
        )

        DOWNLOADER.write_text(
            downloader_text,
            encoding="utf-8"
        )

        check_file(
            DOWNLOADER
        )

        print("OK")

        # ----------------------------------------------------
        # 4. bot.py
        # ----------------------------------------------------

        print()
        print(
            "4/5: патч bot.py..."
        )

        bot_text = BOT.read_text(
            encoding="utf-8"
        )

        bot_text = patch_bot(
            bot_text
        )

        BOT.write_text(
            bot_text,
            encoding="utf-8"
        )

        check_file(
            BOT
        )

        print("OK")

        # ----------------------------------------------------
        # 5. Финальная проверка
        # ----------------------------------------------------

        print()
        print(
            "5/5: финальная проверка..."
        )

        check_file(
            DOWNLOADER
        )

        check_file(
            BOT
        )

        check_file(
            YOUTUBE_FAST
        )

        check_file(
            YANDEX_FAST
        )

        print("OK")

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
        print("=" * 70)
        print()

        print(
            "Созданы:"
        )

        print(
            f"  {YOUTUBE_FAST.name}"
        )

        print(
            f"  {YANDEX_FAST.name}"
        )

        print()

        print(
            "Обновлены:"
        )

        print(
            "  downloader.py"
        )

        print(
            "  bot.py"
        )

        print()

        print(
            "Схема:"
        )

        print(
            "  YouTube + normal -> DIRECT FAST"
        )

        print(
            "  Yandex + normal -> METADATA -> "
            "YOUTUBE FAST SEARCH -> DOWNLOAD"
        )

        print(
            "  YouTube + uncensored -> "
            "METADATA -> SC -> MP3Party -> MP3TM -> "
            "AudioStart -> YouTube fallback"
        )

        print(
            "  Yandex + uncensored -> "
            "METADATA -> SC -> MP3Party -> MP3TM -> "
            "AudioStart -> YouTube fallback"
        )

        print()

    except Exception as error:

        print()
        print("=" * 70)
        print("ОШИБКА ПАТЧА.")
        print("=" * 70)
        print()
        print(
            f"{type(error).__name__}: {error}"
        )

        print()
        print(
            "Восстанавливаю резервные копии..."
        )

        shutil.copy2(
            downloader_backup,
            DOWNLOADER
        )

        shutil.copy2(
            bot_backup,
            BOT
        )

        print(
            "downloader.py восстановлен."
        )

        print(
            "bot.py восстановлен."
        )

        # Новые файлы удалить, чтобы после отката
        # не осталось частично применённой архитектуры.

        for path in (
            YOUTUBE_FAST,
            YANDEX_FAST
        ):

            if path.exists():

                try:
                    path.unlink()
                except Exception:
                    pass

        print()
        print(
            "Изменения откатились."
        )

        raise


if __name__ == "__main__":
    main()
