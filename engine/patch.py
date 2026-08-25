from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys


BOT = Path("bot.py")
DOWNLOADER = Path("downloader.py")


# ============================================================
# НОВЫЕ ФУНКЦИИ
# ============================================================

NEW_FUNCTIONS = r'''
def start_status_session(chat_id):
    """
    Начинает новую статусную сессию.

    Следующая отправка через send_message() создаст
    новое статусное сообщение вместо редактирования
    сообщения предыдущей ссылки.
    """

    try:

        status_states = globals().get(
            "_STATUS_MESSAGES"
        )

        if status_states is not None:

            status_lock = globals().get(
                "_STATUS_LOCK"
            )

            if status_lock is not None:

                with status_lock:

                    status_states.pop(
                        chat_id,
                        None
                    )

            else:

                status_states.pop(
                    chat_id,
                    None
                )

    except Exception as e:

        print(
            "Не удалось начать новую "
            "статусную сессию:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )


def process_youtube_playlist(chat_id, url):

    try:

        start_status_session(
            chat_id
        )

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ YOUTUBE MUSIC ПЛЕЙЛИСТА")
        print("=" * 70)
        print()
        print(
            f"URL плейлиста: {url}"
        )

        send_message(
            chat_id,
            "Получаю список треков YouTube Music..."
        )

        print()
        print(
            "YouTube Music: "
            "получение списка треков..."
        )

        playlist = (
            downloader.get_youtube_playlist_tracks(
                url
            )
        )

        if not playlist:

            send_message(
                chat_id,
                "Не удалось получить список треков YouTube Music."
            )

            print(
                "ОШИБКА: "
                "get_youtube_playlist_tracks() "
                "вернул пустой результат."
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
            f"Название плейлиста: "
            f"{playlist_title}"
        )

        print(
            f"Найдено треков: "
            f"{len(tracks)}"
        )

        if not tracks:

            send_message(
                chat_id,
                "В YouTube Music-плейлисте не найдено треков."
            )

            return

        send_message(
            chat_id,
            (
                f"Плейлист найден.\n\n"
                f"{playlist_title}\n"
                f"Треков: {len(tracks)}\n\n"
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
                f"YOUTUBE PLAYLIST: "
                f"ТРЕК {index}/{len(tracks)}"
            )
            print("=" * 70)
            print()
            print(
                f"URL трека: {track_url}"
            )

            try:

                success = process_track(
                    chat_id,
                    track_url
                )

                if success:
                    successful += 1
                else:
                    failed += 1

            except Exception as track_error:

                failed += 1

                print()
                print(
                    "ОШИБКА ТРЕКА "
                    "YOUTUBE-ПЛЕЙЛИСТА:"
                )

                print(
                    f"{type(track_error).__name__}: "
                    f"{track_error}"
                )

        print()
        print("=" * 70)
        print("YOUTUBE MUSIC ПЛЕЙЛИСТ ЗАВЕРШЁН")
        print("=" * 70)
        print()

        print(
            f"Всего треков: {len(tracks)}"
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
                f"Всего треков: {len(tracks)}\n"
                f"Успешно: {successful}\n"
                f"Ошибок: {failed}"
            )
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
                "Произошла ошибка при обработке "
                "YouTube Music-плейлиста."
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

'''


# ============================================================
# УТИЛИТЫ
# ============================================================

def check_syntax(path):
    try:

        source = path.read_text(
            encoding="utf-8"
        )

        ast.parse(
            source,
            filename=str(path)
        )

        return True

    except Exception as e:

        print(
            f"ОШИБКА синтаксиса "
            f"{path.name}:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        return False


def get_tree(source):
    return ast.parse(
        source,
        filename=str(BOT)
    )


def get_function_node(source, name):
    tree = get_tree(source)

    for node in tree.body:

        if (
            isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and node.name == name
        ):
            return node

    return None


def function_exists(path, name):

    try:

        source = path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(path)
        )

        for node in tree.body:

            if (
                isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                )
                and node.name == name
            ):
                return True

        return False

    except Exception:

        return False


