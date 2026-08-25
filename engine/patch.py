from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys


BOT = Path("bot.py")


# ============================================================
# НОВАЯ ФУНКЦИЯ
# ============================================================

NEW_FUNCTION = r'''
def start_status_session(chat_id):
    """
    Начинает новую пользовательскую сессию обработки.

    Следующая отправка через send_message() создаст новое
    статусное сообщение вместо редактирования сообщения
    предыдущей ссылки.
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

                # process_track() уже самостоятельно
                # сообщает пользователю об ошибке через
                # существующее статусное сообщение.
                #
                # Здесь ничего дополнительно не отправляем,
                # чтобы не создавать отдельное сообщение.

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


def parse_tree(source):
    return ast.parse(
        source,
        filename=str(BOT)
    )


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
            "ОШИБКА синтаксиса:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        return False


def find_function_node(source, name):
    tree = parse_tree(source)

    for node in tree.body:

        if (
            isinstance(
                node,
                ast.FunctionDef
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

        return (
            find_function_node(
                source,
                name
            )
            is not None
        )

    except Exception:
        return False


def get_function_source(source, node):
    lines = source.splitlines(
        keepends=True
    )

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(
        lines[start:end]
    )


def add_start_status_to_function(
    source,
    function_name
):
    node = find_function_node(
        source,
        function_name
    )

    if node is None:
        raise RuntimeError(
            f"{function_name}() не найдена."
        )

    function_source = get_function_source(
        source,
        node
    )

    if "start_status_session(" in function_source:
        return source

    lines = source.splitlines(
        keepends=True
    )

    # Ищем первую строку тела после def.
    # У наших функций тело начинается с try:.
    def_line_index = node.lineno - 1

    try_line_index = None

    for i in range(
        def_line_index + 1,
        node.end_lineno
    ):

        stripped = lines[i].strip()

        if stripped == "try:":
            try_line_index = i
            break

    if try_line_index is None:

        raise RuntimeError(
            f"Не найдено начало тела "
            f"{function_name}()."
        )

    # Вставляем вызов непосредственно
    # после try: с тем же уровнем отступа,
    # который используется внутри try.
    body_indent = (
        len(lines[try_line_index + 1])
        - len(
            lines[
                try_line_index + 1
            ].lstrip()
        )
    )

    indentation = " " * body_indent

    insertion = (
        indentation
        + "start_status_session(\n"
        + indentation
        + "    chat_id\n"
        + indentation
        + ")\n"
    )

    lines.insert(
        try_line_index + 1,
        insertion
    )

    return "".join(lines)


# ============================================================
# START
# ============================================================

print("=" * 70)
print(
    "CENSURU.NET — YOUTUBE MUSIC PLAYLIST BOT"
)
print("=" * 70)
print()


# ------------------------------------------------------------
# 1. Исходная проверка
# ------------------------------------------------------------

print(
    "Проверка исходного bot.py..."
)

if not BOT.exists():

    print(
        "ОШИБКА: bot.py не найден."
    )

    sys.exit(1)

if not check_syntax(BOT):

    print(
        "ОШИБКА: исходный bot.py "
        "синтаксически некорректен."
    )

    sys.exit(1)

print(
    "  OK: исходный синтаксис."
)


source = BOT.read_text(
    encoding="utf-8"
)


# ------------------------------------------------------------
# 2. Проверяем необходимые функции
# ------------------------------------------------------------

print()
print(
    "Проверка функций..."
)

required_functions = (
    "process_track",
    "process_yandex_playlist",
)

for function_name in required_functions:

    if not function_exists(
        BOT,
        function_name
    ):

        print(
            f"  ОШИБКА: "
            f"{function_name}() не найдена."
        )

        sys.exit(1)

    print(
        f"  OK: "
        f"{function_name}() найдена."
    )


if function_exists(
    BOT,
    "process_youtube_playlist"
):

    print()
    print(
        "ОШИБКА: process_youtube_playlist() "
        "уже существует."
    )

    print(
        "Файл не изменён."
    )

    sys.exit(1)


# ------------------------------------------------------------
# 3. Проверяем downloader.py
# ------------------------------------------------------------

print()
print(
    "Проверка downloader.py..."
)

DOWNLOADER = BOT.with_name(
    "downloader.py"
)

if not DOWNLOADER.exists():

    print(
        "ОШИБКА: downloader.py не найден."
    )

    sys.exit(1)

if not function_exists(
    DOWNLOADER,
    "get_youtube_playlist_tracks"
):

    print(
        "ОШИБКА: "
        "get_youtube_playlist_tracks() "
        "не найдена в downloader.py."
    )

    print(
        "Сначала должен быть применён "
        "предыдущий патч."
    )

    sys.exit(1)

print(
    "  OK: "
    "get_youtube_playlist_tracks()."
)


# ------------------------------------------------------------
# 4. Backup
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
# 5. Добавляем start_status_session()
#    и process_youtube_playlist()
# ------------------------------------------------------------

print()
print(
    "1/4: добавление новых функций..."
)

try:

    process_track_node = find_function_node(
        source,
        "process_track"
    )

    process_yandex_node = find_function_node(
        source,
        "process_yandex_playlist"
    )

    if (
        process_track_node is None
        or process_yandex_node is None
    ):
        raise RuntimeError(
            "Не удалось определить расположение "
            "существующих функций."
        )

    # Вставляем новые функции непосредственно
    # перед process_yandex_playlist().
    lines = source.splitlines(
        keepends=True
    )

    insertion_index = (
        process_yandex_node.lineno - 1
    )

    lines.insert(
        insertion_index,
        NEW_FUNCTION
        + "\n"
    )

    source = "".join(lines)

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
# 6. Добавляем начало новой статусной сессии
# ------------------------------------------------------------

print()
print(
    "2/4: обновление начала "
    "process_track()..."
)

try:

    source = add_start_status_to_function(
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


print()
print(
    "3/4: обновление начала "
    "process_yandex_playlist()..."
)

try:

    source = add_start_status_to_function(
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
# 7. Меняем только маршрутизацию playlist
# ------------------------------------------------------------

print()
print(
    "4/4: подключение "
    "process_youtube_playlist()..."
)

old_block = '''                else:

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

