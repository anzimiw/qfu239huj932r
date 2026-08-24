# -*- coding: utf-8 -*-

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path


DOWNLOADER = Path(__file__).resolve().parent / "downloader.py"


def find_function(text, name):
    pattern = rf"(?m)^def\s+{re.escape(name)}\s*\("
    match = re.search(pattern, text)

    if not match:
        return None

    start = match.start()

    next_match = re.search(
        r"(?m)^def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(",
        text[match.end():]
    )

    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(text)

    return start, end


def backup(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(
        f"{path.stem}.backup_yandex_v2_{timestamp}{path.suffix}"
    )
    shutil.copy2(path, target)
    return target


HELPERS = r'''

# ============================================================
# YANDEX MUSIC HTML FALLBACK V2
# ============================================================

def _yandex_extract_balanced_json(text, start):
    """
    Извлекает JSON-объект начиная с позиции '{',
    корректно учитывая вложенные объекты и строки.
    """

    if start < 0 or start >= len(text):
        return None

    if text[start] != "{":
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[start:index + 1]

    return None


def _yandex_find_track_data_in_html(html_text, track_id):
    """
    Ищет полноценный объект data нужного трека
    непосредственно в HTML страницы Яндекс Музыки.

    Ожидаемая структура:

    "value":{
        "id":"154676063",
        ...
        "data":{
            "id":"154676063",
            "title":"Отражение",
            ...
        }
    }
    """

    track_id = str(track_id)

    marker = f'"id":"{track_id}"'

    position = 0

    while True:
        position = html_text.find(marker, position)

        if position < 0:
            return None

        # Берём разумный участок после найденного ID.
        chunk_end = min(
            len(html_text),
            position + 50000
        )

        chunk = html_text[position:chunk_end]

        # Ищем data после найденного ID.
        data_marker = '"data":'

        data_position = chunk.find(data_marker)

        if data_position >= 0:

            object_start = (
                position
                + data_position
                + len(data_marker)
            )

            while (
                object_start < len(html_text)
                and html_text[object_start].isspace()
            ):
                object_start += 1

            if (
                object_start < len(html_text)
                and html_text[object_start] == "{"
            ):

                raw = _yandex_extract_balanced_json(
                    html_text,
                    object_start
                )

                if raw:

                    try:
                        data = json.loads(raw)
                    except Exception:
                        data = None

                    if isinstance(data, dict):

                        if str(data.get("id")) == track_id:
                            return data

        position += len(marker)


def _yandex_music_info_from_html(
    track_id,
    album_id
):
    """
    Резервное получение метаданных Яндекс Музыки
    непосредственно из HTML страницы трека.
    """

    print(
        "Получение метаданных непосредственно "
        "со страницы Яндекс Музыки..."
    )

    urls = []

    if album_id:
        urls.append(
            "https://music.yandex.ru/"
            f"album/{album_id}/track/{track_id}"
        )

    urls.append(
        f"https://music.yandex.ru/track/{track_id}"
    )

    for page_url in urls:

        try:
            response = requests.get(
                page_url,
                headers=HEADERS,
                timeout=TIMEOUT
            )

        except requests.RequestException as exc:

            print(
                "Ошибка получения HTML Яндекс Музыки: "
                f"{exc}"
            )

            continue

        if response.status_code != 200:

            print(
                "HTML Яндекс Музыки вернул HTTP "
                f"{response.status_code}"
            )

            continue

        html_text = response.text

        track = _yandex_find_track_data_in_html(
            html_text,
            track_id
        )

        if not isinstance(track, dict):
            continue

        artists = track.get("artists") or []

        artist_names = []

        for item in artists:

            if (
                isinstance(item, dict)
                and item.get("name")
            ):
                artist_names.append(
                    str(item["name"])
                )

        artist = ", ".join(
            artist_names
        )

        title = (
            track.get("title")
            or ""
        )

        album = ""

        actual_album_id = (
            track.get("albumId")
            or album_id
        )

        albums = track.get("albums") or []

        if albums:

            first_album = albums[0]

            if isinstance(
                first_album,
                dict
            ):

                album = (
                    first_album.get("title")
                    or ""
                )

                actual_album_id = (
                    first_album.get("id")
                    or actual_album_id
                )

        duration = None

        duration_ms = (
            track.get("durationMs")
        )

        if duration_ms is not None:

            try:
                duration = (
                    float(duration_ms)
                    / 1000
                )

            except Exception:
                pass

        cover_uri = (
            track.get("coverUri")
            or track.get("ogImage")
        )

        cover_url = None

        if cover_uri:

            cover_url = str(
                cover_uri
            ).replace(
                "%%",
                "720x720"
            )

            if cover_url.startswith("//"):

                cover_url = (
                    "https:"
                    + cover_url
                )

            elif not cover_url.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                cover_url = (
                    "https://"
                    + cover_url
                )

        print(
            "Метаданные получены "
            "непосредственно со страницы "
            "Яндекс Музыки."
        )

        print(
            f"Исполнитель: {artist}"
        )

        print(
            f"Название: {title}"
        )

        print(
            f"Альбом: "
            f"{album or 'не определён'}"
        )

        print(
            f"Длительность: "
            f"{format_duration(duration)}"
        )

        print(
            "Обложка: "
            f"{'НАЙДЕНА' if cover_url else 'НЕ НАЙДЕНА'}"
        )

        if (
            not artist
            or not title
            or duration is None
        ):
            print(
                "HTML найден, но обязательные "
                "поля трека отсутствуют."
            )

            continue

        return {
            "source": "yandex",
            "artist": artist,
            "title": title,
            "album": album,
            "duration": duration,
            "cover_url": cover_url,
            "track_id": track_id,
            "album_id": (
                str(actual_album_id)
                if actual_album_id
                else ""
            )
        }

    print(
        "Не удалось получить метаданные "
        "Яндекс Музыки из HTML."
    )

    return None

'''


NEW_FUNCTION = r'''def get_yandex_music_info(url):
    status(
        "Получение информации из Яндекс Музыки..."
    )

    parsed = parse_yandex_url(url)

    if not parsed:
        print(
            "Не удалось определить ID трека "
            "Яндекс Музыки."
        )
        return None

    track_id = parsed["track_id"]
    album_id = parsed["album_id"]

    # ========================================================
    # 1. ОСНОВНОЙ API
    # ========================================================

    try:
        response = requests.get(
            f"https://api.music.yandex.net/tracks/{track_id}",
            headers=YANDEX_HEADERS,
            timeout=TIMEOUT
        )

    except requests.RequestException as exc:

        print(
            "Не удалось получить данные "
            "Яндекс Музыки через API."
        )

        print(
            f"Ошибка: {exc}"
        )

        print(
            "Переход к получению данных "
            "непосредственно со страницы..."
        )

        return _yandex_music_info_from_html(
            track_id,
            album_id
        )

    if response.status_code != 200:

        print(
            "Не удалось получить метаданные "
            "трека через API."
        )

        print(
            f"HTTP: {response.status_code}"
        )

        print(
            "Переход к получению данных "
            "непосредственно со страницы..."
        )

        return _yandex_music_info_from_html(
            track_id,
            album_id
        )

    try:

        data = response.json()

    except Exception:

        print(
            "Не удалось обработать данные "
            "Яндекс Музыки."
        )

        print(
            "Переход к получению данных "
            "непосредственно со страницы..."
        )

        return _yandex_music_info_from_html(
            track_id,
            album_id
        )

    result = data.get("result")

    if isinstance(result, dict):

        result = result.get(
            "track",
            result
        )

    elif isinstance(result, list):

        result = (
            result[0]
            if result
            else None
        )

    if not isinstance(result, dict):

        print(
            "API Яндекс Музыки не вернул "
            "данные трека."
        )

        print(
            "Переход к получению данных "
            "непосредственно со страницы..."
        )

        return _yandex_music_info_from_html(
            track_id,
            album_id
        )

    track = result

    artists = (
        track.get("artists")
        or []
    )

    artist = ", ".join(
        str(x.get("name"))
        for x in artists
        if (
            isinstance(x, dict)
            and x.get("name")
        )
    )

    title = (
        track.get("title")
        or ""
    )

    album = ""

    albums = track.get("albums")

    if (
        isinstance(albums, list)
        and albums
        and isinstance(
            albums[0],
            dict
        )
    ):

        album = (
            albums[0].get("title")
            or ""
        )

        album_id = str(
            albums[0].get("id")
            or album_id
        )

    duration = None

    if track.get("durationMs") is not None:

        try:

            duration = (
                float(
                    track["durationMs"]
                )
                / 1000
            )

        except Exception:
            pass

    cover_uri = (
        track.get("coverUri")
        or track.get("ogImage")
    )

    cover_url = None

    if cover_uri:

        cover_url = str(
            cover_uri
        ).replace(
            "%%",
            "720x720"
        )

        if cover_url.startswith("//"):

            cover_url = (
                "https:"
                + cover_url
            )

        elif not cover_url.startswith(
            (
                "http://",
                "https://"
            )
        ):

            cover_url = (
                "https://"
                + cover_url
            )

    if (
        not artist
        or not title
        or duration is None
    ):

        print(
            "API получил неполные данные "
            "трека."
        )

        print(
            "Переход к получению данных "
            "непосредственно со страницы..."
        )

        return _yandex_music_info_from_html(
            track_id,
            album_id
        )

    print(
        f"Исполнитель: {artist}"
    )

    print(
        f"Название: {title}"
    )

    print(
        f"Альбом: "
        f"{album or 'не определён'}"
    )

    print(
        f"Длительность: "
        f"{format_duration(duration)}"
    )

    print(
        "Обложка: "
        f"{'НАЙДЕНА' if cover_url else 'НЕ НАЙДЕНА'}"
    )

    return {
        "source": "yandex",
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration,
        "cover_url": cover_url,
        "track_id": track_id,
        "album_id": album_id
    }

'''


def main():

    print("=" * 70)
    print(
        "CENSURU.NET — YANDEX HTML FALLBACK V2"
    )
    print("=" * 70)

    if not DOWNLOADER.exists():

        print()
        print(
            "ОШИБКА: downloader.py не найден:"
        )

        print(DOWNLOADER)

        return

    text = DOWNLOADER.read_text(
        encoding="utf-8"
    )

    print()
    print(
        "1. Проверка текущей структуры..."
    )

    current = find_function(
        text,
        "get_yandex_music_info"
    )

    if not current:

        print(
            "ОШИБКА: get_yandex_music_info() "
            "не найдена."
        )

        return

    print(
        "  OK: функция найдена."
    )

    # Если предыдущий неудачный патч всё-таки
    # присутствует, удаляем его вспомогательные
    # функции перед установкой V2.
    helper_names = [
        "_extract_yandex_state_patches",
        "_extract_yandex_track_from_html",
        "_get_yandex_music_info_from_html",
        "_yandex_music_info_from_html",
        "_yandex_find_track_data_in_html",
        "_yandex_extract_balanced_json",
    ]

    for name in helper_names:

        if find_function(text, name):

            print(
                f"  Обнаружена старая helper-функция: "
                f"{name}"
            )

    print()
    print(
        "2. Создание резервной копии..."
    )

    backup_file = backup(
        DOWNLOADER
    )

    print(
        f"  Backup: {backup_file.name}"
    )

    # --------------------------------------------------------
    # Удаляем старые helper-функции, если они есть.
    # --------------------------------------------------------

    for name in helper_names:

        block = find_function(
            text,
            name
        )

        if block:

            start, end = block

            text = (
                text[:start]
                + text[end:]
            )

    # --------------------------------------------------------
    # Повторно ищем get_yandex_music_info.
    # --------------------------------------------------------

    current = find_function(
        text,
        "get_yandex_music_info"
    )

    start, end = current

    old_function = text[start:end]

    # --------------------------------------------------------
    # Добавляем helpers непосредственно перед
    # get_yandex_music_info.
    # --------------------------------------------------------

    new_text = (
        text[:start]
        + HELPERS
        + "\n"
        + NEW_FUNCTION
        + "\n"
        + text[end:]
    )

    print()
    print(
        "3. Установка HTML fallback V2..."
    )

    DOWNLOADER.write_text(
        new_text,
        encoding="utf-8",
        newline="\n"
    )

    print()
    print(
        "4. Проверка синтаксиса..."
    )

    try:

        compile(
            new_text,
            str(DOWNLOADER),
            "exec"
        )

    except SyntaxError as exc:

        print(
            "ОШИБКА СИНТАКСИСА!"
        )

        print(
            f"Строка: {exc.lineno}"
        )

        print(
            f"Причина: {exc.msg}"
        )

        print()
        print(
            "Восстанавливаю backup..."
        )

        shutil.copy2(
            backup_file,
            DOWNLOADER
        )

        print(
            "Исходный файл восстановлен."
        )

        return

    print(
        "  OK: синтаксис корректен."
    )

    print()
    print(
        "5. Проверка функций..."
    )

    checks = [
        "_yandex_extract_balanced_json",
        "_yandex_find_track_data_in_html",
        "_yandex_music_info_from_html",
        "get_yandex_music_info",
    ]

    for name in checks:

        if find_function(
            new_text,
            name
        ):

            print(
                f"  OK: {name}"
            )

        else:

            print(
                f"  ERROR: {name}"
            )

            print(
                "Восстанавливаю backup..."
            )

            shutil.copy2(
                backup_file,
                DOWNLOADER
            )

            return

    print()
    print("=" * 70)
    print(
        "ПАТЧ V2 УСПЕШНО ПРИМЕНЁН"
    )
    print("=" * 70)

    print()
    print(
        "Резервная копия:"
    )

    print(
        f"  {backup_file}"
    )

    print()
    print(
        "Теперь get_yandex_music_info() работает так:"
    )

    print(
        "  URL → API → HTML fallback"
    )

    print()
    print(
        "Следующий тест выполняем именно URL-ом."
    )


if __name__ == "__main__":
    main()