def replace_once(source, old, new, description):

    count = source.count(
        old
    )

    if count != 1:

        raise RuntimeError(
            f"{description}: "
            f"ожидалось 1 совпадение, "
            f"найдено {count}."
        )

    return source.replace(
        old,
        new,
        1
    )


def insert_before_function(
    source,
    function_name,
    text
):

    node = get_function_node(
        source,
        function_name
    )

    if node is None:

        raise RuntimeError(
            f"{function_name}() не найдена."
        )

    lines = source.splitlines(
        keepends=True
    )

    index = node.lineno - 1

    lines.insert(
        index,
        text + "\n"
    )

    return "".join(lines)


def add_status_session_to_function(
    source,
    function_name
):

    node = get_function_node(
        source,
        function_name
    )

    if node is None:

        raise RuntimeError(
            f"{function_name}() не найдена."
        )

    lines = source.splitlines(
        keepends=True
    )

    start = node.lineno - 1
    end = node.end_lineno

    function_text = "".join(
        lines[start:end]
    )

    if "start_status_session(" in function_text:

        raise RuntimeError(
            f"start_status_session() уже "
            f"есть внутри {function_name}()."
        )

    # Ищем точную конструкцию:
    #
    #     try:
    #
    #         ...
    #
    # Вставляем после пустой строки.
    #
    # Это безопаснее, чем определять отступ
    # по произвольной соседней строке.

    pattern = (
        "    try:\n"
        "\n"
    )

    replacement = (
        "    try:\n"
        "\n"
        "        start_status_session(\n"
        "            chat_id\n"
        "        )\n"
        "\n"
    )

    local_count = function_text.count(
        pattern
    )

    if local_count != 1:

        raise RuntimeError(
            f"{function_name}(): "
            f"ожидалась одна конструкция "
            f"'    try:\\n\\n', "
            f"найдено {local_count}."
        )

    new_function_text = function_text.replace(
        pattern,
        replacement,
        1
    )

    lines[start:end] = [
        new_function_text
    ]

    return "".join(lines)


# ============================================================
# НАЧАЛО
# ============================================================

print("=" * 70)
print(
    "CENSURU.NET — YOUTUBE MUSIC PLAYLIST BOT v2"
)
print("=" * 70)
print()


# ------------------------------------------------------------
# 1. Проверяем файлы
# ------------------------------------------------------------

print(
    "Проверка файлов..."
)

if not BOT.exists():

    print(
        "ОШИБКА: bot.py не найден."
    )

    sys.exit(1)

if not DOWNLOADER.exists():

    print(
        "ОШИБКА: downloader.py не найден."
    )

    sys.exit(1)

print(
    "  OK: bot.py."
)

print(
    "  OK: downloader.py."
)


# ------------------------------------------------------------
# 2. Проверяем исходный bot.py
# ------------------------------------------------------------

print()
print(
    "Проверка исходного bot.py..."
)

if not check_syntax(BOT):

    print(
        "ОШИБКА: исходный bot.py "
        "нельзя безопасно изменять."
    )

    sys.exit(1)

print(
    "  OK: исходный синтаксис."
)


# ------------------------------------------------------------
# 3. Проверяем необходимые функции
# ------------------------------------------------------------

print()
print(
    "Проверка функций..."
)

for name in (
    "process_track",
    "process_yandex_playlist",
):

    if not function_exists(
        BOT,
        name
    ):

        print(
            f"  ОШИБКА: {name}() не найдена."
        )

        sys.exit(1)

    print(
        f"  OK: {name}() найдена."
    )


if function_exists(
    BOT,
    "process_youtube_playlist"
):

    print()
    print(
        "ОШИБКА: "
        "process_youtube_playlist() "
        "уже существует."
    )

    sys.exit(1)


