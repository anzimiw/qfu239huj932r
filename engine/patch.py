from pathlib import Path
from datetime import datetime
import shutil
import py_compile


ENGINE = Path(__file__).resolve().parent
BOT = ENGINE / "bot.py"


def backup_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(
        f"{path.name}.backup_{timestamp}"
    )
    shutil.copy2(path, backup)
    print(f"Резервная копия: {backup.name}")
    return backup


def main():
    print("=" * 70)
    print("ПАТЧ YOUTUBE FAST POST-PROCESSING V2")
    print("=" * 70)
    print()

    if not BOT.is_file():
        raise RuntimeError(
            f"Не найден файл: {BOT}"
        )

    print("Создание резервной копии...")
    backup = backup_file(BOT)

    try:
        text = BOT.read_text(
            encoding="utf-8"
        )

        # ------------------------------------------------------------
        # Ищем актуальный Fast-блок.
        # ------------------------------------------------------------

        marker_start = '''        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "Запуск YouTube Fast..."
            )
'''

        marker_end = '''        else:

            result = downloader.find_and_download_track(
'''

        start = text.find(marker_start)

        if start < 0:
            raise RuntimeError(
                "Не найден актуальный блок YouTube Fast "
                "в bot.py."
            )

        end = text.find(
            marker_end,
            start
        )

        if end < 0:
            raise RuntimeError(
                "Не найден конец блока YouTube Fast "
                "в bot.py."
            )

        old_block = text[start:end]

        # ------------------------------------------------------------
        # Новый Fast-блок.
        #
        # До скачивания metadata НЕ получаются.
        #
        # После успешного скачивания:
        #   1. получаем metadata;
        #   2. обновляем artist/title/duration/source;
        #   3. переименовываем MP3;
        #   4. общий post-processing использует нормальные данные.
        # ------------------------------------------------------------

        new_block = '''        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "Запуск YouTube Fast..."
            )

            result = downloader.download_youtube_fast_direct(
                url,
                TRACKS_FOLDER
            )

            if result:
                print()
                print(
                    "YouTube Fast: "
                    "MP3 скачан."
                )

                print()
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
                    print()
                    print(
                        "YouTube Fast: "
                        "metadata успешно получены."
                    )

                    artist = post_info.get(
                        "artist",
                        ""
                    )

                    title = post_info.get(
                        "title",
                        ""
                    )

                    duration = post_info.get(
                        "duration",
                        0
                    )

                    source = post_info.get(
                        "source",
                        "youtube"
                    )

                    youtube_age_restricted = post_info.get(
                        "youtube_age_restricted",
                        post_info.get(
                            "age_restricted",
                            False
                        )
                    )

                    album = post_info.get(
                        "album",
                        ""
                    )

                    cover_url = post_info.get(
                        "cover_url"
                    )

                    print()
                    print(
                        "YouTube Fast metadata:"
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
                    print(
                        f"  Альбом: {album}"
                    )
                    print(
                        "  Обложка: "
                        f"{'НАЙДЕНА' if cover_url else 'НЕ НАЙДЕНА'}"
                    )

                    # ------------------------------------------------
                    # Переименование Fast-файла.
                    # ------------------------------------------------

                    if artist and title:

                        old_filepath = str(
                            result
                        )

                        new_filename = (
                            f"{downloader.safe_filename(artist)}"
                            f" - "
                            f"{downloader.safe_filename(title)}"
                            f".mp3"
                        )

                        new_filepath = os.path.join(
                            TRACKS_FOLDER,
                            new_filename
                        )

                        if (
                            os.path.abspath(
                                old_filepath
                            )
                            !=
                            os.path.abspath(
                                new_filepath
                            )
                        ):

                            try:

                                if os.path.isfile(
                                    new_filepath
                                ):
                                    os.remove(
                                        new_filepath
                                    )

                                os.replace(
                                    old_filepath,
                                    new_filepath
                                )

                                result = new_filepath

                                print()
                                print(
                                    "YouTube Fast: "
                                    "MP3 переименован:"
                                )
                                print(
                                    f"  {result}"
                                )

                            except Exception as rename_error:

                                print()
                                print(
                                    "YouTube Fast: "
                                    "не удалось переименовать MP3:"
                                )
                                print(
                                    f"{type(rename_error).__name__}: "
                                    f"{rename_error}"
                                )

                    # ------------------------------------------------
                    # Обновляем info для общего post-processing.
                    # ------------------------------------------------

                    info.update(
                        post_info
                    )

                    info[
                        "artist"
                    ] = artist

                    info[
                        "title"
                    ] = title

                    info[
                        "duration"
                    ] = duration

                    info[
                        "album"
                    ] = album

                    info[
                        "cover_url"
                    ] = cover_url

                else:

                    print()
                    print(
                        "YouTube Fast: "
                        "metadata после скачивания "
                        "получить не удалось."
                    )

                    print(
                        "YouTube Fast: "
                        "MP3 будет отправлен без "
                        "новых metadata."
                    )

'''
        # Проверяем, что заменяем именно ожидаемый блок.
        if "download_youtube_fast_direct" not in old_block:
            raise RuntimeError(
                "Найденный Fast-блок не содержит "
                "download_youtube_fast_direct()."
            )

        text = (
            text[:start]
            + new_block
            + text[end:]
        )

        BOT.write_text(
            text,
            encoding="utf-8"
        )

        print()
        print("Патч bot.py применён.")

        # ------------------------------------------------------------
        # Проверка синтаксиса.
        # ------------------------------------------------------------

        print()
        print("Финальная проверка bot.py...")

        py_compile.compile(
            str(BOT),
            doraise=True
        )

        print("OK")

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
        print("=" * 70)
        print()
        print("Изменён:")
        print("  bot.py")
        print()
        print("Новая схема YouTube Fast:")
        print("  1. прямое скачивание")
        print("  2. metadata ПОСЛЕ скачивания")
        print("  3. нормальное имя MP3")
        print("  4. embedded cover + ID3")
        print("  5. LRC")
        print("  6. отправка в Telegram")

    except Exception as error:

        print()
        print("=" * 70)
        print("ПАТЧ НЕ ПРИМЕНЁН")
        print("=" * 70)
        print()
        print(
            f"{type(error).__name__}: {error}"
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
            f"Восстановлен: {BOT.name}"
        )

        raise


if __name__ == "__main__":
    main()
