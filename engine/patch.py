# -*- coding: utf-8 -*-

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path


# ============================================================
# CENSURU.NET — YANDEX MUSIC HTML FALLBACK PATCH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADER = BASE_DIR / "downloader.py"


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(
        f"{path.stem}.backup_yandex_html_{timestamp}{path.suffix}"
    )
    shutil.copy2(path, backup)
    return backup


def check_function_exists(text: str, name: str) -> bool:
    pattern = rf"(?m)^def\s+{re.escape(name)}\s*\("
    return re.search(pattern, text) is not None


def find_function_block(text: str, name: str):
    """
    Находит тело обычной def-функции до следующей функции
    того же уровня.
    """
    pattern = rf"(?m)^def\s+{re.escape(name)}\s*\([^)]*\):"
    match = re.search(pattern, text)

    if not match:
        return None

    start = match.start()

    next_match = re.search(
        r"(?m)^def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(",
        text[match.end():],
    )

    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(text)

    return start, end


# ============================================================
# НОВЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

HELPERS = r'''

# ============================================================
# YANDEX MUSIC HTML FALLBACK
# ============================================================

def _extract_yandex_state_patches(html):
    """
    Извлекает объекты __STATE_PATCHES__ из HTML Яндекс Музыки.

    Яндекс отдаёт их примерно в таком виде:

    window.__STATE_PATCHES__ = window.__STATE_PATCHES__ || []
    ).push([
        {...},
        {...}
    ]);

    В HTML данные могут находиться внутри JSON-строк,
    поэтому сначала декодируем unicode escape-последовательности.
    """
    import json
    import re

    patches = []

    # Основной вариант: ищем содержимое push([...])
    pattern = re.compile(
        r'\(\s*window\.__STATE_PATCHES__\s*=\s*'
        r'window\.__STATE_PATCHES__\s*\|\|\s*\[\]\s*\)\.push'
        r'\(\s*(.*?)\s*\)\s*;',
        re.DOTALL,
    )

    for match in pattern.finditer(html):
        raw = match.group(1)

        # Обычно первый элемент массива — число/служебное значение,
        # второй — строка с JSON-подобным содержимым.
        try:
            value = ast.literal_eval(raw)
        except Exception:
            value = None

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    patches.append(item)

                elif isinstance(item, str):
                    # Строка может содержать экранированные данные.
                    try:
                        decoded = json.loads('"' + item.replace('"', '\\"') + '"')
                    except Exception:
                        decoded = item

                    # Ищем JSON-объекты внутри декодированной строки.
                    for obj_match in re.finditer(
                        r'\{.*?\}',
                        decoded,
                        re.DOTALL,
                    ):
                        chunk = obj_match.group(0)

                        try:
                            obj = json.loads(chunk)
                        except Exception:
                            continue

                        if isinstance(obj, dict):
                            patches.append(obj)

    return patches


def _extract_yandex_track_from_html(html, track_id):
    """
    Ищет полноценный объект трека в HTML страницы Яндекс Музыки.

    Основной ориентир:
        "path":"/playlist/items/N",
        "value":{
            "id":"TRACK_ID",
            ...
            "data":{
                ...
            }
        }

    Возвращает словарь data либо None.
    """
    import json

    track_id = str(track_id)

    # --------------------------------------------------------
    # Вариант 1. Прямой поиск блока вокруг нужного ID.
    # Это наиболее надёжный вариант для наблюдаемого HTML.
    # --------------------------------------------------------

    marker = f'"id":"{track_id}"'

    positions = []
    start = 0

    while True:
        pos = html.find(marker, start)

        if pos < 0:
            break

        positions.append(pos)
        start = pos + len(marker)

    for pos in positions:

        # Берём достаточно большой фрагмент после ID.
        chunk = html[pos:pos + 30000]

        data_pos = chunk.find('"data":{')

        if data_pos < 0:
            continue

        # ----------------------------------------------------
        # Извлекаем JSON-объект data методом балансировки скобок.
        # ----------------------------------------------------

        object_start = data_pos + len('"data":')

        while (
            object_start < len(chunk)
            and chunk[object_start].isspace()
        ):
            object_start += 1

        if object_start >= len(chunk):
            continue

        if chunk[object_start] != "{":
            continue

        depth = 0
        in_string = False
        escaped = False
        end = None

        for i in range(object_start, len(chunk)):

            char = chunk[i]

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
                    end = i + 1
                    break

        if end is None:
            continue

        raw_data = chunk[object_start:end]

        # JSON в HTML использует \u002F и т.п.
        try:
            data = json.loads(raw_data)
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        if str(data.get("id")) != track_id:
            continue

        return data

    return None


def _get_yandex_music_info_from_html(track_id, album_id=None):
    """
    HTML fallback для Яндекс Музыки.

    Используется только если основной API не смог получить
    метаданные трека.
    """
    import requests

    track_id = str(track_id)

    print("Yandex Music: fallback через HTML страницы...")

    urls = []

    if album_id:
        urls.append(
            f"https://music.yandex.ru/album/{album_id}/track/{track_id}"
        )

    urls.append(
        f"https://music.yandex.ru/track/{track_id}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    for url in urls:

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=15,
            )
        except Exception as exc:
            print(
                f"Yandex Music: ошибка HTML-запроса: {exc}"
            )
            continue

        if response.status_code != 200:
            print(
                f"Yandex Music: HTML HTTP {response.status_code}"
            )
            continue

        html = response.text

        data = _extract_yandex_track_from_html(
            html,
            track_id,
        )

        if not data:
            continue

        # ----------------------------------------------------
        # Исполнители
        # ----------------------------------------------------

        artists = data.get("artists") or []

        artist_names = []

        for artist in artists:
            if not isinstance(artist, dict):
                continue

            name = artist.get("name")

            if name:
                artist_names.append(str(name))

        artist = ", ".join(artist_names)

        # ----------------------------------------------------
        # Основные поля
        # ----------------------------------------------------

        title = data.get("title") or ""

        duration_ms = data.get("durationMs")

        duration = None

        if duration_ms is not None:
            try:
                duration = float(duration_ms) / 1000.0
            except Exception:
                duration = None

        actual_album_id = data.get("albumId") or album_id

        albums = data.get("albums") or []

        album = ""

        if albums and isinstance(albums[0], dict):
            album = albums[0].get("title") or ""

        # ----------------------------------------------------
        # Обложка
        # ----------------------------------------------------

        cover_uri = data.get("coverUri") or ""

        cover_url = None

        if cover_uri:
            cover_url = "https://" + str(cover_uri)

            cover_url = cover_url.replace(
                "%%",
                "1000x1000",
            )

        # ----------------------------------------------------
        # Lyrics flags
        # ----------------------------------------------------

        has_lyrics = bool(
            data.get("hasLyrics")
        )

        has_sync_lyrics = bool(
            data.get("hasSyncLyrics")
        )

        print(
            "Yandex Music: данные получены из HTML."
        )

        print(
            f"  Исполнитель: {artist}"
        )

        print(
            f"  Название: {title}"
        )

        if duration is not None:
            print(
                f"  Длительность: {duration:.2f} сек."
            )

        print(
            f"  Album ID: {actual_album_id}"
        )

        print(
            f"  Lyrics: {has_lyrics}"
        )

        print(
            f"  Sync lyrics: {has_sync_lyrics}"
        )

        return {
            "artist": artist,
            "title": title,
            "album": album,
            "duration": duration,
            "cover_url": cover_url,
            "track_id": str(
                data.get("id") or track_id
            ),
            "album_id": (
                str(actual_album_id)
                if actual_album_id is not None
                else None
            ),
            "has_lyrics": has_lyrics,
            "has_sync_lyrics": has_sync_lyrics,
        }

    print(
        "Yandex Music: HTML fallback также не дал данных."
    )

    return None

'''


