import ast
import os
import re
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
    source = read_file(path)

    try:
        ast.parse(
            source,
            filename=path
        )
    except SyntaxError as e:
        print(
            f"ОШИБКА СИНТАКСИСА: "
            f"{e}"
        )
        return False

    return True


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


def build_youtube_playlist_function():
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
    print(
        "======================================================================"
    )
    print(
        "CENSURU.NET — ДОБАВЛЕНИЕ YOUTUBE MUSIC PLAYLIST PROCESSOR"
    )
    print(
        "======================================================================"
    )
    print()

    if not os.path.isfile(BOT_FILE):
        print(
            f"ОШИБКА: файл {BOT_FILE} не найден."
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
        "Проверка существующих функций..."
    )

    process_track = find_function(
        source,
        "process_track"
    )

    process_yandex = find_function(
        source,
        "process_yandex_playlist"
    )

    youtube_playlist = find_function(
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
            "  ОШИБКА: process_yandex_playlist() "
            "не найдена."
        )
        return 1

    print(
        "  OK: process_yandex_playlist() найдена."
    )

    if youtube_playlist is not None:
        print(
            "  ВНИМАНИЕ: process_youtube_playlist() "
            "уже существует."
        )
        print(
            "  Патч не будет добавлять дубликат."
        )
    else:
        print(
            "  OK: process_youtube_playlist() "
            "пока отсутствует — будет добавлена."
        )

    # ------------------------------------------------------------
    # Проверяем downloader.py только информационно.
    # ------------------------------------------------------------

    downloader_file = "downloader.py"

    if os.path.isfile(downloader_file):

        print()
        print(
            "Проверка downloader.py..."
        )

        downloader_source = read_file(
            downloader_file
        )

        if not check_syntax(
            downloader_file
        ):
            return 1

        downloader_function = find_function(
            downloader_source,
            "get_youtube_playlist_tracks"
        )

        if downloader_function is None:

            print(
                "  ОШИБКА: "
                "get_youtube_playlist_tracks() "
                "не найдена."
            )

            return 1

        print(
            "  OK: "
            "get_youtube_playlist_tracks()."
        )

    # ------------------------------------------------------------
    # Проверяем URL handler.
    # ------------------------------------------------------------

    print()
    print(
        "Проверка URL handler..."
    )

    if (
        "downloader.is_playlist_url(text)"
        not in source
    ):
        print(
            "  ОШИБКА: "
            "downloader.is_playlist_url(text) "
            "не найдена."
        )
        return 1

    print(
        "  OK: обнаружение плейлистов."
    )

    if (
        'target=process_yandex_playlist'
        not in source
    ):
        print(
            "  ОШИБКА: "
            "маршрутизация Яндекс-плейлиста "
            "не найдена."
        )
        return 1

    print(
        "  OK: маршрутизация Яндекс-плейлиста."
    )

    # ------------------------------------------------------------
    # Создаём backup ДО любых изменений.
    # ------------------------------------------------------------

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

    original_source = source

    # ------------------------------------------------------------
    # 1. Добавляем process_youtube_playlist().
    # ------------------------------------------------------------

    if youtube_playlist is None:

        print()
        print(
            "1/2: добавление process_youtube_playlist()..."
        )

        function_text = (
            build_youtube_playlist_function()
        )

        # Вставляем перед process_yandex_playlist().
        marker = (
            "def process_yandex_playlist("
        )

        position = source.find(
            marker
        )

        if position < 0:

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

        source = (
            source[:position]
            + function_text
            + "\n"
            + source[position:]
        )

        print(
            "  OK"
        )

    else:

        print()
        print(
            "1/2: process_youtube_playlist() "
            "уже существует — пропуск."
        )

    # ------------------------------------------------------------
    # 2. Меняем ТОЛЬКО YouTube ветку.
    # ------------------------------------------------------------

    print()
    print(
        "2/2: обновление маршрутизации "
        "YouTube Music-плейлиста..."
    )

    youtube_branch_pattern = re.compile(
        r'('
        r'else:\s*'
        r'\n\s*print\(\s*'
        r'"Источник плейлиста: "\s*'
        r'\n\s*"YouTube Music"\s*'
        r'\n\s*\)\s*'
        r'\n\s*'
        r'# Текущую обработку YouTube-плейлистов\s*'
        r'\n\s*# пока не меняем\.\s*'
        r'\n\s*'
        r'thread = threading\.Thread\(\s*'
        r'\n\s*target=process_track,'
        r'\n\s*args=\(\s*'
        r'\n\s*chat_id,'
        r'\n\s*text\s*'
        r'\n\s*\)\s*'
        r'\n\s*daemon=True\s*'
        r'\n\s*\)'
        r')',
        re.MULTILINE
    )

    replacement = '''else:
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
                    )'''

    new_source, replacements = (
        youtube_branch_pattern.subn(
            replacement,
            source,
            count=1
        )
    )

    if replacements != 1:

        print(
            "  ОШИБКА: не удалось безопасно "
            "найти текущую YouTube Music "
            "ветку."
        )

        print(
            "  Автоматический откат..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    source = new_source

    print(
        "  OK"
    )

    # ------------------------------------------------------------
    # Проверяем, что Яндекс ветка НЕ изменилась.
    # ------------------------------------------------------------

    original_yandex_text = (
        get_function_text(
            original_source,
            process_yandex
        )
    )

    new_yandex_node = find_function(
        source,
        "process_yandex_playlist"
    )

    if new_yandex_node is None:

        print()
        print(
            "ОШИБКА: "
            "process_yandex_playlist() "
            "исчезла после патча."
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

    if original_yandex_text != new_yandex_text:

        print()
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
        "Проверка сохранения process_yandex_playlist()..."
    )
    print(
        "  OK: функция не изменялась."
    )

    # ------------------------------------------------------------
    # Записываем новый bot.py.
    # ------------------------------------------------------------

    write_file(
        BOT_FILE,
        source
    )

    # ------------------------------------------------------------
    # Финальная проверка синтаксиса.
    # ------------------------------------------------------------

    print()
    print(
        "Финальная проверка bot.py..."
    )

    if not check_syntax(
        BOT_FILE
    ):

        print(
            "  ОШИБКА: новый bot.py "
            "не проходит синтаксическую проверку."
        )

        print(
            "Автоматический откат..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        if check_syntax(
            BOT_FILE
        ):
            print(
                "  OK: исходный bot.py восстановлен."
            )

        return 1

    print(
        "  OK: синтаксис."
    )

    final_source = read_file(
        BOT_FILE
    )

    print()
    print(
        "Проверка установленных функций..."
    )

    checks = (
        "process_track",
        "process_yandex_playlist",
        "process_youtube_playlist"
    )

    for name in checks:

        if find_function(
            final_source,
            name
        ) is None:

            print(
                f"  ОШИБКА: {name}() "
                f"не найдена."
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

    # ------------------------------------------------------------
    # Проверяем маршрутизацию.
    # ------------------------------------------------------------

    print()
    print(
        "Проверка маршрутизации..."
    )

    if (
        "target=process_youtube_playlist"
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
        "target=process_yandex_playlist"
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

    # Проверяем, что старый ошибочный target
    # не остался внутри YouTube ветки.
    youtube_target_count = len(
        re.findall(
            r'target=process_youtube_playlist',
            final_source
        )
    )

    if youtube_target_count < 1:

        print(
            "  ОШИБКА: "
            "target=process_youtube_playlist "
            "не найден."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        return 1

    print(
        "  OK: старый ошибочный "
        "YouTube playlist -> process_track "
        "устранён."
    )

    print()
    print(
        "======================================================================"
    )
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print(
        "======================================================================"
    )

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
        "  - YouTube Music playlist направляется "
        "в отдельный обработчик"
    )
    print(
        "  - обработка треков использует "
        "существующий process_track()"
    )

    print()
    print(
        "Не изменено:"
    )
    print(
        "  - process_track()"
    )
    print(
        "  - process_yandex_playlist()"
    )
    print(
        "  - send_message()"
    )
    print(
        "  - downloader.py"
    )
    print(
        "  - polling"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
      )
