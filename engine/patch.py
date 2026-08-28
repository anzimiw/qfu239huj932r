from pathlib import Path
from datetime import datetime
import shutil
import ast


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

    return backup


def main():

    print("=" * 70)
    print("ПАТЧ YOUTUBE FAST POST-PROCESSING")
    print("=" * 70)
    print()

    if not BOT.is_file():
        raise RuntimeError(
            "Не найден bot.py."
        )

    backup = backup_file(BOT)

    print(
        f"Резервная копия: {backup.name}"
    )

    text = BOT.read_text(
        encoding="utf-8"
    )

    # ------------------------------------------------------------
    # 1. Ищем точный существующий блок после успешного скачивания
    # ------------------------------------------------------------

    marker_start = """        file_size = os.path.getsize(
            file_path
        )

        print()
        print("MP3 создан:")
        print(f"  {file_path}")
        print(f"  Размер: {file_size:,} байт")
"""

    if marker_start not in text:
        raise RuntimeError(
            "Не найден блок проверки созданного MP3."
        )

    # ------------------------------------------------------------
    # 2. Добавляем POST-DOWNLOAD METADATA
    # ------------------------------------------------------------

    replacement_start = """        file_size = os.path.getsize(
            file_path
        )

        # ----------------------------------------------------
        # YOUTUBE FAST:
        # метаданные получаем ТОЛЬКО ПОСЛЕ успешного скачивания.
        #
        # Это сохраняет быстрый путь:
        #
        #     URL -> MP3
        #
        # Но перед post-processing нам всё равно нужны:
        #     artist
        #     title
        #     duration
        #     album
        #     cover_url
        # ----------------------------------------------------

        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "YouTube Fast: MP3 уже скачан."
            )

            print(
                "YouTube Fast: "
                "получение метаданных ПОСЛЕ скачивания..."
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
                    "пост-метаданные получены."
                )

                info.update(
                    post_info
                )

                # Не теряем признак Fast-пути.
                info["fast_youtube"] = True

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
                    info.get(
                        "age_restricted",
                        False
                    )
                )

                print(
                    "Исполнитель:",
                    artist
                )

                print(
                    "Название:",
                    title
                )

                print(
                    "Альбом:",
                    info.get(
                        "album",
                        ""
                    )
                    or "не определён"
                )

                print(
                    "Длительность:",
                    duration
                )

                print(
                    "Обложка:",
                    (
                        "НАЙДЕНА"
                        if info.get("cover_url")
                        else "НЕ НАЙДЕНА"
                    )
                )

            else:

                print()
                print(
                    "YouTube Fast: "
                    "не удалось получить "
                    "пост-метаданные."
                )

                print(
                    "Продолжаю обработку "
                    "скачанного MP3 без них."
                )

        file_size = os.path.getsize(
            file_path
        )

        print()
        print("MP3 создан:")
        print(f"  {file_path}")
        print(f"  Размер: {file_size:,} байт")
"""

    text = text.replace(
        marker_start,
        replacement_start,
        1
    )

    # ------------------------------------------------------------
    # 3. Проверяем, что новый блок действительно вставился
    # ------------------------------------------------------------

    if (
        "YouTube Fast: "
        "получение метаданных ПОСЛЕ скачивания..."
        not in text
    ):
        raise RuntimeError(
            "Не удалось вставить "
            "YouTube Fast post-processing."
        )

    # ------------------------------------------------------------
    # 4. Переименование Fast-файла после получения metadata
    # ------------------------------------------------------------

    marker_embed = """        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
"""

    if marker_embed not in text:
        raise RuntimeError(
            "Не найден блок embed_cover()."
        )

    replacement_embed = """        # ----------------------------------------------------
        # YOUTUBE FAST:
        # после получения metadata переименовываем временный
        # youtube_fast_*.mp3 в нормальное имя.
        #
        # Это делается ДО создания LRC, чтобы:
        #
        #     Artist - Title.mp3
        #     Artist - Title.lrc
        #
        # имели одинаковое имя.
        # ----------------------------------------------------

        if (
            info.get("fast_youtube", False)
            and artist
            and title
        ):

            safe_artist = downloader.safe_filename(
                artist
            )

            safe_title = downloader.safe_filename(
                title
            )

            target_name = (
                f"{safe_artist} - {safe_title}.mp3"
            )

            target_path = os.path.join(
                TRACKS_FOLDER,
                target_name
            )

            target_path = os.path.abspath(
                target_path
            )

            current_path = os.path.abspath(
                file_path
            )

            if target_path != current_path:

                if os.path.exists(
                    target_path
                ):

                    base_name = (
                        f"{safe_artist} - {safe_title}"
                    )

                    counter = 1

                    while True:

                        candidate_name = (
                            f"{base_name} "
                            f"({counter}).mp3"
                        )

                        candidate_path = os.path.join(
                            TRACKS_FOLDER,
                            candidate_name
                        )

                        if not os.path.exists(
                            candidate_path
                        ):
                            target_path = candidate_path
                            break

                        counter += 1

                try:

                    os.replace(
                        file_path,
                        target_path
                    )

                    file_path = target_path

                    print()
                    print(
                        "YouTube Fast: "
                        "файл переименован:"
                    )

                    print(
                        f"  {file_path}"
                    )

                except Exception as rename_error:

                    print()
                    print(
                        "YouTube Fast: "
                        "не удалось переименовать файл:"
                    )

                    print(
                        f"{type(rename_error).__name__}: "
                        f"{rename_error}"
                    )

        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
"""

    text = text.replace(
        marker_embed,
        replacement_embed,
        1
    )

    # ------------------------------------------------------------
    # 5. Записываем файл
    # ------------------------------------------------------------

    BOT.write_text(
        text,
        encoding="utf-8"
    )

    # ------------------------------------------------------------
    # 6. AST-проверка
    # ------------------------------------------------------------

    try:

        ast.parse(
            text,
            filename=str(BOT)
        )

    except SyntaxError:

        print()
        print(
            "ОШИБКА: bot.py содержит "
            "синтаксическую ошибку."
        )

        shutil.copy2(
            backup,
            BOT
        )

        print(
            f"Восстановлен: {BOT.name}"
        )

        raise

    # ------------------------------------------------------------
    # 7. Финальная проверка ключевых элементов
    # ------------------------------------------------------------

    required = (
        'info.get(\n'
        '            "fast_youtube",\n'
        '            False\n'
        '        )',
        "get_youtube_music_info(",
        "post_info",
        "downloader.embed_cover(",
        "downloader.process_lrc(",
        "os.replace("
    )

    missing = []

    for item in required:

        if item not in text:
            missing.append(
                item
            )

    if missing:

        print()
        print(
            "ОШИБКА: финальная проверка не пройдена."
        )

        shutil.copy2(
            backup,
            BOT
        )

        print(
            f"Восстановлен: {BOT.name}"
        )

        raise RuntimeError(
            "Не найдены элементы: "
            + ", ".join(missing)
        )

    print()
    print("=" * 70)
    print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
    print("=" * 70)
    print()
    print(
        "Изменён: bot.py"
    )
    print()
    print(
        "YouTube Fast теперь работает по схеме:"
    )
    print(
        "  1. URL -> MP3 без metadata"
    )
    print(
        "  2. MP3 успешно скачан"
    )
    print(
        "  3. Получение metadata ПОСЛЕ скачивания"
    )
    print(
        "  4. Получение cover"
    )
    print(
        "  5. ID3 + APIC"
    )
    print(
        "  6. LRC"
    )
    print(
        "  7. Нормальное имя MP3/LRC"
    )
    print(
        "  8. Отправка MP3"
    )
    print(
        "  9. Отправка LRC"
    )
    print()
    print(
        f"Резервная копия: {backup.name}"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as e:

        print()
        print("=" * 70)
        print("ПАТЧ НЕ ПРИМЕНЁН")
        print("=" * 70)
        print()
        print(
            f"{type(e).__name__}: {e}"
        )

        raise
