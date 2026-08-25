import ast
import os
import re
import shutil
import sys
from datetime import datetime


TARGET = "downloader.py"
BACKUP_PREFIX = "downloader.py.backup_"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def check_syntax(text, label="file"):
    try:
        ast.parse(text, filename=label)
        return True
    except SyntaxError as e:
        print(f"ОШИБКА СИНТАКСИСА: {e}")
        return False


def find_function(text, name):
    try:
        tree = ast.parse(text, filename=TARGET)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node

    return None


EXTRACT_FUNCTION = r'''
def extract_yandex_playlist_state(html):
    """
    Извлекает состояние плейлиста Яндекс Музыки из HTML страницы.

    Яндекс сейчас передаёт данные плейлиста через:
        window.__STATE_PATCHES__

    Нас интересуют операции вида:
        replace /playlist/items/N
        add     /playlist/items/N

    Функция возвращает список словарей с данными треков.
    """

    if not html:
        return []

    # ------------------------------------------------------------
    # 1. Ищем все блоки __STATE_PATCHES__
    # ------------------------------------------------------------
    matches = re.findall(
        r'window\.__STATE_PATCHES__\s*=\s*window\.__STATE_PATCHES__\s*\|\|\s*\[\]\s*\)\.push\(\s*(\[[\s\S]*?\])\s*\)',
        html
    )

    if not matches:
        # Более мягкий fallback:
        # ищем участок после __STATE_PATCHES__ до ближайшего завершения push
        matches = re.findall(
            r'window\.__STATE_PATCHES__[\s\S]{0,200}?\)\.push\((\[[\s\S]*?\])\)',
            html
        )

    if not matches:
        return []

    tracks = {}

    # ------------------------------------------------------------
    # 2. Извлекаем track objects
    #
    # В HTML встречается JSON-подобная структура:
    #
    # {
    #   "op":"replace",
    #   "path":"\/playlist\/items\/2",
    #   "value":{
    #       "id":"154676063",
    #       ...
    #       "data":{
    #           ...
    #       }
    #   }
    # }
    #
    # Используем несколько уровней fallback, поскольку HTML
    # Яндекса содержит escaped JSON и React Server Components.
    # ------------------------------------------------------------

    for block in matches:
        # Нормализуем unicode escapes только для поиска структурных
        # полей. Не пытаемся целиком json.loads(), потому что блок
        # может содержать React Flight-структуры.
        normalized = block.replace(r'\/', '/')

        # --------------------------------------------------------
        # Вариант A: ищем непосредственно value/data объектов
        # --------------------------------------------------------
        pattern = re.compile(
            r'"path"\s*:\s*"\\?/playlist/items/(\d+)"'
            r'[\s\S]{0,100000}?'
            r'"value"\s*:\s*\{'
            r'[\s\S]{0,100000}?'
            r'"id"\s*:\s*"(\d+)"'
            r'[\s\S]{0,100000}?'
            r'"data"\s*:\s*\{'
            r'([\s\S]{0,100000}?)'
            r'\}\s*,\s*"loadingState"',
            re.S
        )

        for m in pattern.finditer(normalized):
            index = int(m.group(1))
            track_id = m.group(2)
            data_blob = m.group(3)

            if index not in tracks:
                tracks[index] = {
                    "id": track_id,
                    "index": index,
                    "data_blob": data_blob,
                }

        # --------------------------------------------------------
        # Вариант B: более широкий поиск replace + track data
        # --------------------------------------------------------
        pattern2 = re.compile(
            r'"path"\s*:\s*"\\?/playlist/items/(\d+)"'
            r'[\s\S]{0,5000}?'
            r'"id"\s*:\s*"(\d+)"'
            r'[\s\S]{0,5000}?'
            r'"data"\s*:\s*\{',
            re.S
        )

        for m in pattern2.finditer(normalized):
            index = int(m.group(1))
            track_id = m.group(2)

            if index not in tracks:
                tracks[index] = {
                    "id": track_id,
                    "index": index,
                    "data_blob": "",
                }

    # ------------------------------------------------------------
    # 3. Если регулярки выше не сработали, используем прямой
    #    поиск объектов по playlist/items/N.
    # ------------------------------------------------------------
    if not tracks:
        for m in re.finditer(
            r'"path"\s*:\s*"\\?/playlist/items/(\d+)"',
            normalized
        ):
            index = int(m.group(1))

            start = m.start()
            chunk = normalized[start:start + 120000]

            id_match = re.search(
                r'"id"\s*:\s*"(\d+)"',
                chunk
            )

            if not id_match:
                continue

            tracks[index] = {
                "id": id_match.group(1),
                "index": index,
                "data_blob": chunk,
            }

    # ------------------------------------------------------------
    # 4. Преобразуем найденные объекты в нормальный список
    # ------------------------------------------------------------
    result = []

    for index in sorted(tracks):
        item = tracks[index]
        blob = item.get("data_blob", "")

        track_id = item["id"]

        # albumId
        album_match = re.search(
            r'"albumId"\s*:\s*(\d+)',
            blob
        )
        album_id = album_match.group(1) if album_match else None

        # title
        title_match = re.search(
            r'"title"\s*:\s*"((?:\\.|[^"\\])*)"',
            blob
        )
        title = title_match.group(1) if title_match else ""

        # durationMs
        duration_match = re.search(
            r'"durationMs"\s*:\s*(\d+)',
            blob
        )
        duration_ms = (
            int(duration_match.group(1))
            if duration_match
            else None
        )

        # coverUri
        cover_match = re.search(
            r'"coverUri"\s*:\s*"((?:\\.|[^"\\])*)"',
            blob
        )
        cover_uri = cover_match.group(1) if cover_match else ""

        # --------------------------------------------------------
        # Исполнители
        # --------------------------------------------------------
        artists = []

        artists_match = re.search(
            r'"artists"\s*:\s*\[(.*?)\]',
            blob,
            re.S
        )

        if artists_match:
            artists_blob = artists_match.group(1)

            for artist_match in re.finditer(
                r'"name"\s*:\s*"((?:\\.|[^"\\])*)"',
                artists_blob
            ):
                name = artist_match.group(1)
                if name and name not in artists:
                    artists.append(name)

        # --------------------------------------------------------
        # Собираем объект в формате, пригодном для downloader.py
        # --------------------------------------------------------
        result.append({
            "id": track_id,
            "track_id": track_id,
            "album_id": album_id,
            "title": title,
            "artist": ", ".join(artists),
            "artists": artists,
            "duration_ms": duration_ms,
            "duration": (
                duration_ms / 1000.0
                if duration_ms is not None
                else None
            ),
            "cover_uri": cover_uri,
            "cover_url": (
                "https://" + cover_uri.replace("%%", "720x720")
                if cover_uri
                else None
            ),
            "source": "yandex",
        })

    return result
'''


