from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys


BOT_FILE = Path("bot.py")


def get_function_node(source, function_name):
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name == function_name:
                return node

    raise RuntimeError(
        f"Функция {function_name}() не найдена."
    )


def extract_function(source, function_name):
    node = get_function_node(
        source,
        function_name
    )

    lines = source.splitlines(keepends=True)

    return "".join(
        lines[node.lineno - 1:node.end_lineno]
    )


def replace_function(source, function_name, new_function):
    node = get_function_node(
        source,
        function_name
    )

    lines = source.splitlines(keepends=True)

    start = node.lineno - 1
    end = node.end_lineno

    before = "".join(lines[:start])
    after = "".join(lines[end:])

    return (
        before
        + new_function.rstrip()
        + "\n\n"
        + after.lstrip("\n")
    )


NEW_PROCESS_TRACK = r'''def process_track(chat_id, url, playlist_progress=None):

    try:

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ ТРЕКА")
        print("=" * 70)
        print()
        print(f"URL: {url}")

        if playlist_progress:
            current_index, total_tracks = playlist_progress

            send_message(
                chat_id,
                (
                    f"Обработка трека "
                    f"{current_index}/{total_tracks}...\n\n"
                    f"Получаю информацию о треке..."
                )
            )
        else:
            send_message(
                chat_id,
                "Получаю информацию о треке..."
            )

        # ----------------------------------------------------
        # 1. Получение информации
        # ----------------------------------------------------

        print()
        print("Получение информации из downloader.py...")

        if downloader.is_yandex_music_url(url):

            print()
            print("Источник: Яндекс Музыка")
            print("Получение информации из Яндекс Музыки...")

            info = downloader.get_yandex_music_info(
                url
            )

        else:

            print()
            print("Источник: YouTube Music")
            print("Получение информации из YouTube Music...")

            info = downloader.get_youtube_music_info(
                url
            )

        if not info:

            send_message(
                chat_id,
                "Не удалось получить информацию о треке."
            )

            print(
                "ОШИБКА: получение информации вернуло "
                "пустой результат."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        print()
        print("Информация получена:")
        print(info)

        artist = info.get(
            "artist",
            ""
        )

        title = info.get(
            "title",
            ""
        )

        duration = info.get(
            "duration",
            0
        )

        source = info.get(
            "source",
            "youtube"
        )

        youtube_age_restricted = info.get(
            "youtube_age_restricted",
            False
        )

        if not artist or not title or not duration:

            send_message(
                chat_id,
                "Не удалось определить исполнителя, название или длительность."
            )

            print(
                "ОШИБКА: неполные метаданные."
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        # ----------------------------------------------------
        # Формат длительности: MM:SS
        # ----------------------------------------------------

        try:

            duration_seconds = int(
                float(duration)
            )

            minutes = duration_seconds // 60
            seconds = duration_seconds % 60

            duration_text = (
                f"{minutes}:{seconds:02d}"
            )

        except Exception:

            duration_text = str(
                duration
            )

        # ----------------------------------------------------
        # 2. Сообщение пользователю
        # ----------------------------------------------------

        if playlist_progress:

            current_index, total_tracks = playlist_progress

            status_text = (
                f"Обработка трека "
                f"{current_index}/{total_tracks}\n\n"
                f"{artist} — {title}\n"
                f"Длительность: {duration_text}\n\n"
                f"Начинаю поиск аудиофайла..."
            )

        else:

            status_text = (
                f"Трек найден:\n\n"
                f"Исполнитель: {artist}\n"
                f"Название: {title}\n"
                f"Длительность: {duration_text}\n\n"
                f"Начинаю поиск аудиофайла..."
            )

        send_message(
            chat_id,
            status_text
        )

        # ----------------------------------------------------
        # 3. Запуск существующего downloader.py
        # ----------------------------------------------------

        print()
        print("Запуск find_and_download_track()...")

        result = downloader.find_and_download_track(
            artist,
            title,
            duration,
            TRACKS_FOLDER,
            url,
            source,
            youtube_age_restricted
        )

        print()
        print("Результат downloader.py:")
        print(repr(result))

        if not result:

            send_message(
                chat_id,
                (
                    "Не удалось скачать аудиофайл.\n\n"
                    f"{artist} — {title}"
                )
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        # ----------------------------------------------------
        # 4. Проверка файла
        # ----------------------------------------------------

        file_path = str(result)

        if not os.path.isfile(file_path):

            send_message(
                chat_id,
                "downloader.py завершился, но MP3-файл не найден."
            )

            print(
                f"Файл не найден: {file_path}"
            )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return False

        file_size = os.path.getsize(
            file_path
        )

        print()
        print("MP3 создан:")
        print(f"  {file_path}")
        print(f"  Размер: {file_size:,} байт")

        # ----------------------------------------------------
        # Добавление embedded cover и ID3-тегов
        # ----------------------------------------------------

        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )

        # ----------------------------------------------------
        # Проверка embedded cover
        # ----------------------------------------------------

        try:

            from mutagen.id3 import ID3

            tags = ID3(file_path)

            apic_count = len(
                tags.getall("APIC:")
            )

            print(
                f"Embedded cover APIC: {apic_count}"
            )

            if apic_count > 0:
                print(
                    "OK: обложка действительно записана в MP3."
                )
            else:
                print(
                    "ВНИМАНИЕ: APIC отсутствует в MP3."
                )

        except Exception as cover_check_error:

            print(
                "Не удалось проверить embedded cover:",
                cover_check_error
            )

        # ----------------------------------------------------
        # Статус перед отправкой MP3
        # ----------------------------------------------------

        send_message(
            chat_id,
            (
                f"Трек скачан.\n\n"
                f"{artist} — {title}"
            )
        )

        print()
        print("ЭТАП СКАЧИВАНИЯ УСПЕШНО ЗАВЕРШЁН.")

        # ----------------------------------------------------
        # Отправка MP3 в Telegram
        # ----------------------------------------------------

        print()
        print("Отправка MP3 в Telegram...")

        upload_result = send_audio(
            chat_id,
            file_path
        )

        if upload_result.get("ok"):

            print(
                "MP3 успешно отправлен в Telegram."
            )

            if playlist_progress:

                current_index, total_tracks = playlist_progress

                send_message(
                    chat_id,
                    (
                        f"Трек {current_index}/{total_tracks} готов.\n\n"
                        f"{artist} — {title}\n\n"
                        f"Переход к следующему треку..."
                    )
                )

            else:

                send_message(
                    chat_id,
                    (
                        f"Трек готов.\n\n"
                        f"{artist} — {title}"
                    )
                )

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

            return True

        print(
            "Ошибка отправки MP3:"
        )

        print(
            upload_result
        )

        send_message(
            chat_id,
            (
                "Трек скачан, но Telegram "
                "не принял MP3 при отправке."
            )
        )

        globals().get(
            "_STATUS_MESSAGES",
            {}
        ).pop(
            chat_id,
            None
        )

        return False

    except Exception as e:

        print()
        print("=" * 70)
        print("ОШИБКА ОБРАБОТКИ ТРЕКА")
        print("=" * 70)
        print()

        print(
            f"{type(e).__name__}: {e}"
        )

        try:

            send_message(
                chat_id,
                "Произошла ошибка при обработке трека."
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

        return False
'''


