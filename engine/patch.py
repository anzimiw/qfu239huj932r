from pathlib import Path
from datetime import datetime
import ast
import shutil
import re
import sys


TARGET = Path("bot.py")


def fail(message):
    print()
    print("ОШИБКА:")
    print(message)
    sys.exit(1)


def check_syntax(path):
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


print("=" * 70)
print("CENSURU.NET — ПАТЧ ЯНДЕКС-ПЛЕЙЛИСТА ДЛЯ BOT.PY")
print("=" * 70)
print()

if not TARGET.exists():
    fail(
        f"Файл не найден: {TARGET.resolve()}"
    )


print("Целевой файл:")
print(TARGET.resolve())
print()

print("Исходный файл прочитан.")

source = TARGET.read_text(
    encoding="utf-8"
)

print(
    f"Размер: {len(source):,} байт"
)

print(
    f"Строк: {len(source.splitlines()):,}"
)

print()

print("Проверка исходного синтаксиса...")

if not check_syntax(TARGET):
    fail(
        "Исходный bot.py содержит синтаксическую ошибку."
    )

print("OK: синтаксис исходного bot.py.")

print()


# ============================================================
# 1. Проверяем необходимые функции
# ============================================================

required_tokens = [
    "def process_track(",
    "downloader.is_yandex_music_url(",
    "downloader.get_yandex_music_info(",
    "downloader.get_playlist_tracks(",
    "def send_audio(",
]

print("Проверка структуры bot.py...")

for token in required_tokens:
    if token not in source:
        fail(
            f"Не найден обязательный элемент:\n{token}"
        )

    print(
        f"  OK: {token}"
    )

print()


# ============================================================
# 2. Проверяем, не установлен ли патч уже
# ============================================================

marker_start = (
    "# ============================================================\n"
    "# CENSURU.NET — YANDEX PLAYLIST HANDLER\n"
    "# ============================================================\n"
)

marker_function = (
    "def process_yandex_playlist("
)

if (
    marker_start in source
    or marker_function in source
):
    fail(
        "Похоже, патч Яндекс-плейлиста уже установлен.\n"
        "Повторно применять его не будем."
    )


# ============================================================
# 3. Находим process_track
# ============================================================

tree = ast.parse(
    source,
    filename=str(TARGET)
)

process_track_node = None

for node in tree.body:
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "process_track"
    ):
        process_track_node = node
        break

if process_track_node is None:
    fail(
        "Функция process_track() не найдена."
    )

print(
    "Функция process_track(): найдена."
)

print(
    f"Строки функции: "
    f"{process_track_node.lineno}-"
    f"{process_track_node.end_lineno}"
)

print()


# ============================================================
# 4. Находим начало тела process_track
# ============================================================

lines = source.splitlines(
    keepends=True
)

function_line_index = (
    process_track_node.lineno - 1
)

body_start_index = (
    process_track_node.body[0].lineno - 1
)

body_start_text = lines[
    body_start_index
]

# Нам нужно вставить обработку плейлиста сразу
# после try: в process_track().
#
# Сейчас структура:
#
# def process_track(...):
#     try:
#         ...
#
# Вставляем:
#
#         if downloader.is_playlist_url(url):
#             return process_yandex_playlist(...)
#

try_node = None

for node in process_track_node.body:
    if isinstance(node, ast.Try):
        try_node = node
        break

if try_node is None:
    fail(
        "В process_track() не найден основной блок try."
    )

if not try_node.body:
    fail(
        "Основной блок try в process_track() пуст."
    )

first_try_line = (
    try_node.body[0].lineno - 1
)

indent_match = re.match(
    r"^(\s*)",
    lines[first_try_line]
)

if not indent_match:
    fail(
        "Не удалось определить отступ process_track()."
    )

inner_indent = indent_match.group(1)

if not inner_indent:
    fail(
        "Не удалось определить внутренний отступ process_track()."
    )


# ============================================================
# 5. Код новой функции
# ============================================================