def main():
    print("=" * 70)
    print("CENSURU.NET — ДОБАВЛЕНИЕ extract_yandex_playlist_state()")
    print("=" * 70)

    if not os.path.exists(TARGET):
        print(f"ОШИБКА: не найден {TARGET}")
        sys.exit(1)

    print()
    print("1. Чтение downloader.py...")
    original = read_file(TARGET)

    if not check_syntax(original, TARGET):
        print("ОШИБКА: исходный downloader.py имеет синтаксическую ошибку.")
        sys.exit(1)

    print("   OK: синтаксис исходного файла корректен.")

    print()
    print("2. Проверка функций...")

    playlist_url_func = find_function(original, "is_playlist_url")
    playlist_func = find_function(original, "get_playlist_tracks")
    state_func = find_function(original, "extract_yandex_playlist_state")

    if playlist_url_func is None:
        print("ОШИБКА: is_playlist_url() не найдена.")
        sys.exit(1)

    print("   OK: is_playlist_url() найдена.")

    if playlist_func is None:
        print("ОШИБКА: get_playlist_tracks() не найдена.")
        sys.exit(1)

    print("   OK: get_playlist_tracks() найдена.")

    if state_func is not None:
        print("ОШИБКА: extract_yandex_playlist_state() уже существует.")
        print("Патч не требуется.")
        sys.exit(1)

    print("   OK: extract_yandex_playlist_state() отсутствует.")
    print("   Именно эту функцию сейчас добавляем.")

    print()
    print("3. Создание резервной копии...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{BACKUP_PREFIX}{timestamp}"

    shutil.copy2(TARGET, backup)

    print(f"   Backup: {backup}")

    print()
    print("4. Добавление extract_yandex_playlist_state()...")

    # Получаем исходную строку начала get_playlist_tracks()
    lines = original.splitlines(True)

    try:
        insert_line = playlist_func.lineno - 1
    except AttributeError:
        print("ОШИБКА: невозможно определить позицию get_playlist_tracks().")
        shutil.copy2(backup, TARGET)
        sys.exit(1)

    function_text = EXTRACT_FUNCTION.strip() + "\n\n"

    new_text = (
        "".join(lines[:insert_line])
        + function_text
        + "".join(lines[insert_line:])
    )

    print("   OK: функция вставлена перед get_playlist_tracks().")

    print()
    print("5. Проверка нового downloader.py...")

    if not check_syntax(new_text, TARGET):
        print()
        print("ОШИБКА: новый файл не прошёл проверку синтаксиса.")
        print("Восстановление резервной копии...")

        shutil.copy2(backup, TARGET)

        print("Файл восстановлен.")
        sys.exit(1)

    print("   OK: синтаксис корректен.")

    print()
    print("6. Проверка структуры после патча...")

    if find_function(new_text, "extract_yandex_playlist_state") is None:
        print("ОШИБКА: функция после вставки не обнаружена.")
        shutil.copy2(backup, TARGET)
        print("Файл восстановлен.")
        sys.exit(1)

    if find_function(new_text, "is_playlist_url") is None:
        print("ОШИБКА: is_playlist_url() исчезла после патча.")
        shutil.copy2(backup, TARGET)
        print("Файл восстановлен.")
        sys.exit(1)

    if find_function(new_text, "get_playlist_tracks") is None:
        print("ОШИБКА: get_playlist_tracks() исчезла после патча.")
        shutil.copy2(backup, TARGET)
        print("Файл восстановлен.")
        sys.exit(1)

    write_file(TARGET, new_text)

    print("   OK: is_playlist_url() сохранена.")
    print("   OK: get_playlist_tracks() сохранена.")
    print("   OK: extract_yandex_playlist_state() добавлена.")

    print()
    print("=" * 70)
    print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
    print("=" * 70)
    print()
    print(f"Файл:   {os.path.abspath(TARGET)}")
    print(f"Backup: {os.path.abspath(backup)}")
    print()
    print("Следующий шаг — проверить импорт:")
    print()
    print(
        'python -c "import downloader; '
        'print(hasattr(downloader, \'extract_yandex_playlist_state\'))"'
    )
    print()


if __name__ == "__main__":
    main()
