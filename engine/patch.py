import os
import re
import json
import shutil
from datetime import datetime


FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "downloader.py"
)


def backup_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.backup_{timestamp}"
    shutil.copy2(path, backup)
    return backup


def find_function_end(lines, start_index):
    """
    Находит конец функции по следующей функции
    с нулевым уровнем отступа.
    """
    for i in range(start_index + 1, len(lines)):
        line = lines[i]

        if (
            line.startswith("def ")
            or line.startswith("class ")
        ):
            return i

    return len(lines)


def patch_playlist_functions(text):
    """
    Добавляет:
      - extract_yandex_playlist_state()
      - get_playlist_tracks()

    Если старые версии этих функций уже существуют,
    они заменяются.
    """

    lines = text.splitlines(keepends=True)

    new_functions = r'''
# ==============================================================
# YANDEX MUSIC PLAYLIST PARSER
# ==============================================================

def _extract_balanced_json_array(text, start):
    """
    Извлекает JSON-массив, начиная с позиции '['.

    Учитывает:
      - вложенные массивы;
      - объекты;
      - строки;
      - escaped quotes.
    """

    if start < 0 or start >= len(text):
        return None

    if text[start] != "[":
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start,
        len(text)
    ):
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

        if char == "[":
            depth += 1

        elif char == "]":
            depth -= 1

            if depth == 0:
                return text[
                    start:index + 1
                ]

    return None


def _extract_yandex_state_patch_arrays(text):
    """
    Извлекает массивы из конструкций:

    window.__STATE_PATCHES__ = ...
    .push([...]);

    Яндекс сейчас передаёт состояние плейлиста
    именно через такие state patches.
    """

    arrays = []

    marker = ".push("

    position = 0

    while True:
        position = text.find(
            marker,
            position
        )

        if position < 0:
            break

        array_start = text.find(
            "[",
            position + len(marker)
        )

        if array_start < 0:
            break

        array_text = (
            _extract_balanced_json_array(
                text,
                array_start
            )
        )

        if array_text:
            try:
                data = json.loads(
                    array_text
                )

                if isinstance(
                    data,
                    list
                ):
                    arrays.append(data)

            except Exception:
                pass

            position = (
                array_start
                + len(array_text)
            )

        else:
            position = (
                array_start + 1
            )

    return arrays


def _set_yandex_playlist_item(
    items,
    index,
    value
):
    """
    Устанавливает элемент плейлиста
    по индексу.
    """

    try:
        index = int(index)
    except Exception:
        return

    while len(items) <= index:
        items.append(None)

    items[index] = value


def _apply_yandex_playlist_patch(
    state,
    operation
):
    """
    Применяет один STATE_PATCH.

    Поддерживаются операции add/replace,
    которые реально используются в полученном
    HTML Яндекс Музыки.
    """

    if not isinstance(
        operation,
        dict
    ):
        return

    op = operation.get("op")

    if op not in (
        "add",
        "replace"
    ):
        return

    path = operation.get(
        "path"
    )

    if not isinstance(
        path,
        str
    ):
        return

    value = operation.get(
        "value"
    )

    # ----------------------------------------------------------
    # playlist/meta
    # ----------------------------------------------------------

    if path == "/playlist/meta":
        state["meta"] = value
        return

    # ----------------------------------------------------------
    # playlist/uuid
    # ----------------------------------------------------------

    if path == "/playlist/uuid":
        state["uuid"] = value
        return

    # ----------------------------------------------------------
    # playlist/items/N
    # ----------------------------------------------------------

    match = re.fullmatch(
        r"/playlist/items/(\d+)",
        path
    )

    if match:
        index = match.group(1)

        _set_yandex_playlist_item(
            state["items"],
            index,
            value
        )

        return

    # ----------------------------------------------------------
    # playlist/items/N/...
    # ----------------------------------------------------------

    match = re.fullmatch(
        r"/playlist/items/(\d+)/(.+)",
        path
    )

    if match:
        index = match.group(1)
        field = match.group(2)

        try:
            index = int(index)
        except Exception:
            return

        items = state["items"]

        while len(items) <= index:
            items.append({})

        if not isinstance(
            items[index],
            dict
        ):
            items[index] = {}

        items[index][field] = value


def extract_yandex_playlist_state(
    html_text
):
    """
    Извлекает финальное состояние Яндекс-плейлиста
    из window.__STATE_PATCHES__.

    Возвращает:

    {
        "uuid": ...,
        "meta": {...},
        "items": [...]
    }

    """

    if not html_text:
        return None

    state = {
        "uuid": "",
        "meta": {},
        "items": []
    }

    patch_arrays = (
        _extract_yandex_state_patch_arrays(
            html_text
        )
    )

    if not patch_arrays:
        print(
            "Яндекс: STATE_PATCHES "
            "не найдены."
        )
        return None

    operation_count = 0

    for patch_array in patch_arrays:

        for entry in patch_array:

            operation = entry

            # Некоторые структуры могут
            # содержать вложенные массивы.
            if isinstance(
                entry,
                list
            ):
                for nested in entry:
                    if isinstance(
                        nested,
                        dict
                    ):
                        _apply_yandex_playlist_patch(
                            state,
                            nested
                        )

                        operation_count += 1

            elif isinstance(
                operation,
                dict
            ):
                _apply_yandex_playlist_patch(
                    state,
                    operation
                )

                operation_count += 1

    if not state["items"]:
        print(
            "Яндекс: элементы плейлиста "
            "в STATE_PATCHES не найдены."
        )
        return None

    meta = state.get(
        "meta"
    )

    if not isinstance(
        meta,
        dict
    ):
        meta = {}

    state["meta"] = meta

    print(
        "Яндекс: STATE_PATCHES обработаны."
    )

    print(
        "Яндекс: операций обработано:",
        operation_count
    )

    print(
        "Яндекс: название плейлиста:",
        meta.get(
            "title",
            "Без названия"
        )
    )

    print(
        "Яндекс: элементов найдено:",
        len(state["items"])
    )

    return state


def get_playlist_tracks(
    url
):
    """
    Получает список треков Яндекс-плейлиста.

    Возвращает:

    {
        "title": "...",
        "tracks": [
            "https://music.yandex.ru/album/.../track/...",
            ...
        ]
    }
    """

    print(
        "Получение списка треков плейлиста..."
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

    except requests.RequestException as e:
        print(
            "Не удалось получить страницу "
            "плейлиста Яндекс Музыки."
        )

        print(
            "Ошибка:",
            e
        )

        return None

    if response.status_code != 200:
        print(
            "Яндекс: HTTP-код:",
            response.status_code
        )

        return None

    html_text = response.text

    state = extract_yandex_playlist_state(
        html_text
    )

    if not state:
        print(
            "Яндекс: не удалось извлечь "
            "состояние плейлиста."
        )

        return None

    meta = state.get(
        "meta"
    ) or {}

    playlist_title = (
        meta.get(
            "title"
        )
        or "Яндекс-плейлист"
    )

    tracks = []

    for index, item in enumerate(
        state.get(
            "items",
            []
        ),
        1
    ):

        if not isinstance(
            item,
            dict
        ):
            continue

        track_id = (
            item.get(
                "id"
            )
        )

        album_id = (
            item.get(
                "albumId"
            )
        )

        data = item.get(
            "data"
        )

        # В финальном RESOLVE data содержит
        # настоящие track/album ID.
        if isinstance(
            data,
            dict
        ):

            track_id = (
                data.get(
                    "id"
                )
                or data.get(
                    "realId"
                )
                or track_id
            )

            album_id = (
                data.get(
                    "albumId"
                )
                or album_id
            )

        if not track_id:
            print(
                f"Яндекс: трек {index}: "
                "ID не найден."
            )

            continue

        if not album_id:
            print(
                f"Яндекс: трек {index}: "
                "albumId не найден."
            )

            continue

        track_url = (
            "https://music.yandex.ru/"
            f"album/{album_id}/"
            f"track/{track_id}"
        )

        tracks.append(
            track_url
        )

    if not tracks:
        print(
            "Яндекс: в плейлисте "
            "не найдено ни одного трека."
        )

        return None

    print()
    print(
        "Яндекс: плейлист:",
        playlist_title
    )

    print(
        "Яндекс: треков найдено:",
        len(tracks)
    )

    for index, track_url in enumerate(
        tracks,
        1
    ):
        print(
            f"  {index}. {track_url}"
        )

    return {
        "title": playlist_title,
        "tracks": tracks
    }

'''


    # Удаляем старые версии функций,
    # если они вдруг уже появились.

    function_names = {
        "extract_yandex_playlist_state",
        "get_playlist_tracks"
    }

    result = []
    i = 0

    while i < len(lines):

        line = lines[i]

        match = re.match(
            r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            line
        )

        if (
            match
            and match.group(1)
            in function_names
        ):
            end = find_function_end(
                lines,
                i
            )

            i = end
            continue

        result.append(
            line
        )

        i += 1

    text = "".join(result)

    # Вставляем функции перед
    # PLAYLIST PROCESSING.

    marker = (
        "# PLAYLIST PROCESSING"
    )

    position = text.find(
        marker
    )

    if position < 0:
        raise RuntimeError(
            "Не найден раздел "
            "'# PLAYLIST PROCESSING'."
        )

    text = (
        text[:position]
        + new_functions
        + "\n"
        + text[position:]
    )

    return text