playlist_function = r'''
# ============================================================
# CENSURU.NET — YANDEX PLAYLIST HANDLER
# ============================================================

def process_yandex_playlist(
    chat_id,
    url
):
    """
    Обработка Яндекс-плейлиста внутри Telegram-бота.

    downloader.py отвечает за получение списка треков.
    bot.py отвечает за последовательную обработку и
    отправку готовых MP3 в Telegram.
    """

    print()
    print("=" * 70)
    print("ОБРАБОТКА ЯНДЕКС-ПЛЕЙЛИСТА")
    print("=" * 70)
    print()
    print(f"Playlist URL: {url}")

    send_message(
        chat_id,
        "Получаю список треков Яндекс-плейлиста..."
    )

    print()
    print(
        "Получение списка треков через downloader.py..."
    )

    playlist = downloader.get_playlist_tracks(
        url
    )

    if not playlist:
        send_message(
            chat_id,
            "Не удалось получить список треков Яндекс-плейлиста."
        )

        print(
            "ОШИБКА: get_playlist_tracks() вернул пустой результат."
        )

        return

    playlist_title = (
        playlist.get("title")
        or "Яндекс Музыка"
    )

    tracks = (
        playlist.get("tracks")
        or []
    )

    if not tracks:
        send_message(
            chat_id,
            "В Яндекс-плейлисте не найдено треков."
        )

        print(
            "ОШИБКА: список треков пуст."
        )

        return

    print()
    print(
        f"Название плейлиста: {playlist_title}"
    )

    print(
        f"Количество треков: {len(tracks)}"
    )

    send_message(
        chat_id,
        (
            f"Плейлист найден.\n\n"
            f"Название: {playlist_title}\n"
            f"Треков: {len(tracks)}\n\n"
            f"Начинаю обработку."
        )
    )

    total = len(tracks)
    successful = 0
    failed = 0

    for index, track_url in enumerate(
        tracks,
        1
    ):
        print()
        print("=" * 70)
        print(
            f"ПЛЕЙЛИСТ: ТРЕК {index}/{total}"
        )
        print("=" * 70)
        print()
        print(
            f"URL трека: {track_url}"
        )

        send_message(
            chat_id,
            (
                f"Плейлист: {playlist_title}\n\n"
                f"Трек {index}/{total}\n"
                f"Начинаю обработку..."
            )
        )

        try:
            result = process_track(
                chat_id,
                track_url
            )

            if result:
                successful += 1
            else:
                failed += 1

        except Exception as playlist_track_error:
            failed += 1

            print()
            print(
                "ОШИБКА ОБРАБОТКИ ТРЕКА ПЛЕЙЛИСТА:"
            )
            print(
                f"{type(playlist_track_error).__name__}: "
                f"{playlist_track_error}"
            )

            send_message(
                chat_id,
                (
                    f"Ошибка при обработке трека "
                    f"{index}/{total}.\n\n"
                    f"{type(playlist_track_error).__name__}: "
                    f"{playlist_track_error}"
                )
            )

    print()
    print("=" * 70)
    print("ЯНДЕКС-ПЛЕЙЛИСТ ЗАВЕРШЁН")
    print("=" * 70)
    print()
    print(
        f"Плейлист: {playlist_title}"
    )
    print(
        f"Всего треков: {total}"
    )
    print(
        f"Успешно: {successful}"
    )
    print(
        f"Ошибок: {failed}"
    )

    send_message(
        chat_id,
        (
            f"Плейлист обработан.\n\n"
            f"{playlist_title}\n\n"
            f"Всего треков: {total}\n"
            f"Скачано: {successful}\n"
            f"Ошибок: {failed}"
        )
    )

    return {
        "title": playlist_title,
        "total": total,
        "successful": successful,
        "failed": failed
    }

'''


# ============================================================
# 6. Вставляем функцию перед process_track
# ============================================================

function_insert_text = (
    playlist_function.strip("\n")
    + "\n\n\n"
)

# Определяем строку начала process_track.
insert_position = sum(
    len(x)
    for x in lines[:function_line_index]
)

source_with_function = (
    source[:insert_position]
    + function_insert_text
    + source[insert_position:]
)


# ============================================================
# 7. Добавляем проверку плейлиста в process_track
# ============================================================

# После вставки функции номера строк изменились,
# но сам текст process_track сохранился.

needle = (
    "        print(\"Получение информации из downloader.py...\")\n"
)

if needle not in source_with_function:
    # Возможна другая форма кавычек/форматирования.
    needle = (
        '        print(\n'
        '            "Получение информации из downloader.py..."\n'
        '        )\n'
    )

if needle not in source_with_function:
    fail(
        "Не найдено место перед получением информации "
        "из downloader.py в process_track()."
    )


playlist_route = r'''
        # ------------------------------------------------
        # Яндекс-плейлист
        # ------------------------------------------------
        #
        # Плейлист нельзя передавать в
        # get_yandex_music_info(), потому что эта функция
        # предназначена только для отдельного трека.
        #
        # Передаём плейлист в специальный Telegram-handler.
        # ------------------------------------------------

        if downloader.is_playlist_url(url):
            print()
            print(
                "Источник: Яндекс Музыка"
            )
            print(
                "Тип: Яндекс-плейлист"
            )
            print(
                "Передача в обработчик плейлиста..."
            )

            return process_yandex_playlist(
                chat_id,
                url
            )

        # ------------------------------------------------
        # Обычный одиночный трек
        # ------------------------------------------------

'''

# Вставляем после print("Получение информации...")
route_position = (
    source_with_function.index(needle)
    + len(needle)
)

source_with_route = (
    source_with_function[:route_position]
    + playlist_route
    + source_with_function[route_position:]
)


# ============================================================
# 8. Проверяем, что маршрут действительно появился
# ============================================================

print(
    "Проверка нового маршрута..."
)