new_block = '''                else:

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

if old_block not in source:

    print(
        "  ОШИБКА: ожидаемый блок "
        "маршрутизации YouTube-плейлиста "
        "не найден."
    )

    print(
        "Это означает, что структура "
        "bot.py отличается от ожидаемой."
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    sys.exit(1)

source = source.replace(
    old_block,
    new_block,
    1
)

print(
    "  OK"
)


# ------------------------------------------------------------
# 8. Запись
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
# 9. Синтаксис
# ------------------------------------------------------------

print()
print(
    "Проверка нового bot.py..."
)

if not check_syntax(BOT):

    print()
    print(
        "Синтаксис повреждён."
    )

    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        BOT
    )

    print(
        "  OK: исходный bot.py восстановлен."
    )

    sys.exit(1)

print(
    "  OK: синтаксис."
)


# ------------------------------------------------------------
# 10. Проверяем функции
# ------------------------------------------------------------

print()
print(
    "Проверка установленных функций..."
)

checks = (
    "start_status_session",
    "process_youtube_playlist",
    "process_track",
    "process_yandex_playlist",
)

for function_name in checks:

    if not function_exists(
        BOT,
        function_name
    ):

        print(
            f"  ОШИБКА: "
            f"{function_name}() не найдена."
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
        f"  OK: "
        f"{function_name}()."
    )


# ------------------------------------------------------------
# 11. Проверяем маршрутизацию
# ------------------------------------------------------------

final_source = BOT.read_text(
    encoding="utf-8"
)

if (
    "target=process_youtube_playlist"
    not in final_source
):

    print(
        "ОШИБКА: маршрутизация "
        "YouTube-плейлиста не установлена."
    )

    print(
        "Автоматический откат..."
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
        "ОШИБКА: маршрутизация "
        "Яндекс-плейлиста отсутствует."
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
# Финал
# ------------------------------------------------------------

print()
print(
    "Проверка записанного файла..."
)

if not check_syntax(BOT):

    print(
        "ОШИБКА финальной проверки."
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
    "  OK: bot.py записан "
    "и синтаксически корректен."
)


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
    "теперь обрабатывается отдельно"
)
print(
    "  - новая ссылка начинает "
    "новое статусное сообщение"
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
    "  - логика Яндекс-плейлиста"
)
print(
    "  - логика скачивания отдельного трека"
  )