# ============================================================
# НОВАЯ ВЕРСИЯ get_yandex_music_info
# ============================================================

NEW_FUNCTION = r'''def get_yandex_music_info(track_id, album_id=None):
    """
    Получает метаданные трека Яндекс Музыки.

    Основной источник:
        API Яндекс Музыки.

    Резервный источник:
        HTML страницы трека с __STATE_PATCHES__.

    HTML fallback используется только при проблеме с API.
    """

    import requests

    track_id = str(track_id)

    # ========================================================
    # 1. ОСНОВНОЙ API
    # ========================================================

    url = (
        f"https://api.music.yandex.net/tracks/"
        f"{track_id}"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:

            payload = response.json()

            result = payload.get("result")

            if isinstance(result, list) and result:

                track = result[0]

                artists = track.get("artists") or []

                artist_names = []

                for item in artists:

                    if not isinstance(item, dict):
                        continue

                    name = item.get("name")

                    if name:
                        artist_names.append(
                            str(name)
                        )

                artist = ", ".join(
                    artist_names
                )

                title = (
                    track.get("title")
                    or ""
                )

                duration = None

                duration_ms = (
                    track.get("durationMs")
                )

                if duration_ms is not None:

                    try:
                        duration = (
                            float(duration_ms)
                            / 1000.0
                        )
                    except Exception:
                        duration = None

                albums = (
                    track.get("albums")
                    or []
                )

                album = ""

                actual_album_id = album_id

                if albums:

                    first_album = albums[0]

                    if isinstance(
                        first_album,
                        dict,
                    ):

                        album = (
                            first_album.get(
                                "title"
                            )
                            or ""
                        )

                        actual_album_id = (
                            first_album.get(
                                "id"
                            )
                            or actual_album_id
                        )

                cover_uri = (
                    track.get("coverUri")
                    or ""
                )

                cover_url = None

                if cover_uri:

                    cover_url = (
                        "https://"
                        + str(cover_uri)
                    )

                    cover_url = (
                        cover_url.replace(
                            "%%",
                            "1000x1000",
                        )
                    )

                has_lyrics = bool(
                    track.get("hasLyrics")
                )

                has_sync_lyrics = bool(
                    track.get(
                        "hasSyncLyrics"
                    )
                )

                print(
                    "Yandex Music: метаданные "
                    "получены через API."
                )

                return {
                    "artist": artist,
                    "title": title,
                    "album": album,
                    "duration": duration,
                    "cover_url": cover_url,
                    "track_id": str(
                        track.get("id")
                        or track_id
                    ),
                    "album_id": (
                        str(actual_album_id)
                        if actual_album_id
                        is not None
                        else None
                    ),
                    "has_lyrics": has_lyrics,
                    "has_sync_lyrics":
                        has_sync_lyrics,
                }

            print(
                "Yandex Music: API вернул "
                "неожиданный формат данных."
            )

        else:

            print(
                "Yandex Music: API HTTP "
                f"{response.status_code}."
            )

    except Exception as exc:

        print(
            "Yandex Music: ошибка API: "
            f"{exc}"
        )

    # ========================================================
    # 2. HTML FALLBACK
    # ========================================================

    print(
        "Yandex Music: переход к HTML fallback..."
    )

    return _get_yandex_music_info_from_html(
        track_id,
        album_id,
    )

'''