if function_exists(
    BOT,
    "start_status_session"
):

    print()
    print(
        "ОШИБКА: "
        "start_status_session() "
        "уже существует."
    )

    sys.exit(1)


# ------------------------------------------------------------
# 4. Проверяем downloader.py
# ------------------------------------------------------------

print()
print(
    "Проверка downloader.py..."
)

if not function_exists(
    DOWNLOADER,
    "get_youtube_playlist_tracks"
):

    print(
        "ОШИБКА: "
        "get_youtube_playlist_tracks() "
        "не найдена."
    )

    sys.exit(1)

print(
    "  OK: "
    "get_youtube_playlist_tracks()."
)


# ------------------------------------------------------------
# 5. ПОЛНАЯ ПРОВЕРКА ТОЧЕК ИЗМЕНЕНИЯ
#    ДО СОЗДАНИЯ BACKUP
# ------------------------------------------------------------

source = BOT.read_text(
    encoding="utf-8"
)

print()
print(
    "Проверка точек изменения..."
)

# Проверяем, что process_track начинается
# ожидаемой конструкцией.
track_node = get_function_node(
    source,
    "process_track"
)

yandex_node = get_function_node(
    source,
    "process_yandex_playlist"
)

if track_node is None:
    print("  ОШИБКА: process_track().")
    sys.exit(1)

if yandex_node is None:
    print("  ОШИБКА: process_yandex_playlist().")
    sys.exit(1)


def get_func_text(source, node):
    lines = source.splitlines(
        keepends=True
    )

    return "".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


track_text = get_func_text(
    source,
    track_node
)

yandex_text = get_func_text(
    source,
    yandex_node
)


if track_text.count(
    "    try:\n\n"
) != 1:

    print(
        "  ОШИБКА: "
        "неожидаемая структура process_track()."
    )

    sys.exit(1)


if yandex_text.count(
    "    try:\n\n"
) != 1:

    print(
        "  ОШИБКА: "
        "неожидаемая структура "
        "process_yandex_playlist()."
    )

    sys.exit(1)


# Точный старый блок маршрутизации.
OLD_ROUTING = '''                else:

                    print(
                        "Источник плейлиста: "
                        "YouTube Music"
                    )

                    # Текущую обработку YouTube-плейлистов
                    # пока не меняем.
                    thread = threading.Thread(
                        target=process_track,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )
'''

if source.count(
    OLD_ROUTING
) != 1:

    print(
        "  ОШИБКА: "
        "точный блок маршрутизации "
        "YouTube Music не найден."
    )

    print(
        "Файл не будет изменён."
    )

    sys.exit(1)


print(
    "  OK: все точки изменения найдены."
)


# ------------------------------------------------------------
# 6. Backup
# ------------------------------------------------------------

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = BOT.with_name(
    BOT.name
    + ".backup_"
    + timestamp
)

print()
print(
    "Создание резервной копии..."
)

try:

    shutil.copy2(
        BOT,
        backup
    )

