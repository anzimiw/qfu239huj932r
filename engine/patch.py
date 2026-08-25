import ast
import os
import shutil
from datetime import datetime


BOT_FILE = "bot.py"


PROCESS_TRACK_MARKER = "def process_track(chat_id, url, playlist_progress=None):"


YOUTUBE_PLAYLIST_FUNCTION = r'''
# ============================================================
# ОБРАБОТКА ПЛЕЙЛИСТА YOUTUBE MUSIC
# ============================================================

def process_youtube_playlist(chat_id, url):

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
            "YouTube Music: получение списка треков "
            "через downloader.py..."
        )

        playlist = downloader.get_youtube_playlist_tracks(
            url
        )

        if not playlist:

            send_message(
                chat_id,
                "Не удалось получить список треков YouTube Music."
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
                "В YouTube Music плейлисте не найдено треков."
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
                f"YOUTUBE MUSIC: ТРЕК "
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
                    "ОШИБКА ТРЕКА YOUTUBE MUSIC ПЛЕЙЛИСТА:"
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
            f"Название: {playlist_title}"
        )

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
                "Произошла ошибка при обработке YouTube Music плейлиста."
            )

        except Exception as telegram_error:

            print(
                "Не удалось отправить сообщение об ошибке:"
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


def syntax_check(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        source = f.read()

    ast.parse(
        source,
        filename=path
    )


def get_function_names(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        source = f.read()

    tree = ast.parse(
        source,
        filename=path
    )

    return {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }


def find_process_track_start(source):
    marker = (
        "def process_track(chat_id, url, playlist_progress=None):"
    )

    positions = []

    start = 0

    while True:

        pos = source.find(
            marker,
            start
        )

        if pos == -1:
            break

        positions.append(pos)
        start = pos + len(marker)

    if len(positions) != 1:
        raise RuntimeError(
            "Ожидалась ровно одна функция "
            "process_track(), найдено: "
            f"{len(positions)}"
        )

    return positions[0]


def find_polling_youtube_branch(source):
    """
    Ищем именно фактический блок из текущего bot.py:

        else:

            print(
                "Источник плейлиста: "
                "YouTube Music"
            )

            # Текущую обработку YouTube-плейлистов
            # пока не меняем.
            thread = threading.Thread(
                target=process_track,
                ...
            )

    Возвращаем границы только target=process_track.
    """

    source_marker = (
        'print(\n'
        '                        "Источник плейлиста: "\n'
        '                        "YouTube Music"\n'
        '                    )'
    )

    source_pos = source.find(
        source_marker
    )

    if source_pos == -1:
        raise RuntimeError(
            "Не найден блок "
            '"Источник плейлиста: YouTube Music".'
        )

    branch_end = source.find(
        "            else:",
        source_pos
    )

    if branch_end == -1:
        raise RuntimeError(
            "Не найден конец YouTube Music ветки."
        )

    branch = source[
        source_pos:
        branch_end
    ]

    target_marker = (
        "target=process_track,"
    )

    target_pos = branch.find(
        target_marker
    )

    if target_pos == -1:
        raise RuntimeError(
            "В YouTube Music ветке "
            "не найден target=process_track."
        )

    absolute_target = (
        source_pos +
        target_pos
    )

    return (
        absolute_target,
        absolute_target + len(target_marker)
    )


def main():

    print("=" * 70)
    print("CENSURU.NET — YOUTUBE PLAYLIST PATCH")
    print("=" * 70)
    print()

    if not os.path.isfile(
        BOT_FILE
    ):
        print(
            f"ОШИБКА: файл {BOT_FILE} не найден."
        )
        return 1

    print(
        "Проверка исходного bot.py..."
    )

    try:

        syntax_check(
            BOT_FILE
        )

        print(
            "  OK: исходный синтаксис."
        )

    except Exception as e:

        print(
            "  ОШИБКА синтаксиса:"
        )

        print(
            e
        )

        return 1

    functions = get_function_names(
        BOT_FILE
    )

    print()
    print(
        "Проверка функций..."
    )

    if "process_track" not in functions:

        print(
            "  ОШИБКА: process_track() не найдена."
        )

        return 1

    print(
        "  OK: process_track() найдена."
    )

    if "process_yandex_playlist" not in functions:

        print(
            "  ОШИБКА: process_yandex_playlist() не найдена."
        )

        return 1

    print(
        "  OK: process_yandex_playlist() найдена."
    )

    if "process_youtube_playlist" in functions:

        print(
            "  ОШИБКА: process_youtube_playlist() "
            "уже существует."
        )

        print(
            "Патч не будет применён повторно."
        )

        return 1

    print(
        "  OK: process_youtube_playlist() "
        "отсутствует — будет добавлена."
    )

    with open(
        BOT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        source = f.read()

    print()
    print(
        "Поиск точки вставки..."
    )

    try:

        process_track_start = (
            find_process_track_start(
                source
            )
        )

    except Exception as e:

        print(
            f"  ОШИБКА: {e}"
        )

        return 1

    print(
        "  OK: process_track() найден."
    )

    print()
    print(
        "Поиск YouTube Music ветки..."
    )

    try:

        target_start, target_end = (
            find_polling_youtube_branch(
                source
            )
        )

    except Exception as e:

        print(
            f"  ОШИБКА: {e}"
        )

        return 1

    print(
        "  OK: текущая YouTube Music ветка найдена."
    )

    print()
    print(
        "Создание резервной копии..."
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = (
        f"{BOT_FILE}.backup_{timestamp}"
    )

    shutil.copy2(
        BOT_FILE,
        backup
    )

    print(
        f"  OK: {backup}"
    )

    try:

        print()
        print(
            "1/2: добавление process_youtube_playlist()..."
        )

        new_source = (
            source[
                :process_track_start
            ]
            + YOUTUBE_PLAYLIST_FUNCTION
            + "\n"
            + source[
                process_track_start:
            ]
        )

        print(
            "  OK"
        )

        print()
        print(
            "2/2: обновление маршрутизации "
            "YouTube Music-плейлиста..."
        )

        # После вставки функции абсолютные позиции
        # polling-блока могли измениться, поэтому
        # ищем его повторно уже в новом тексте.
        new_target_start, new_target_end = (
            find_polling_youtube_branch(
                new_source
            )
        )

        new_source = (
            new_source[
                :new_target_start
            ]
            + "target=process_youtube_playlist,"
            + new_source[
                new_target_end:
            ]
        )

        print(
            "  OK"
        )

        print()
        print(
            "Проверка результата..."
        )

        # Сначала проверяем AST до записи.
        ast.parse(
            new_source,
            filename=BOT_FILE
        )

        new_functions = get_function_names_from_source(
            new_source
        )

        if "process_track" not in new_functions:
            raise RuntimeError(
                "После патча пропала process_track()."
            )

        if "process_yandex_playlist" not in new_functions:
            raise RuntimeError(
                "После патча пропала process_yandex_playlist()."
            )

        if "process_youtube_playlist" not in new_functions:
            raise RuntimeError(
                "process_youtube_playlist() "
                "не добавилась."
            )

        if (
            "target=process_youtube_playlist,"
            not in new_source
        ):
            raise RuntimeError(
                "Маршрутизация YouTube Music "
                "не была изменена."
            )

        # Проверяем, что Яндекс остался на месте.
        if (
            "target=process_yandex_playlist,"
            not in new_source
        ):
            raise RuntimeError(
                "Маршрутизация Яндекс-плейлиста "
                "была повреждена."
            )

        with open(
            BOT_FILE,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:

            f.write(
                new_source
            )

        syntax_check(
            BOT_FILE
        )

        print(
            "  OK: синтаксис."
        )

        final_functions = get_function_names(
            BOT_FILE
        )

        print()
        print(
            "ИТОГ:"
        )

        print(
            "  process_track(): "
            + (
                "OK"
                if "process_track" in final_functions
                else "MISSING"
            )
        )

        print(
            "  process_yandex_playlist(): "
            + (
                "OK"
                if "process_yandex_playlist"
                in final_functions
                else "MISSING"
            )
        )

        print(
            "  process_youtube_playlist(): "
            + (
                "OK"
                if "process_youtube_playlist"
                in final_functions
                else "MISSING"
            )
        )

        print()
        print(
            "ПАТЧ УСПЕШНО ПРИМЕНЁН."
        )

        print(
            f"Резервная копия: {backup}"
        )

        return 0

    except Exception as e:

        print()
        print(
            "ОШИБКА:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Автоматический откат..."
        )

        try:

            shutil.copy2(
                backup,
                BOT_FILE
            )

            syntax_check(
                BOT_FILE
            )

            print(
                "  OK: bot.py восстановлен."
            )

        except Exception as rollback_error:

            print(
                "КРИТИЧЕСКАЯ ОШИБКА ОТКАТА:"
            )

            print(
                f"{type(rollback_error).__name__}: "
                f"{rollback_error}"
            )

        return 1


def get_function_names_from_source(
    source
):
    tree = ast.parse(
        source,
        filename=BOT_FILE
    )

    return {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }


if __name__ == "__main__":
    raise SystemExit(
        main()
  )