def patch_file():
    print("=" * 70)
    print("CENSURU.NET — YANDEX MUSIC HTML FALLBACK PATCH")
    print("=" * 70)

    if not DOWNLOADER.exists():
        print()
        print("ОШИБКА: downloader.py не найден:")
        print(DOWNLOADER)
        return False

    print()
    print("1. Проверка downloader.py...")

    text = DOWNLOADER.read_text(
        encoding="utf-8"
    )

    if not check_function_exists(
        text,
        "get_yandex_music_info",
    ):
        print(
            "ОШИБКА: функция "
            "get_yandex_music_info() не найдена."
        )
        return False

    print(
        "  OK: get_yandex_music_info() найдена."
    )

    # --------------------------------------------------------
    # Проверяем, не применён ли патч уже.
    # --------------------------------------------------------

    if (
        "_get_yandex_music_info_from_html"
        in text
    ):
        print()
        print(
            "Патч уже присутствует в downloader.py."
        )
        print(
            "Изменения повторно не выполняются."
        )
        return True

    # --------------------------------------------------------
    # Проверяем наличие ast.
    # --------------------------------------------------------

    if not re.search(
        r"(?m)^import\s+ast\s*$",
        text,
    ) and not re.search(
        r"(?m)^from\s+ast\s+import\s+",
        text,
    ):

        # Добавляем import ast в начало.
        text = "import ast\n" + text

    # --------------------------------------------------------
    # Находим текущую функцию.
    # --------------------------------------------------------

    block = find_function_block(
        text,
        "get_yandex_music_info",
    )

    if not block:
        print(
            "ОШИБКА: не удалось определить "
            "границы get_yandex_music_info()."
        )
        return False

    start, end = block

    old_function = text[start:end]

    print()
    print(
        "2. Текущая функция найдена."
    )

    print(
        f"  Размер старой функции: "
        f"{len(old_function)} символов"
    )

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    print()
    print("3. Создание резервной копии...")

    backup = backup_file(DOWNLOADER)

    print(
        f"  Backup: {backup.name}"
    )

    # --------------------------------------------------------
    # Вставляем helpers перед функцией.
    # --------------------------------------------------------

    new_text = (
        text[:start]
        + HELPERS
        + "\n\n"
        + NEW_FUNCTION
        + "\n"
        + text[end:]
    )

    # --------------------------------------------------------
    # Запись.
    # --------------------------------------------------------

    print()
    print(
        "4. Запись изменённого downloader.py..."
    )

    DOWNLOADER.write_text(
        new_text,
        encoding="utf-8",
        newline="\n",
    )

    # --------------------------------------------------------
    # Проверка синтаксиса.
    # --------------------------------------------------------

    print()
    print(
        "5. Проверка синтаксиса..."
    )

    try:
        compile(
            new_text,
            str(DOWNLOADER),
            "exec",
        )
    except SyntaxError as exc:

        print()
        print(
            "ОШИБКА СИНТАКСИСА!"
        )

        print(
            f"  Строка: {exc.lineno}"
        )

        print(
            f"  Причина: {exc.msg}"
        )

        print()
        print(
            "Восстановление из backup..."
        )

        shutil.copy2(
            backup,
            DOWNLOADER,
        )

        print(
            "Исходный downloader.py восстановлен."
        )

        return False

    print(
        "  OK: синтаксис корректен."
    )

    # --------------------------------------------------------
    # Проверяем функции.
    # --------------------------------------------------------

    required = [
        "get_yandex_music_info",
        "_extract_yandex_state_patches",
        "_extract_yandex_track_from_html",
        "_get_yandex_music_info_from_html",
    ]

    print()
    print(
        "6. Проверка установленных функций..."
    )

    for name in required:

        if check_function_exists(
            new_text,
            name,
        ):
            print(
                f"  OK: {name}"
            )
        else:
            print(
                f"  ERROR: {name} не найдена."
            )

            print(
                "Восстановление backup..."
            )

            shutil.copy2(
                backup,
                DOWNLOADER,
            )

            return False

    print()
    print("=" * 70)
    print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
    print("=" * 70)

    print()
    print(
        "Теперь порядок получения данных:"
    )

    print(
        "  1. API Яндекс Музыки"
    )

    print(
        "  2. HTML страницы трека"
    )

    print(
        "  3. __STATE_PATCHES__ → data трека"
    )

    print()
    print(
        "Резервная копия:"
    )

    print(
        f"  {backup}"
    )

    return True


if __name__ == "__main__":
    try:
        success = patch_file()
    except Exception as exc:
        print()
        print(
            "КРИТИЧЕСКАЯ ОШИБКА:"
        )
        print(exc)
        success = False

    print()

    if success:
        print(
            "Готово. Теперь можно запускать downloader.py."
        )
    else:
        print(
            "Патч НЕ применён либо был автоматически отменён."
        )

    input(
        "\nНажмите Enter для выхода..."
)
