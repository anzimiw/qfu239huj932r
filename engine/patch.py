from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys


BOT = Path("bot.py")


def backup_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(
        f"{path.name}.backup_{timestamp}"
    )

    shutil.copy2(
        path,
        backup
    )

    print(
        f"Резервная копия: {backup.name}"
    )

    return backup


def fail(message):
    raise RuntimeError(message)


def main():
    print()
    print("=" * 70)
    print("ПАТЧ YOUTUBE FAST POST-PROCESSING")
    print("=" * 70)
    print()

    if not BOT.exists():
        fail(
            "Не найден bot.py. "
            "Запусти патч из папки engine."
        )

    original = BOT.read_text(
        encoding="utf-8"
    )

    backup = backup_file(
        BOT
    )

    text = original

    # ============================================================
    # 1. Добавляем флаг состояния fast metadata
    # ============================================================

    marker = '''        # ----------------------------------------------------
        # 4. Проверка файла
        # ----------------------------------------------------
'''

    if marker not in text:
        fail(
            "Не найден блок "
            "'4. Проверка файла' в bot.py."
        )

    replacement = '''        # ----------------------------------------------------
        # FAST YOUTUBE POST-PROCESSING STATE
        # ----------------------------------------------------

        fast_youtube_metadata_ready = (
            not info.get(
                "fast_youtube",
                False
            )
        )

        # ----------------------------------------------------
        # 4. Проверка файла
        # ----------------------------------------------------
'''

    if text.count(marker) != 1:
        fail(
            "Блок проверки файла найден "
            "не один раз."
        )

    text = text.replace(
        marker,
        replacement,
        1
    )

    # ============================================================
    # 2. После успешного fast download получаем metadata
    # ============================================================

    marker = '''        file_size = os.path.getsize(
            file_path
        )

        print()
        print("MP3 создан:")
'''

    if marker not in text:
        fail(
            "Не найден блок "
            "'file_size = os.path.getsize' "
            "в bot.py."
        )

    replacement = '''        file_size = os.path.getsize(
            file_path
        )

        # ========================================================
        # YOUTUBE FAST:
        # metadata получаем ТОЛЬКО ПОСЛЕ успешного скачивания.
        #
        # Это принципиально:
        #
        #   ДО скачивания:
        #       никаких get_youtube_music_info()
        #
        #   ПОСЛЕ скачивания:
        #       metadata -> cover / ID3 / LRC / имя файла
        # ========================================================

        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "=" * 60
            )
            print(
                "YOUTUBE FAST: "
                "ПОСТ-ОБРАБОТКА"
            )
            print(
                "=" * 60
            )

            print()
            print(
                "YouTube Fast: MP3 уже скачан."
            )

            print(
                "YouTube Fast: "
                "получение metadata ПОСЛЕ скачивания..."
            )

            post_info = (
                downloader.get_youtube_music_info(
                    url
                )
            )

            if post_info:

                post_artist = (
                    post_info.get(
                        "artist",
                        ""
                    )
                )

                post_title = (
                    post_info.get(
                        "title",
                        ""
                    )
                )

                post_duration = (
                    post_info.get(
                        "duration",
                        0
                    )
                )

                if (
                    post_artist
                    and post_title
                    and post_duration
                ):

                    info.update(
                        post_info
                    )

                    info[
                        "fast_youtube"
                    ] = True

                    info[
                        "youtube_age_restricted"
                    ] = bool(
                        post_info.get(
                            "age_restricted",
                            False
                        )
                    )

                    artist = post_artist
                    title = post_title
                    duration = post_duration

                    source = info.get(
                        "source",
                        "youtube"
                    )

                    youtube_age_restricted = (
                        info.get(
                            "youtube_age_restricted",
                            False
                        )
                    )

                    fast_youtube_metadata_ready = True

                    print()
                    print(
                        "YouTube Fast: "
                        "metadata успешно получены."
                    )

                    print(
                        f"  Исполнитель: {artist}"
                    )

                    print(
                        f"  Название: {title}"
                    )

                    print(
                        f"  Длительность: {duration}"
                    )

                    # ------------------------------------------------
                    # Переименование временного fast-файла.
                    # ------------------------------------------------

                    final_filename = (
                        f"{downloader.safe_filename(artist)} - "
                        f"{downloader.safe_filename(title)}.mp3"
                    )

                    final_path = (
                        Path(
                            TRACKS_FOLDER
                        )
                        / final_filename
                    )

                    final_path = str(
                        final_path
                    )

                    if os.path.abspath(
                        final_path
                    ) != os.path.abspath(
                        file_path
                    ):

                        print()
                        print(
                            "YouTube Fast: "
                            "переименование MP3..."
                        )

                        try:

                            if os.path.exists(
                                final_path
                            ):
                                os.remove(
                                    final_path
                                )

                            os.replace(
                                file_path,
                                final_path
                            )

                            file_path = final_path

                            print(
                                "YouTube Fast: "
                                "итоговое имя:"
                            )

                            print(
                                f"  {file_path}"
                            )

                        except Exception as rename_error:

                            print(
                                "YouTube Fast: "
                                "не удалось переименовать файл:"
                            )

                            print(
                                f"{type(rename_error).__name__}: "
                                f"{rename_error}"
                            )

                else:

                    print()
                    print(
                        "YouTube Fast: "
                        "metadata получены, "
                        "но они неполные."
                    )

                    print(
                        "YouTube Fast: "
                        "оставляю техническое имя MP3."
                    )

            else:

                print()
                print(
                    "YouTube Fast: "
                    "metadata после скачивания "
                    "получить не удалось."
                )

                print(
                    "YouTube Fast: "
                    "MP3 сохраняется."
                )

        print()
        print("MP3 создан:")
'''

    if text.count(marker) != 1:
        fail(
            "Блок post-download metadata "
            "найден не один раз."
        )

    text = text.replace(
        marker,
        replacement,
        1
    )

    # ============================================================
    # 3. Cover только при наличии metadata
    # ============================================================

    old = '''        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )
'''

    if old not in text:
        fail(
            "Не найден блок embed_cover()."
        )

    new = '''        print()
        print("Добавление обложки в MP3...")

        if (
            fast_youtube_metadata_ready
            and artist
            and title
            and duration
        ):

            downloader.embed_cover(
                file_path,
                info.get("cover_url"),
                artist,
                title,
                info.get("album", "")
            )

        elif info.get(
            "fast_youtube",
            False
        ):

            print(
                "YouTube Fast: "
                "обложка пропущена — "
                "metadata недоступны."
            )

        else:

            downloader.embed_cover(
                file_path,
                info.get("cover_url"),
                artist,
                title,
                info.get("album", "")
            )
'''

    if text.count(old) != 1:
        fail(
            "Блок embed_cover() найден "
            "не один раз."
        )

    text = text.replace(
        old,
        new,
        1
    )

    # ============================================================
    # 4. LRC только при наличии полноценной metadata
    # ============================================================

    old = '''        if effective_with_lrc:
            time.sleep(
                downloader.LRCLIB_DELAY
            )
            downloader.process_lrc(
                artist,
                title,
                info.get("album", ""),
                duration,
                file_path
            )
'''

    if old not in text:
        fail(
            "Не найден блок process_lrc()."
        )

    new = '''        if (
            effective_with_lrc
            and artist
            and title
            and duration
            and fast_youtube_metadata_ready
        ):

            time.sleep(
                downloader.LRCLIB_DELAY
            )

            downloader.process_lrc(
                artist,
                title,
                info.get("album", ""),
                duration,
                file_path
            )

        elif (
            effective_with_lrc
            and info.get(
                "fast_youtube",
                False
            )
        ):

            print()
            print(
                "YouTube Fast: "
                "LRC пропущен — "
                "metadata недоступны."
            )
'''

    if text.count(old) != 1:
        fail(
            "Блок process_lrc() найден "
            "не один раз."
        )

    text = text.replace(
        old,
        new,
        1
    )

    # ============================================================
    # 5. Финальное сообщение для fast-пути
    # ============================================================

    old = '''        send_message(
            chat_id,
            (
                f"Трек скачан.\\n\\n"
                f"{artist} — {title}"
            )
        )
'''

    if old not in text:
        fail(
            "Не найдено финальное сообщение "
            "'Трек скачан'."
        )

    new = '''        if (
            info.get(
                "fast_youtube",
                False
            )
            and (
                not artist
                or not title
            )
        ):

            download_status_text = (
                "Трек скачан."
            )

        else:

            download_status_text = (
                f"Трек скачан.\\n\\n"
                f"{artist} — {title}"
            )

        send_message(
            chat_id,
            download_status_text
        )
'''

    if text.count(old) != 1:
        fail(
            "Финальное сообщение "
            "найдено не один раз."
        )

    text = text.replace(
        old,
        new,
        1
    )

    # ============================================================
    # 6. Сохраняем
    # ============================================================

    BOT.write_text(
        text,
        encoding="utf-8"
    )

    print()
    print("bot.py: патч записан.")

    # ============================================================
    # 7. Проверка синтаксиса
    # ============================================================

    print()
    print(
        "Проверка синтаксиса bot.py..."
    )

    try:

        py_compile.compile(
            str(BOT),
            doraise=True
        )

    except Exception as error:

        print()
        print(
            "=" * 70
        )
        print(
            "ОШИБКА СИНТАКСИСА."
        )
        print(
            "=" * 70
        )

        print(
            error
        )

        print()
        print(
            "Восстанавливаю резервную копию..."
        )

        shutil.copy2(
            backup,
            BOT
        )

        print(
            "bot.py восстановлен."
        )

        raise

    print(
        "OK"
    )

    # ============================================================
    # 8. Финальная проверка ключевых участков
    # ============================================================

    patched = BOT.read_text(
        encoding="utf-8"
    )

    required_markers = (
        "YOUTUBE FAST POST-PROCESSING STATE",
        "YouTube Fast: "
        "получение metadata ПОСЛЕ скачивания...",
        "fast_youtube_metadata_ready",
        "YouTube Fast: "
        "metadata успешно получены.",
    )

    print()
    print(
        "Проверка наличия патча..."
    )

    for marker in required_markers:

        if marker not in patched:

            print()
            print(
                "ОШИБКА: не найден marker:"
            )

            print(
                marker
            )

            print()
            print(
                "Восстанавливаю резервную копию..."
            )

            shutil.copy2(
                backup,
                BOT
            )

            print(
                "bot.py восстановлен."
            )

            raise RuntimeError(
                "Финальная проверка патча не пройдена."
            )

    print(
        "OK"
    )

    print()
    print("=" * 70)
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print("=" * 70)
    print()

    print(
        "Изменён: bot.py"
    )

    print(
        f"Backup: {backup.name}"
    )

    print()
    print(
        "Новая схема YouTube + normal:"
    )

    print(
        "  1. DIRECT FAST DOWNLOAD"
    )

    print(
        "  2. POST-DOWNLOAD METADATA"
    )

    print(
        "  3. Переименование MP3"
    )

    print(
        "  4. Cover + ID3"
    )

    print(
        "  5. LRC"
    )

    print(
        "  6. Telegram"
    )

    print()
    print(
        "Yandex и uncensored pipeline "
        "не изменялись."
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "ПАТЧ НЕ ПРИМЕНЁН"
        )
        print("=" * 70)
        print()

        print(
            f"{type(error).__name__}: {error}"
        )

        sys.exit(1)
