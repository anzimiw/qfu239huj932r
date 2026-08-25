import ast
import os
import re
import shutil
from datetime import datetime


BOT_FILE = "bot.py"
DOWNLOADER_FILE = "downloader.py"


# ============================================================
# HELPERS
# ============================================================

def fail(message):
    print()
    print("ОШИБКА:", message)
    print("Автоматический откат не требуется, если резервная копия")
    print("ещё не создавалась.")
    raise SystemExit(1)


def syntax_check(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig"
    ) as f:
        source = f.read()

    ast.parse(
        source,
        filename=path
    )

    return source


def find_function(source, name):
    tree = ast.parse(
        source,
        filename=BOT_FILE
    )

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node

    return None


def function_source(source, node):
    lines = source.splitlines(
        keepends=True
    )

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(
        lines[start:end]
    )


def find_top_level_function_range(source, name):
    tree = ast.parse(
        source,
        filename=BOT_FILE
    )

    lines = source.splitlines(
        keepends=True
    )

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            start = node.lineno - 1
            end = node.end_lineno

            return (
                start,
                end,
                "".join(lines[start:end])
            )

    return None


def find_url_handler(source):
    """
    Ищем реальный polling URL handler по характерной структуре:

        while True:
            ...
            text = message...
            ...
            if downloader.is_playlist_url(text):
    """

    tree = ast.parse(
        source,
        filename=BOT_FILE
    )

    candidates = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.While):
            continue

        body_source = ast.get_source_segment(
            source,
            node
        )

        if not body_source:
            continue

        score = 0

        if "get_updates" in body_source:
            score += 5

        if "message.get" in body_source:
            score += 3

        if "downloader.is_playlist_url" in body_source:
            score += 5

        if "process_yandex_playlist" in body_source:
            score += 5

        if "process_track" in body_source:
            score += 3

        if score >= 10:
            candidates.append(
                (
                    score,
                    node,
                    body_source
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidates[0]


def find_playlist_if(node):
    """
    Находит внутри URL handler именно:

        if downloader.is_playlist_url(text):
    """

    for child in ast.walk(node):

        if not isinstance(child, ast.If):
            continue

        test = child.test

        if not isinstance(test, ast.Call):
            continue

        func = test.func

        if not isinstance(func, ast.Attribute):
            continue

        if func.attr != "is_playlist_url":
            continue

        value = func.value

        if not isinstance(value, ast.Attribute):
            continue

        if value.attr != "is_playlist_url":
            continue

        # Здесь структура явно downloader.is_playlist_url(...)
        if isinstance(value.value, ast.Name):
            if value.value.id == "downloader":
                return child

    return None


def find_target_call(node, function_name):
    """
    Ищет Thread(target=function_name, ...)
    """

    for child in ast.walk(node):

        if not isinstance(child, ast.Call):
            continue

        func = child.func

        if not isinstance(func, ast.Name):
            continue

        if func.id != "Thread":
            continue

        for keyword in child.keywords:

            if keyword.arg != "target":
                continue

            value = keyword.value

            if (
                isinstance(value, ast.Name)
                and value.id == function_name
            ):
                return child

    return None


def source_segment(source, node):
    return ast.get_source_segment(
        source,
        node
    ) or ""


# ============================================================
# PROCESS_YOUTUBE_PLAYLIST
# ============================================================

YOUTUBE_FUNCTION = r'''def process_youtube_playlist(chat_id, url):

    try:

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ YOUTUBE MUSIC ПЛЕЙЛИСТА")
        print("=" * 70)
        print()
        print(f"URL плейлиста: {url}")

        # ----------------------------------------------------
        # Новый URL = новое статусное сообщение.
        # Старый статус больше не редактируем.
        # ----------------------------------------------------

        globals().get(
            "_STATUS_MESSAGES",
            {}
        ).pop(
            chat_id,
            None
        )

        send_message(
            chat_id,
            "Получаю список треков YouTube Music..."
        )

        print()
        print(
            "YouTube Music playlist: "
            "получение списка через yt-dlp..."
        )

        playlist = (
            downloader.get_youtube_playlist_tracks(
                url
            )
        )

        if not playlist:

            send_message(
                chat_id,
                "Не удалось получить список треков YouTube Music-плейлиста."
            )

            print(
                "ОШИБКА: get_youtube_playlist_tracks() "
                "вернул пустой результат."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return

        playlist_title = (
            playlist.get("title")
            or "YouTube Music"
        )

        tracks = (
            playlist.get("tracks")
            or []
        )

        print()
        print(
            f"Название плейлиста: {playlist_title}"
        )

        print(
            f"Найдено треков: {len(tracks)}"
        )

        if not tracks:

            send_message(
                chat_id,
                "В YouTube Music-плейлисте не найдено треков."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return

        total_tracks = len(tracks)

        send_message(
            chat_id,
            (
                f"Плейлист найден.\n\n"
                f"{playlist_title}\n"
                f"Треков: {total_tracks}\n\n"
                f"Начинаю обработку..."
            )
        )

        successful = 0
        failed = 0

        for index, track_url in enumerate(
            tracks,
            1
        ):

            print()
            print("=" * 70)
            print(
                f"YOUTUBE PLAYLIST: ТРЕК "
                f"{index}/{total_tracks}"
            )
            print("=" * 70)
            print()
            print(
                f"URL трека: {track_url}"
            )

            try:

                success = process_track(
                    chat_id,
                    track_url,
                    playlist_progress=(
                        index,
                        total_tracks
                    )
                )

                if success:
                    successful += 1
                else:
                    failed += 1

                    send_message(
                        chat_id,
                        (
                            f"Трек {index}/{total_tracks} "
                            f"не обработан.\n\n"
                            f"Продолжаю плейлист..."
                        )
                    )

            except Exception as track_error:

                failed += 1

                print()
                print(
                    "ОШИБКА ТРЕКА YOUTUBE PLAYLIST:"
                )

                print(
                    f"{type(track_error).__name__}: "
                    f"{track_error}"
                )

                try:

                    send_message(
                        chat_id,
                        (
                            f"Трек {index}/{total_tracks} "
                            f"не обработан.\n\n"
                            f"Продолжаю плейлист..."
                        )
                    )

                except Exception as telegram_error:

                    print(
                        "Не удалось обновить статус:"
                    )

                    print(
                        f"{type(telegram_error).__name__}: "
                        f"{telegram_error}"
                    )

        print()
        print("=" * 70)
        print("YOUTUBE MUSIC ПЛЕЙЛИСТ ЗАВЕРШЁН")
        print("=" * 70)
        print()

        print(
            f"Всего треков: {total_tracks}"
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
                f"Обработка плейлиста завершена.\n\n"
                f"{playlist_title}\n\n"
                f"Всего треков: {total_tracks}\n"
                f"Успешно: {successful}\n"
                f"Ошибок: {failed}"
            )
        )

        globals().get(
            "_STATUS_MESSAGES",
            {}
        ).pop(
            chat_id,
            None
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("ОШИБКА ОБРАБОТКИ YOUTUBE MUSIC ПЛЕЙЛИСТА")
        print("=" * 70)
        print()

        print(
            f"{type(e).__name__}: {e}"
        )

        try:

            send_message(
                chat_id,
                (
                    "Произошла ошибка при обработке "
                    "YouTube Music-плейлиста."
                )
            )

        except Exception as telegram_error:

            print(
                "Не удалось отправить сообщение "
                "об ошибке:"
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
'''


# ============================================================
# ROUTING REPLACEMENT
# ============================================================

def replace_youtube_branch(
    source,
    handler_node,
    playlist_if
):
    """
    Меняем только else-внутри:

        if downloader.is_yandex_music_url(text):
            ...
        else:
            ...

    который находится внутри
        if downloader.is_playlist_url(text):
    """

    lines = source.splitlines(
        keepends=True
    )

    # Находим именно прямой If downloader.is_yandex_music_url(...)
    yandex_if = None

    for child in playlist_if.body:

        if not isinstance(child, ast.If):
            continue

        segment = source_segment(
            source,
            child
        )

        if (
            "downloader.is_yandex_music_url"
            in segment
        ):
            yandex_if = child
            break

    if yandex_if is None:
        raise RuntimeError(
            "Внутри playlist handler не найден "
            "if downloader.is_yandex_music_url(text)."
        )

    if yandex_if.orelse == []:
        raise RuntimeError(
            "У Яндекс-ветки отсутствует else."
        )

    # Должен быть именно else, а не elif.
    if len(yandex_if.orelse) == 1 and isinstance(
        yandex_if.orelse[0],
        ast.If
    ):
        raise RuntimeError(
            "Структура Яндекс-ветки неожиданная: "
            "найден elif вместо else."
        )

    else_nodes = yandex_if.orelse

    if len(else_nodes) == 0:
        raise RuntimeError(
            "Не найден YouTube else."
        )

    # В обычном случае это список statement'ов else.
    else_start = else_nodes[0].lineno - 1
    else_end = (
        else_nodes[-1].end_lineno
    )

    # Нужно определить отступ else по исходному коду.
    yandex_line = lines[
        yandex_if.lineno - 1
    ]

    yandex_indent = (
        len(yandex_line)
        - len(yandex_line.lstrip())
    )

    # else имеет тот же уровень, что и if.
    else_indent = " " * yandex_indent

    new_else = (
        f"{else_indent}else:\n"
        f"{else_indent}    print()\n"
        f"{else_indent}    print(\n"
        f"{else_indent}        \"Источник плейлиста: \"\n"
        f"{else_indent}        \"YouTube Music\"\n"
        f"{else_indent}    )\n"
        f"{else_indent}\n"
        f"{else_indent}    # Новый URL получает отдельное\n"
        f"{else_indent}    # статусное сообщение.\n"
        f"{else_indent}    globals().get(\n"
        f"{else_indent}        \"_STATUS_MESSAGES\",\n"
        f"{else_indent}        {{}}\n"
        f"{else_indent}    ).pop(\n"
        f"{else_indent}        chat_id,\n"
        f"{else_indent}        None\n"
        f"{else_indent}    )\n"
        f"{else_indent}\n"
        f"{else_indent}    thread = threading.Thread(\n"
        f"{else_indent}        target=process_youtube_playlist,\n"
        f"{else_indent}        args=(\n"
        f"{else_indent}            chat_id,\n"
        f"{else_indent}            text\n"
        f"{else_indent}        ),\n"
        f"{else_indent}        daemon=True\n"
        f"{else_indent}    )"
    )

    # Проверяем, что текущий else действительно содержит
    # старую заглушку process_track(text).
    old_else_source = "".join(
        lines[
            else_start:else_end
        ]
    )

    if "process_track" not in old_else_source:
        raise RuntimeError(
            "YouTube else найден, но внутри нет "
            "ожидаемого process_track(). "
            "Отказываюсь менять структуру."
        )

    if "target=process_youtube_playlist" in old_else_source:
        raise RuntimeError(
            "YouTube branch уже содержит "
            "process_youtube_playlist()."
        )

    # AST не даёт координату самого else keyword,
    # поэтому ищем диапазон начиная с первого statement else
    # и сохраняем его содержимое.
    #
    # Здесь безопасно заменить statements else целиком:
    # они находятся между первой строкой тела else
    # и концом последнего statement.
    #
    # Чтобы сохранить сам else, заменяем только body.
    body_start = else_nodes[0].lineno - 1
    body_end = else_nodes[-1].end_lineno

    # Отступ тела else на один уровень больше.
    body_indent = " " * (yandex_indent + 4)

    new_body = (
        f"{body_indent}print()\n"
        f"{body_indent}print(\n"
        f"{body_indent}    \"Источник плейлиста: \"\n"
        f"{body_indent}    \"YouTube Music\"\n"
        f"{body_indent})\n"
        f"{body_indent}\n"
        f"{body_indent}# Новый URL получает отдельное статусное сообщение.\n"
        f"{body_indent}globals().get(\n"
        f"{body_indent}    \"_STATUS_MESSAGES\",\n"
        f"{body_indent}    {{}}\n"
        f"{body_indent}).pop(\n"
        f"{body_indent}    chat_id,\n"
        f"{body_indent}    None\n"
        f"{body_indent})\n"
        f"{body_indent}\n"
        f"{body_indent}thread = threading.Thread(\n"
        f"{body_indent}    target=process_youtube_playlist,\n"
        f"{body_indent}    args=(\n"
        f"{body_indent}        chat_id,\n"
        f"{body_indent}        text\n"
        f"{body_indent}    ),\n"
        f"{body_indent}    daemon=True\n"
        f"{body_indent})\n"
    )

    new_lines = (
        lines[:body_start]
        + [new_body]
        + lines[body_end:]
    )

    return "".join(new_lines)


# ============================================================
# EXTRA CHECKS
# ============================================================

def verify_routing(source):
    tree = ast.parse(
        source,
        filename=BOT_FILE
    )

    functions = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }

    if "process_track" not in functions:
        fail(
            "После патча отсутствует process_track()."
        )

    if "process_yandex_playlist" not in functions:
        fail(
            "После патча отсутствует process_yandex_playlist()."
        )

    if "process_youtube_playlist" not in functions:
        fail(
            "После патча отсутствует process_youtube_playlist()."
        )

    handler = find_url_handler(
        source
    )

    if not handler:
        fail(
            "После патча не найден URL handler."
        )

    _, handler_node, _ = handler

    playlist_if = find_playlist_if(
        handler_node
    )

    if not playlist_if:
        fail(
            "После патча не найден "
            "downloader.is_playlist_url(text)."
        )

    # Яндекс target
    yandex_target = find_target_call(
        playlist_if,
        "process_yandex_playlist"
    )

    if not yandex_target:
        fail(
            "Яндекс-ветка больше не вызывает "
            "process_yandex_playlist()."
        )

    # YouTube target
    youtube_target = find_target_call(
        playlist_if,
        "process_youtube_playlist"
    )

    if not youtube_target:
        fail(
            "YouTube playlist branch не вызывает "
            "process_youtube_playlist()."
        )

    # Проверяем, что process_track не оказался
    # целью playlist branch.
    playlist_source = source_segment(
        source,
        playlist_if
    )

    if (
        "target=process_track"
        in playlist_source
    ):
        fail(
            "Внутри playlist branch остался "
            "target=process_track."
        )

    print(
        "  OK: process_track()."
    )

    print(
        "  OK: process_yandex_playlist()."
    )

    print(
        "  OK: process_youtube_playlist()."
    )

    print(
        "  OK: Яндекс-плейлист -> "
        "process_yandex_playlist()."
    )

    print(
        "  OK: YouTube Music-плейлист -> "
        "process_youtube_playlist()."
    )

    print(
        "  OK: внутри playlist branch "
        "нет target=process_track."
    )


# ============================================================
# MAIN
# ============================================================

print("=" * 70)
print("CENSURU.NET — БЕЗОПАСНЫЙ ПАТЧ YOUTUBE MUSIC PLAYLIST")
print("=" * 70)
print()

if not os.path.isfile(BOT_FILE):
    fail(
        f"Не найден {BOT_FILE}."
    )

if not os.path.isfile(DOWNLOADER_FILE):
    fail(
        f"Не найден {DOWNLOADER_FILE}."
    )


# ------------------------------------------------------------
# Проверка исходных файлов
# ------------------------------------------------------------

print("Проверка файлов...")

try:
    bot_source = syntax_check(
        BOT_FILE
    )

    print(
        "  OK: bot.py."
    )

except SyntaxError as e:
    fail(
        f"bot.py имеет синтаксическую ошибку: {e}"
    )


try:
    downloader_source = syntax_check(
        DOWNLOADER_FILE
    )

    print(
        "  OK: downloader.py."
    )

except SyntaxError as e:
    fail(
        f"downloader.py имеет синтаксическую ошибку: {e}"
    )


print()
print("Проверка существующих функций...")

for function_name in (
    "process_track",
    "process_yandex_playlist"
):

    if find_function(
        bot_source,
        function_name
    ):
        print(
            f"  OK: {function_name}() найдена."
        )

    else:
        fail(
            f"Не найдена {function_name}()."
        )


if find_function(
    bot_source,
    "process_youtube_playlist"
):
    fail(
        "process_youtube_playlist() уже существует. "
        "Отказываюсь создавать дубликат."
    )

else:
    print(
        "  OK: process_youtube_playlist() отсутствует."
    )


print()
print("Проверка downloader.py...")

try:

    downloader_tree = ast.parse(
        downloader_source,
        filename=DOWNLOADER_FILE
    )

    downloader_functions = {
        node.name
        for node in ast.walk(
            downloader_tree
        )
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }

    if "get_youtube_playlist_tracks" not in downloader_functions:
        fail(
            "В downloader.py отсутствует "
            "get_youtube_playlist_tracks()."
        )

    print(
        "  OK: get_youtube_playlist_tracks()."
    )

except Exception as e:
    fail(
        f"Не удалось проверить downloader.py: {e}"
    )


print()
print("Поиск URL handler...")

handler = find_url_handler(
    bot_source
)

if not handler:
    fail(
        "URL handler не найден по AST-структуре."
    )

handler_score, handler_node, handler_source = handler

print(
    f"  OK: URL handler найден (score={handler_score})."
)

playlist_if = find_playlist_if(
    handler_node
)

if not playlist_if:
    fail(
        "В URL handler не найден "
        "downloader.is_playlist_url(text)."
    )

print(
    "  OK: обнаружение плейлистов."
)


yandex_target = find_target_call(
    playlist_if,
    "process_yandex_playlist"
)

if not yandex_target:
    fail(
        "Не найден target=process_yandex_playlist "
        "в playlist branch."
    )

print(
    "  OK: маршрутизация Яндекс-плейлиста."
)


playlist_segment = source_segment(
    bot_source,
    playlist_if
)

if "target=process_track" not in playlist_segment:
    fail(
        "В текущей YouTube playlist branch "
        "не найден ожидаемый target=process_track. "
        "Это защищает от изменения уже другой структуры."
    )

print(
    "  OK: найдена текущая временная "
    "YouTube-ветка target=process_track."
)


# ------------------------------------------------------------
# Backup
# ------------------------------------------------------------

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_file = (
    f"{BOT_FILE}.backup_{timestamp}"
)

print()
print("Создание резервной копии...")

shutil.copy2(
    BOT_FILE,
    backup_file
)

print(
    f"  OK: {backup_file}"
)


# ------------------------------------------------------------
# 1. Добавляем process_youtube_playlist()
# ------------------------------------------------------------

print()
print("1/2: добавление process_youtube_playlist()...")

tree = ast.parse(
    bot_source,
    filename=BOT_FILE
)

top_level_nodes = tree.body

insert_before_line = None

for node in top_level_nodes:

    if (
        isinstance(
            node,
            (ast.Assign, ast.AnnAssign)
        )
        and node.lineno > handler_node.lineno
    ):
        insert_before_line = node.lineno - 1
        break

    if (
        isinstance(
            node,
            (ast.While, ast.For, ast.AsyncFor)
        )
        and node.lineno == handler_node.lineno
    ):
        insert_before_line = node.lineno - 1
        break

    if (
        isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and node.lineno > handler_node.lineno
    ):
        insert_before_line = node.lineno - 1
        break


if insert_before_line is None:
    # Обычно polling handler находится в конце файла.
    # В этом случае добавляем функцию непосредственно
    # перед handler.
    insert_before_line = handler_node.lineno - 1


lines = bot_source.splitlines(
    keepends=True
)

lines.insert(
    insert_before_line,
    YOUTUBE_FUNCTION + "\n\n"
)

modified_source = "".join(
    lines
)

try:
    ast.parse(
        modified_source,
        filename=BOT_FILE
    )

except SyntaxError as e:

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    print(
        "  ОШИБКА синтаксиса после добавления функции:"
    )

    print(
        e
    )

    print(
        "Автоматический откат..."
    )

    raise SystemExit(1)

print(
    "  OK"
)


# ------------------------------------------------------------
# 2. Перепроверяем handler после вставки функции
# ------------------------------------------------------------

print()
print("2/2: обновление маршрутизации YouTube Music-плейлиста...")

new_handler = find_url_handler(
    modified_source
)

if not new_handler:
    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    fail(
        "После добавления функции URL handler "
        "не найден."
    )

_, new_handler_node, _ = new_handler

new_playlist_if = find_playlist_if(
    new_handler_node
)

if not new_playlist_if:

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    fail(
        "После добавления функции не найден "
        "playlist branch."
    )


try:

    modified_source = replace_youtube_branch(
        modified_source,
        new_handler_node,
        new_playlist_if
    )

except Exception as e:

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    print()
    print(
        "ОШИБКА:"
    )

    print(
        str(e)
    )

    print(
        "Автоматический откат..."
    )

    raise SystemExit(1)


print(
    "  OK"
)


# ------------------------------------------------------------
# Финальная проверка
# ------------------------------------------------------------

print()
print("Финальная проверка bot.py...")

try:

    ast.parse(
        modified_source,
        filename=BOT_FILE
    )

    print(
        "  OK: синтаксис."
    )

except SyntaxError as e:

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    print(
        "  ОШИБКА: новый bot.py не проходит синтаксис."
    )

    print(
        e
    )

    print(
        "Автоматический откат..."
    )

    raise SystemExit(1)


print()
print("Проверка установленной маршрутизации...")

try:

    verify_routing(
        modified_source
    )

except Exception as e:

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    print()
    print(
        "ОШИБКА проверки:"
    )

    print(
        str(e)
    )

    print(
        "Автоматический откат..."
    )

    raise SystemExit(1)


# ------------------------------------------------------------
# Запись
# ------------------------------------------------------------

with open(
    BOT_FILE,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    f.write(
        modified_source
    )


# ------------------------------------------------------------
# Проверка записанного файла
# ------------------------------------------------------------

print()
print("Проверка записанного файла...")

try:

    written_source = syntax_check(
        BOT_FILE
    )

    verify_routing(
        written_source
    )

except Exception as e:

    print(
        "ОШИБКА проверки записанного файла:"
    )

    print(
        e
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup_file,
        BOT_FILE
    )

    raise SystemExit(1)


print()
print("=" * 70)
print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
print("=" * 70)

print()
print(
    f"Backup: {backup_file}"
)

print()
print("Изменено:")
print(
    "  - добавлена process_youtube_playlist()"
)
print(
    "  - YouTube Music playlist -> process_youtube_playlist()"
)
print(
    "  - Яндекс playlist -> process_yandex_playlist()"
)
print(
    "  - одиночные ссылки -> process_track()"
)
print(
    "  - новый URL сбрасывает старое статусное сообщение"
)
print(
    "  - downloader.py не изменялся"
)

print()
print("Polling не изменялся.")
print("Готово.")
