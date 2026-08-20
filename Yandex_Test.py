import os
import sys
import json
import subprocess


# ============================================================
# НАСТРОЙКИ
# ============================================================

SCRIPT_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

YTDLP = os.path.join(
    SCRIPT_FOLDER,
    "tools",
    "yt-dlp.exe"
)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def print_line():
    print("=" * 60)


def format_duration(seconds):
    if seconds is None:
        return "??:??"

    try:
        seconds = int(round(float(seconds)))
    except Exception:
        return "??:??"

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


def get_artist(data):
    """
    Яндекс/yt-dlp может возвращать исполнителя
    в разных полях.
    """

    artist = data.get("artist")

    if artist:
        return str(artist)

    artists = data.get("artists")

    if isinstance(artists, list):

        names = []

        for item in artists:

            if isinstance(item, dict):

                name = item.get("name")

                if name:
                    names.append(
                        str(name)
                    )

            elif isinstance(item, str):
                names.append(item)

        if names:
            return ", ".join(names)

    uploader = data.get("uploader")

    if uploader:
        return str(uploader)

    creator = data.get("creator")

    if creator:
        return str(creator)

    return ""


def get_title(data):

    return (
        data.get("track")
        or data.get("title")
        or ""
    )


def get_album(data):

    return (
        data.get("album")
        or ""
    )


def get_cover(data):

    thumbnail = data.get("thumbnail")

    if thumbnail:
        return thumbnail

    thumbnails = data.get("thumbnails")

    if isinstance(thumbnails, list):

        for item in reversed(thumbnails):

            if isinstance(item, dict):

                url = item.get("url")

                if url:
                    return url

    return None


def print_track_info(data, number=None):

    if number is not None:

        print()
        print_line()
        print(
            f"ТРЕК {number}"
        )
        print_line()

    artist = get_artist(data)
    title = get_title(data)
    album = get_album(data)

    duration = data.get("duration")

    cover = get_cover(data)

    print()
    print("Исполнитель: ", artist or "не определён")
    print("Название:    ", title or "не определено")
    print("Альбом:      ", album or "не определён")
    print(
        "Длительность:",
        format_duration(duration)
    )

    print(
        "Обложка:     ",
        "получена" if cover else "не найдена"
    )

    print()

    webpage_url = (
        data.get("webpage_url")
        or data.get("original_url")
        or ""
    )

    if webpage_url:
        print(
            "URL:",
            webpage_url
        )


# ============================================================
# ПРОВЕРКА YT-DLP
# ============================================================

def check_ytdlp():

    if not os.path.exists(YTDLP):

        print()
        print("ОШИБКА:")
        print(
            "yt-dlp.exe не найден."
        )
        print()
        print(
            "Ожидаемое расположение:"
        )
        print(
            YTDLP
        )

        return False

    return True


def get_ytdlp_version():

    try:

        result = subprocess.run(
            [
                YTDLP,
                "--version"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        version = result.stdout.strip()

        if version:
            print(
                "Версия yt-dlp:",
                version
            )

        return True

    except Exception as e:

        print(
            "Не удалось определить версию yt-dlp:",
            e
        )

        return False


# ============================================================
# ПОЛУЧЕНИЕ ДАННЫХ
# ============================================================

def get_yandex_info(url):

    print()
    print("Получение информации через yt-dlp...")
    print()

    command = [
        YTDLP,

        "--dump-single-json",

        "--no-download",

        "--no-warnings",

        "--no-playlist",

        "--ignore-config",

        url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )

    except subprocess.TimeoutExpired:

        print()
        print(
            "ОШИБКА: yt-dlp слишком долго "
            "получает данные."
        )

        return None

    except Exception as e:

        print()
        print(
            "ОШИБКА запуска yt-dlp:",
            e
        )

        return None

    if result.returncode != 0:

        print()
        print(
            "yt-dlp вернул ошибку."
        )

        print()

        if result.stderr:

            print(
                "Сообщение yt-dlp:"
            )

            print(
                result.stderr.strip()
            )

        return None

    output = result.stdout.strip()

    if not output:

        print()
        print(
            "yt-dlp не вернул данных."
        )

        return None

    try:

        data = json.loads(output)

        return data

    except json.JSONDecodeError:

        print()
        print(
            "ОШИБКА: yt-dlp вернул "
            "не JSON."
        )

        print()
        print(
            "Полученный ответ:"
        )

        print(
            output[:5000]
        )

        return None


# ============================================================
# ОПРЕДЕЛЕНИЕ ТИПА
# ============================================================

def detect_url_type(url):

    url_lower = url.lower()

    if "/album/" in url_lower:
        return "альбом"

    if "/playlists/" in url_lower:
        return "плейлист"

    if "/playlist/" in url_lower:
        return "плейлист"

    if "/track/" in url_lower:
        return "трек"

    return "неизвестный тип"


# ============================================================
# АНАЛИЗ ОТВЕТА
# ============================================================

def analyze_result(data):

    if not isinstance(data, dict):

        print()
        print(
            "Ответ имеет неожиданный формат."
        )

        return

    entries = data.get("entries")

    if isinstance(entries, list):

        valid_entries = [
            item
            for item in entries
            if isinstance(item, dict)
        ]

        print()
        print_line()
        print(
            "РЕЗУЛЬТАТ"
        )
        print_line()

        print()
        print(
            "Название:",
            data.get("title")
            or "не определено"
        )

        print(
            "Количество элементов:",
            len(valid_entries)
        )

        for index, entry in enumerate(
            valid_entries,
            1
        ):

            print_track_info(
                entry,
                index
            )

        return

    print()
    print_line()
    print(
        "РЕЗУЛЬТАТ"
    )
    print_line()

    print_track_info(data)


# ============================================================
# MAIN
# ============================================================

def main():

    print_line()
    print(
        "YANDEX MUSIC TEST"
    )
    print_line()

    print()

    if not check_ytdlp():

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    get_ytdlp_version()

    print()

    print(
        "Этот тест ничего не скачивает."
    )

    print(
        "Он только проверяет получение "
        "метаданных через yt-dlp."
    )

    print()

    url = input(
        "Ссылка на Яндекс Музыку: "
    ).strip()

    if not url:

        print()
        print(
            "Ссылка не указана."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    print()

    if (
        "music.yandex.ru" not in url.lower()
        and
        "music.yandex.com" not in url.lower()
    ):

        print(
            "ВНИМАНИЕ:"
        )

        print(
            "Ссылка не похожа на ссылку "
            "Яндекс Музыки."
        )

        print()

        choice = input(
            "Продолжить? [y/n]: "
        ).strip().lower()

        if choice not in (
            "y",
            "д",
            "да"
        ):

            return

    print()

    print(
        "Тип ссылки:",
        detect_url_type(url)
    )

    print()

    data = get_yandex_info(url)

    if data is None:

        print()
        print_line()
        print(
            "ТЕСТ НЕ ПРОЙДЕН"
        )
        print_line()

        print()
        print(
            "Яндекс Музыка не вернула "
            "корректные данные через yt-dlp."
        )

    else:

        analyze_result(data)

        print()
        print_line()
        print(
            "ТЕСТ ПРОЙДЕН"
        )
        print_line()

        print()
        print(
            "yt-dlp смог получить данные "
            "из Яндекс Музыки."
        )

    print()

    input(
        "Нажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