def patch_is_playlist_url(text):
    """
    Расширяет is_playlist_url():

    YouTube playlist
    +
    Yandex playlist
    """

    old = '''def is_playlist_url(url):
    return (
        "list=" in url
        and (
            "youtube.com" in url
            or "music.youtube.com" in url
        )
    )
'''

    new = '''def is_playlist_url(url):
    if not url:
        return False

    url_lower = url.lower()

    # YouTube / YouTube Music
    if (
        "list=" in url_lower
        and (
            "youtube.com" in url_lower
            or "music.youtube.com" in url_lower
        )
    ):
        return True

    # Yandex Music playlist
    if (
        "music.yandex.ru/playlists/" in url_lower
        or "music.yandex.com/playlists/" in url_lower
        or "music.yandex.kz/playlists/" in url_lower
        or "music.yandex.by/playlists/" in url_lower
        or "music.yandex.uz/playlists/" in url_lower
    ):
        return True

    return False
'''

    if old not in text:
        raise RuntimeError(
            "Не найден текущий "
            "is_playlist_url()."
        )

    return text.replace(
        old,
        new,
        1
    )


def main():
    print("=" * 70)
    print(
        "CENSURU.NET — ПАТЧ ЯНДЕКС-ПЛЕЙЛИСТОВ"
    )
    print("=" * 70)

    if not os.path.isfile(FILE):
        print()
        print(
            "ОШИБКА: downloader.py не найден:"
        )
        print(FILE)
        return

    print()
    print(
        "Исходный файл:"
    )
    print(FILE)

    try:
        with open(
            FILE,
            "r",
            encoding="utf-8"
        ) as f:
            original = f.read()

    except Exception as e:
        print(
            "Не удалось прочитать файл:",
            e
        )
        return

    try:
        backup = backup_file(
            FILE
        )

        print()
        print(
            "Резервная копия создана:"
        )
        print(backup)

        patched = (
            patch_playlist_functions(
                original
            )
        )

        patched = (
            patch_is_playlist_url(
                patched
            )
        )

        with open(
            FILE,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:
            f.write(
                patched
            )

    except Exception as e:
        print()
        print(
            "ОШИБКА ПАТЧА:"
        )
        print(e)

        try:
            with open(
                FILE,
                "w",
                encoding="utf-8",
                newline=""
            ) as f:
                f.write(
                    original
                )

            print()
            print(
                "Исходный файл восстановлен."
            )

        except Exception:
            pass

        return

    # ----------------------------------------------------------
    # Проверка синтаксиса
    # ----------------------------------------------------------

    print()
    print(
        "Проверка синтаксиса..."
    )

    try:
        compile(
            patched,
            FILE,
            "exec"
        )

    except SyntaxError as e:
        print(
            "ОШИБКА СИНТАКСИСА:"
        )
        print(e)

        try:
            with open(
                FILE,
                "w",
                encoding="utf-8",
                newline=""
            ) as f:
                f.write(
                    original
                )

            print()
            print(
                "Исходный файл восстановлен."
            )

        except Exception:
            pass

        return

    print(
        "OK: синтаксис корректный."
    )

    # ----------------------------------------------------------
    # Проверка наличия функций
    # ----------------------------------------------------------

    namespace = {}

    try:
        exec(
            compile(
                patched,
                FILE,
                "exec"
            ),
            namespace
        )

    except Exception as e:
        print()
        print(
            "ОШИБКА ЗАГРУЗКИ МОДУЛЯ:"
        )
        print(e)

        try:
            with open(
                FILE,
                "w",
                encoding="utf-8",
                newline=""
            ) as f:
                f.write(
                    original
                )

            print()
            print(
                "Исходный файл восстановлен."
            )

        except Exception:
            pass

        return

    required = (
        "extract_yandex_playlist_state",
        "get_playlist_tracks",
        "is_playlist_url"
    )

    print()

    for name in required:
        if callable(
            namespace.get(name)
        ):
            print(
                f"OK: {name}"
            )
        else:
            print(
                f"ОШИБКА: {name} "
                "не найдена."
            )

    print()
    print("=" * 70)
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