NEW_PROCESS_PLAYLIST = r'''def process_yandex_playlist(chat_id, url):

    try:

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ ПЛЕЙЛИСТА")
        print("=" * 70)
        print()
        print(f"URL плейлиста: {url}")

        send_message(
            chat_id,
            "Получаю список треков Яндекс Музыки..."
        )

        print()
        print("Яндекс Музыка: получение списка треков...")

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
            or "Яндекс Музыка"
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
                f"ПЛЕЙЛИСТ: ТРЕК {index}/{total_tracks}"
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
                    "ОШИБКА ТРЕКА ПЛЕЙЛИСТА:"
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
        print("ПЛЕЙЛИСТ ЗАВЕРШЁН")
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
        print("ОШИБКА ОБРАБОТКИ ПЛЕЙЛИСТА")
        print("=" * 70)
        print()

        print(
            f"{type(e).__name__}: {e}"
        )

        try:

            send_message(
                chat_id,
                "Произошла ошибка при обработке плейлиста."
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


def main():

    print("=" * 70)
    print("CENSURU.NET — STATUS CLEANUP / FORMAT PATCH")
    print("=" * 70)
    print()

    if not BOT_FILE.exists():
        print("ОШИБКА: bot.py не найден.")
        return 1

    original = BOT_FILE.read_text(
        encoding="utf-8"
    )

    print("Проверка исходного bot.py...")

    try:
        ast.parse(original)
    except SyntaxError as e:
        print(
            f"ОШИБКА синтаксиса: {e}"
        )
        return 1

    print("  OK: исходный синтаксис.")

    print()
    print("Проверка функций...")

    try:
        extract_function(
            original,
            "process_track"
        )

        extract_function(
            original,
            "process_yandex_playlist"
        )

    except Exception as e:
        print(
            f"ОШИБКА: {e}"
        )
        return 1

    print("  OK: обе функции найдены.")

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = BOT_FILE.with_name(
        f"bot.py.backup_{timestamp}"
    )

    print()
    print("Создание резервной копии...")

    try:
        shutil.copy2(
            BOT_FILE,
            backup
        )
    except Exception as e:
        print(
            f"ОШИБКА создания backup: {e}"
        )
        return 1

    print(
        f"  OK: {backup.name}"
    )

    try:

        print()
        print("1/5: обновление process_track()...")

        patched = replace_function(
            original,
            "process_track",
            NEW_PROCESS_TRACK
        )

        print("  OK")

        print()
        print("2/5: обновление process_yandex_playlist()...")

        patched = replace_function(
            patched,
            "process_yandex_playlist",
            NEW_PROCESS_PLAYLIST
        )

        print("  OK")

        print()
        print("3/5: проверка синтаксиса...")

        ast.parse(patched)

        print("  OK")

        print()
        print("4/5: проверка изменений...")

        track = extract_function(
            patched,
            "process_track"
        )

        playlist = extract_function(
            patched,
            "process_yandex_playlist"
        )

        required_track = (
            "duration_text",
            "Длительность: {duration_text}",
            "Трек скачан.",
            "upload_result = send_audio(\n            chat_id,\n            file_path",
            "_STATUS_MESSAGES",
            ".pop(\n                chat_id",
        )

        for item in required_track:

            if item not in track:
                raise RuntimeError(
                    "process_track(): "
                    f"не найден ожидаемый фрагмент: {item}"
                )

        forbidden_track = (
            "Размер MP3:",
            "Размер MP3: {file_size:,} байт",
            "Файл:\n{os.path.basename(file_path)}",
            'caption=caption',
        )

        for item in forbidden_track:

            if item in track:
                raise RuntimeError(
                    "process_track(): "
                    f"старый пользовательский фрагмент остался: {item}"
                )

        required_playlist = (
            "_STATUS_MESSAGES",
            ".pop(\n            chat_id",
            "Обработка плейлиста завершена.",
        )

        for item in required_playlist:

            if item not in playlist:
                raise RuntimeError(
                    "process_yandex_playlist(): "
                    f"не найден ожидаемый фрагмент: {item}"
                )

        print("  OK: длительность форматируется как M:SS.")
        print("  OK: размер файла убран из сообщений.")
        print("  OK: имя файла убрано.")
        print("  OK: caption у MP3 убран.")
        print("  OK: статус очищается после обработки.")

        print()
        print("5/5: запись bot.py...")

        BOT_FILE.write_text(
            patched,
            encoding="utf-8"
        )

        written = BOT_FILE.read_text(
            encoding="utf-8"
        )

        ast.parse(written)

        print("  OK: bot.py записан и проверен.")

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
        print("=" * 70)
        print()
        print(f"Backup: {backup.name}")
        print()
        print("Изменения:")
        print("  1. Длительность: M:SS")
        print("  2. Размер MP3 удалён из сообщений")
        print("  3. Имя файла удалено из сообщений")
        print("  4. Caption у MP3 удалён")
        print("  5. После обработки статус очищается")
        print("  6. Следующая ссылка создаёт новое статусное сообщение")
        print()
        print("Polling не изменялся.")
        print("send_message()/edit_message() не изменялись.")
        print()

        return 0

    except Exception as e:

        print()
        print("=" * 70)
        print("ОШИБКА ПАТЧА — ВЫПОЛНЯЕТСЯ ОТКАТ")
        print("=" * 70)
        print()
        print(
            f"{type(e).__name__}: {e}"
        )

        try:

            shutil.copy2(
                backup,
                BOT_FILE
            )

            print()
            print("OK: bot.py восстановлен из backup.")

        except Exception as rollback_error:

            print()
            print("КРИТИЧЕСКАЯ ОШИБКА ОТКАТА:")
            print(
                f"{type(rollback_error).__name__}: "
                f"{rollback_error}"
            )

            return 2

        return 1


if __name__ == "__main__":
    sys.exit(main())
