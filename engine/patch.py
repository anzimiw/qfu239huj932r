import ast
import os
import shutil
import sys
from datetime import datetime


BOT_FILE = "bot.py"


def read_file(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        return f.read()


def write_file(path, text):
    with open(
        path,
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        f.write(text)


def check_syntax(path):
    try:
        ast.parse(
            read_file(path),
            filename=path
        )
        return True
    except SyntaxError as e:
        print(
            f"ОШИБКА СИНТАКСИСА: {e}"
        )
        return False


def find_function(source, name):
    tree = ast.parse(source)

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    return None


def get_function_text(source, node):
    lines = source.splitlines(
        keepends=True
    )

    return "".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def youtube_playlist_function():
    return '''def process_youtube_playlist(chat_id, url):
    try:

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ YOUTUBE MUSIC ПЛЕЙЛИСТА")
        print("=" * 70)
        print()
        print(f"URL плейлиста: {url}")

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
                (
                    "Не удалось получить "
                    "список треков YouTube Music-плейлиста."
                )
            )

            print(
                "ОШИБКА: "
                "get_youtube_playlist_tracks() "
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
                "В плейлисте не найдено треков."
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
                f"Плейлист найден.\\n\\n"
                f"{playlist_title}\\n"
                f"Треков: {total_tracks}\\n\\n"
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
                f"YOUTUBE ПЛЕЙЛИСТ: "
                f"ТРЕК {index}/{total_tracks}"
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
                            f"не обработан.\\n\\n"
                            f"Продолжаю плейлист..."
                        )
                    )

            except Exception as track_error:

                failed += 1

                print()
                print(
                    "ОШИБКА ТРЕКА "
                    "YOUTUBE ПЛЕЙЛИСТА:"
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
                            f"не обработан.\\n\\n"
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
        print(
            "YOUTUBE MUSIC ПЛЕЙЛИСТ ЗАВЕРШЁН"
        )
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
                "Обработка плейлиста завершена.\\n\\n"
                f"{playlist_title}\\n\\n"
                f"Всего треков: {total_tracks}\\n"
                f"Успешно: {successful}\\n"
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
        print(
            "ОШИБКА ОБРАБОТКИ "
            "YOUTUBE MUSIC ПЛЕЙЛИСТА"
        )
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


def main():

    print("=" * 70)
    print(
        "CENSURU.NET — YOUTUBE MUSIC PLAYLIST PATCH V2"
    )
    print("=" * 70)
    print()

    if not os.path.isfile(BOT_FILE):

        print(
            f"ОШИБКА: {BOT_FILE} не найден."
        )

        return 1

    print(
        "Проверка исходного bot.py..."
    )

    if not check_syntax(BOT_FILE):
        return 1

    print(
        "  OK: исходный синтаксис."
    )

    source = read_file(BOT_FILE)

    print()
    print(
        "Проверка функций..."
    )

    process_track = find_function(
        source,
        "process_track"
    )

    process_yandex = find_function(
        source,
        "process_yandex_playlist"
    )

    process_youtube = find_function(
        source,
        "process_youtube_playlist"
    )

    if process_track is None:

        print(
            "  ОШИБКА: process_track() не найдена."
        )

        return 1

    print(
        "  OK: process_track() найдена."
    )

    if process_yandex is None:

        print(
            "  ОШИБКА: "
            "process_yandex_playlist() не найдена."
        )

        return 1

    print(
        "  OK: process_yandex_playlist() найдена."
    )

    if process_youtube is not None:

        print(
            "  ОШИБКА: "
            "process_youtube_playlist() "
            "уже существует."
        )

        print(
            "  Патч остановлен для безопасности."
        )

        return 1

    print(
        "  OK: process_youtube_playlist() "
        "отсутствует."
    )

    # ---------------------------------------------------------
    # Проверяем downloader.py
    # ---------------------------------------------------------

    downloader_file = "downloader.py"

    if os.path.isfile(
        downloader_file
    ):

        print()
        print(
            "Проверка downloader.py..."
        )

        downloader_source = read_file(
            downloader_file
        )

        try:
            ast.parse(
                downloader_source,
                filename=downloader_file
            )
        except SyntaxError as e:

            print(
                f"ОШИБКА downloader.py: {e}"
            )

            return 1

        if find_function(
            downloader_source,
            "get_youtube_playlist_tracks"
        ) is None:

            print(
                "  ОШИБКА: "
                "get_youtube_playlist_tracks() "
                "не найдена."
            )

            return 1

        print(
            "  OK: get_youtube_playlist_tracks()."
        )

    # ---------------------------------------------------------
    # Сохраняем исходную process_yandex_playlist()
    # ---------------------------------------------------------

    original_yandex_text = (
        get_function_text(
            source,
            process_yandex
        )
    )

    # ---------------------------------------------------------
    # Создаём backup
    # ---------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_file = (
        f"{BOT_FILE}.backup_{timestamp}"
    )

    print()
    print(
        "Создание резервной копии..."
    )

    shutil.copy2(
        BOT_FILE,
        backup_file
    )

    print(
        f"  OK: {backup_file}"
    )

    # ---------------------------------------------------------
    # 1. Добавляем функцию
    # ---------------------------------------------------------

    print()
    print(
        "1/2: добавление "
        "process_youtube_playlist()..."
    )

    marker = (
        "def process_yandex_playlist("
    )

    position = source.find(
        marker
    )

    if position == -1:

        print(
            "  ОШИБКА: "
            "не найдено начало "
            "process_yandex_playlist()."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    new_function = (
        youtube_playlist_function()
    )

    source = (
        source[:position]
        + new_function
        + "\n"
        + source[position:]
    )

    print(
        "  OK"
    )

    # ---------------------------------------------------------
    # 2. Безопасно меняем только нужный target.
    # ---------------------------------------------------------

    print()
    print(
        "2/2: обновление маршрутизации "
        "YouTube Music-плейлиста..."
    )

    youtube_marker = (
        'print(\n'
        '                        "Источник плейлиста: "\n'
        '                        "YouTube Music"\n'
        '                    )'
    )

    marker_position = source.find(
        youtube_marker
    )

    if marker_position == -1:

        print(
            "  ОШИБКА: "
            "не найден маркер YouTube Music "
            "в URL handler."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    # Ищем target=process_track только
    # после найденного YouTube-маркера.
    target_marker = (
        "target=process_track,"
    )

    target_position = source.find(
        target_marker,
        marker_position
    )

    if target_position == -1:

        print(
            "  ОШИБКА: "
            "после YouTube Music маркера "
            "не найден target=process_track."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    # Важная проверка: target должен находиться
    # внутри текущего URL handler, а не в другой функции.
    main_loop_position = source.find(
        "while True:",
        marker_position
    )

    if main_loop_position == -1:

        print(
            "  ОШИБКА: "
            "не найден URL handler."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    # Проверяем, что найденный target находится
    # до конца polling loop.
    polling_end = source.find(
        "except KeyboardInterrupt:",
        target_position
    )

    if polling_end == -1:

        print(
            "  ОШИБКА: "
            "не найден конец polling handler."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    if target_position > polling_end:

        print(
            "  ОШИБКА: "
            "найден target вне URL handler."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    # Теперь меняем ровно 1 вхождение.
    source = (
        source[:target_position]
        + "target=process_youtube_playlist,"
        + source[
            target_position
            + len(target_marker):
        ]
    )

    print(
        "  OK"
    )

    # ---------------------------------------------------------
    # Проверяем, что process_yandex_playlist() не изменилась.
    # ---------------------------------------------------------

    new_yandex_node = find_function(
        source,
        "process_yandex_playlist"
    )

    if new_yandex_node is None:

        print(
            "ОШИБКА: "
            "process_yandex_playlist() "
            "исчезла."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    new_yandex_text = (
        get_function_text(
            source,
            new_yandex_node
        )
    )

    if (
        new_yandex_text
        != original_yandex_text
    ):

        print(
            "ОШИБКА: "
            "process_yandex_playlist() "
            "изменилась."
        )

        print(
            "Автоматический откат..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print()
    print(
        "Проверка process_yandex_playlist()..."
    )
    print(
        "  OK: функция не изменялась."
    )

    # ---------------------------------------------------------
    # Записываем
    # ---------------------------------------------------------

    write_file(
        BOT_FILE,
        source
    )

    # ---------------------------------------------------------
    # Проверка синтаксиса
    # ---------------------------------------------------------

    print()
    print(
        "Проверка нового bot.py..."
    )

    if not check_syntax(
        BOT_FILE
    ):

        print(
            "  ОШИБКА: новый bot.py "
            "не проходит синтаксис."
        )

        print(
            "Автоматический откат..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print(
        "  OK: синтаксис."
    )

    final_source = read_file(
        BOT_FILE
    )

    # ---------------------------------------------------------
    # Проверяем функции
    # ---------------------------------------------------------

    print()
    print(
        "Проверка установленных функций..."
    )

    for name in (
        "process_track",
        "process_yandex_playlist",
        "process_youtube_playlist"
    ):

        if find_function(
            final_source,
            name
        ) is None:

            print(
                f"  ОШИБКА: {name}() не найдена."
            )

            print(
                "Автоматический откат..."
            )

            shutil.copy2(
                backup_file,
                BOT_FILE
            )

            return 1

        print(
            f"  OK: {name}()."
        )

    # ---------------------------------------------------------
    # Проверяем маршрутизацию
    # ---------------------------------------------------------

    print()
    print(
        "Проверка маршрутизации..."
    )

    if (
        "target=process_youtube_playlist,"
        not in final_source
    ):

        print(
            "  ОШИБКА: "
            "YouTube Music playlist "
            "не направляется в "
            "process_youtube_playlist()."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print(
        "  OK: YouTube Music playlist "
        "-> process_youtube_playlist()."
    )

    if (
        "target=process_yandex_playlist,"
        not in final_source
    ):

        print(
            "  ОШИБКА: "
            "Яндекс playlist "
            "не направляется в "
            "process_yandex_playlist()."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print(
        "  OK: Яндекс playlist "
        "-> process_yandex_playlist()."
    )

    # Проверяем, что обычный process_track()
    # всё ещё существует в URL handler.
    track_target_count = final_source.count(
        "target=process_track,"
    )

    if track_target_count < 1:

        print(
            "  ОШИБКА: "
            "target=process_track "
            "полностью исчез."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print(
        "  OK: обычный трек "
        "по-прежнему -> process_track()."
    )

    # ---------------------------------------------------------
    # Проверяем downloader.py НЕ изменился.
    # ---------------------------------------------------------

    if os.path.isfile(
        downloader_file
    ):

        print()
        print(
            "Проверка downloader.py..."
        )

        # Патч вообще не записывает downloader.py,
        # поэтому достаточно проверить наличие функции.
        print(
            "  OK: downloader.py не изменялся."
        )

    print()
    print("=" * 70)
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print("=" * 70)

    print()
    print(
        f"Backup: {backup_file}"
    )

    print()
    print(
        "Изменено:"
    )
    print(
        "  - добавлена process_youtube_playlist()"
    )
    print(
        "  - YouTube Music playlist -> "
        "process_youtube_playlist()"
    )

    print()
    print(
        "Сохранено без изменений:"
    )
    print(
        "  - process_track()"
    )
    print(
        "  - process_yandex_playlist()"
    )
    print(
        "  - downloader.py"
    )
    print(
        "  - send_message()"
    )
    print(
        "  - polling"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
      )