checks = [
    (
        "process_yandex_playlist()",
        "def process_yandex_playlist("
        in source_with_route
    ),
    (
        "is_playlist_url()",
        "if downloader.is_playlist_url(url):"
        in source_with_route
    ),
    (
        "get_playlist_tracks()",
        "downloader.get_playlist_tracks("
        in source_with_route
    ),
    (
        "playlist -> process_track()",
        "result = process_track("
        in source_with_route
    ),
    (
        "обычный get_yandex_music_info()",
        "downloader.get_yandex_music_info("
        in source_with_route
    ),
    (
        "обычный get_youtube_music_info()",
        "downloader.get_youtube_music_info("
        in source_with_route
    ),
]

for name, ok in checks:
    if ok:
        print(
            f"  OK: {name}"
        )
    else:
        print(
            f"  FAIL: {name}"
        )
        fail(
            f"Проверка не пройдена: {name}"
        )

print()


# ============================================================
# 9. Проверяем синтаксис НОВОГО текста до записи
# ============================================================

print(
    "Проверка синтаксиса нового bot.py..."
)

try:
    ast.parse(
        source_with_route,
        filename=str(TARGET)
    )
except SyntaxError as exc:
    print(
        f"  FAIL: строка {exc.lineno}: {exc.msg}"
    )
    fail(
        "Новый код не прошёл AST-проверку. "
        "Файл пока НЕ изменён."
    )

print(
    "OK: новый синтаксис."
)

print()


# ============================================================
# 10. Backup
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = TARGET.with_name(
    f"{TARGET.stem}.backup_yandex_playlist_{timestamp}"
    f"{TARGET.suffix}"
)

try:
    shutil.copy2(
        TARGET,
        backup
    )
except Exception as exc:
    fail(
        f"Не удалось создать backup:\n{exc}"
    )

print(
    f"Backup: {backup.name}"
)

print()


# ============================================================
# 11. Запись
# ============================================================

try:
    TARGET.write_text(
        source_with_route,
        encoding="utf-8",
        newline=""
    )
except Exception as exc:
    print()
    print(
        "ОШИБКА ЗАПИСИ."
    )
    print(
        f"{type(exc).__name__}: {exc}"
    )
    print()
    print(
        "Восстанавливаем backup..."
    )

    try:
        shutil.copy2(
            backup,
            TARGET
        )
        print(
            "Backup восстановлен."
        )
    except Exception as restore_exc:
        print(
            "КРИТИЧЕСКАЯ ОШИБКА:"
        )
        print(
            f"Не удалось восстановить backup: "
            f"{restore_exc}"
        )

    sys.exit(1)


print(
    "Патч применён."
)

print()


# ============================================================
# 12. Проверяем записанный файл
# ============================================================

print(
    "Проверка записанного bot.py..."
)

if not check_syntax(TARGET):
    print()
    print(
        "Синтаксис после записи НЕПРАВИЛЬНЫЙ."
    )
    print(
        "Восстанавливаем backup..."
    )

    try:
        shutil.copy2(
            backup,
            TARGET
        )
        print(
            "Backup восстановлен."
        )
    except Exception as exc:
        print(
            "КРИТИЧЕСКАЯ ОШИБКА ВОССТАНОВЛЕНИЯ:"
        )
        print(exc)

    sys.exit(1)

print(
    "OK: синтаксис."
)

print()


# ============================================================
# 13. Финальные структурные проверки
# ============================================================

final_source = TARGET.read_text(
    encoding="utf-8"
)

print(
    "Финальная проверка..."
)

final_checks = [
    (
        "Обработчик Яндекс-плейлиста",
        "def process_yandex_playlist("
        in final_source
    ),
    (
        "Проверка is_playlist_url",
        "if downloader.is_playlist_url(url):"
        in final_source
    ),
    (
        "Получение списка треков",
        "downloader.get_playlist_tracks("
        in final_source
    ),
    (
        "Обработка отдельных треков",
        "result = process_track("
        in final_source
    ),
    (
        "Обычный Яндекс-трек",
        "downloader.get_yandex_music_info("
        in final_source
    ),
    (
        "Обычный YouTube-трек",
        "downloader.get_youtube_music_info("
        in final_source
    ),
    (
        "Telegram send_audio",
        "send_audio("
        in final_source
    ),
]

for name, ok in final_checks:
    if ok:
        print(
            f"  OK: {name}"
        )
    else:
        print(
            f"  FAIL: {name}"
        )
        fail(
            f"Финальная проверка не пройдена: {name}"
        )

print()

print("=" * 70)
print("ПАТЧ УСПЕШНО ЗАВЕРШЁН")
print("=" * 70)
print()
print(
    f"Изменён: {TARGET.resolve()}"
)
print(
    f"Backup:  {backup.resolve()}"
)
print()
print(
    "Яндекс-плейлист теперь перехватывается "
    "до get_yandex_music_info()."
)
print(
    "Одиночные YouTube/Яндекс-треки "
    "оставлены в существующем маршруте."
)
print()
print(
    "Следующий шаг: запустить бота и проверить "
    "реальный URL Яндекс-плейлиста."
)