except Exception as e:

    print(
        "ОШИБКА создания backup:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    sys.exit(1)

print(
    f"  OK: {backup.name}"
)


# ------------------------------------------------------------
# 7. Добавляем новые функции
# ------------------------------------------------------------

print()
print(
    "1/5: добавление новых функций..."
)

try:

    source = insert_before_function(
        source,
        "process_yandex_playlist",
        NEW_FUNCTIONS.rstrip()
    )

except Exception as e:

    print(
        "  ОШИБКА:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK"
)


# ------------------------------------------------------------
# 8. process_track
# ------------------------------------------------------------

print()
print(
    "2/5: обновление "
    "process_track()..."
)

try:

    source = add_status_session_to_function(
        source,
        "process_track"
    )

except Exception as e:

    print(
        "  ОШИБКА:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK"
)


# ------------------------------------------------------------
# 9. process_yandex_playlist
# ------------------------------------------------------------

print()
print(
    "3/5: обновление "
    "process_yandex_playlist()..."
)

try:

    source = add_status_session_to_function(
        source,
        "process_yandex_playlist"
    )

except Exception as e:

    print(
        "  ОШИБКА:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK"
)


# ------------------------------------------------------------
# 10. Маршрутизация
# ------------------------------------------------------------

print()
print(
    "4/5: подключение "
    "process_youtube_playlist()..."
)

NEW_ROUTING = '''                else:

                    print(
                        "Источник плейлиста: "
                        "YouTube Music"
                    )

                    thread = threading.Thread(
                        target=process_youtube_playlist,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )
'''

try:

    source = replace_once(
        source,
        OLD_ROUTING,
        NEW_ROUTING,
        "Маршрутизация YouTube Music"
    )

except Exception as e:

    print(
        "  ОШИБКА:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK"
)


# ------------------------------------------------------------
# 11. AST проверка ПЕРЕД записью
# ------------------------------------------------------------

print()
print(
    "5/5: предварительная проверка "
    "новой структуры..."
)

try:

    ast.parse(
        source,
        filename=str(BOT)
    )

except Exception as e:

    print(
        "  ОШИБКА: новая структура "
        "синтаксически некорректна."
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Файл ещё не записан."
    )

    print(
        "Автоматический откат backup..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK: AST корректен."
)


# ------------------------------------------------------------
# 12. Запись
# ------------------------------------------------------------

try:

    BOT.write_text(
        source,
        encoding="utf-8",
        newline="\n"
    )

except Exception as e:

    print()
    print(
        "ОШИБКА записи bot.py:"
    )

    print(
        f"{type(e).__name__}: {e}"
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)


# ------------------------------------------------------------
# 13. Финальная проверка
# ------------------------------------------------------------

print()
print(
    "Проверка записанного bot.py..."
)

if not check_syntax(BOT):

    print(
        "ОШИБКА финального синтаксиса."
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

print(
    "  OK: синтаксис."
)


# ------------------------------------------------------------
# 14. Проверка функций
# ------------------------------------------------------------

print()
print(
    "Проверка установленных функций..."
)

for name in (
    "start_status_session",
    "process_youtube_playlist",
    "process_track",
    "process_yandex_playlist",
):

    if not function_exists(
        BOT,
        name
    ):

        print(
            f"  ОШИБКА: {name}() не найдена."
        )

        print(
            "Автоматический откат..."
        )

        shutil.copy2(
            backup,
            BOT
        )

        sys.exit(1)

    print(
        f"  OK: {name}()."
    )


# ------------------------------------------------------------
# 15. Проверяем маршрутизацию
# ------------------------------------------------------------

final_source = BOT.read_text(
    encoding="utf-8"
)

if (
    "target=process_youtube_playlist"
    not in final_source
):

    print(
        "ОШИБКА: "
        "YouTube Music playlist "
        "не подключён."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)


if (
    "target=process_yandex_playlist"
    not in final_source
):

    print(
        "ОШИБКА: "
        "Яндекс playlist "
        "маршрутизация отсутствует."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)


# ------------------------------------------------------------
# ФИНАЛ
# ------------------------------------------------------------

print()
print("=" * 70)
print(
    "ПАТЧ УСПЕШНО ПРИМЕНЁН"
)
print("=" * 70)
print()
print(
    f"Backup: {backup.name}"
)
print()
print(
    "Добавлено:"
)
print(
    "  - start_status_session()"
)
print(
    "  - process_youtube_playlist()"
)
print()
print(
    "Изменено:"
)
print(
    "  - YouTube Music playlist "
    "получил отдельный обработчик"
)
print(
    "  - каждая новая ссылка "
    "начинает новую статусную сессию"
)
print()
print(
    "Не изменялось:"
)
print(
    "  - send_message()"
)
print(
    "  - edit_message()"
)
print(
    "  - polling"
)
print(
    "  - downloader.py"
)
print(
    "  - get_playlist_tracks()"
)
print(
    "  - логика скачивания трека"
)
