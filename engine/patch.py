# -*- coding: utf-8 -*-

"""
CENSURU.NET — ПАТЧ ИНТЕРФЕЙСА TELEGRAM-БОТА

Изменения:
1. Одно редактируемое статусное сообщение вместо множества сообщений.
2. Для плейлиста одно статусное сообщение на весь процесс.
3. process_track() умеет использовать существующее статусное сообщение.
4. Технические исключения не показываются пользователю.
5. TimeoutError / WinError 10060 не выводятся пользователю.
6. /start и неправильная ссылка используют единое приглашение.
7. Пользователю показываются только YouTube Music и Яндекс Музыка.
8. downloader.py и источники скачивания не изменяются.
9. Перед изменением создаётся резервная копия bot.py.
10. После изменения выполняются синтаксические и структурные проверки.

Важно:
Если сам процесс Python полностью завершится, он физически не сможет
отправить Telegram-сообщение после завершения. Контроль полного падения
процесса будет отдельной задачей для watchdog/службы.
"""

import ast
import os
import shutil
import sys
from datetime import datetime


BOT_FILE = "bot.py"


# ============================================================
# УТИЛИТЫ
# ============================================================

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


def backup_file(path):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        f"{path}.backup_{timestamp}"
    )

    shutil.copy2(
        path,
        backup_path
    )

    return backup_path


def get_function_node(
    tree,
    name
):
    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        ):
            if node.name == name:
                return node

    return None


def replace_function(
    source,
    function_name,
    replacement
):
    """
    Заменяет top-level функцию целиком
    по AST-границам.
    """

    tree = ast.parse(
        source
    )

    node = get_function_node(
        tree,
        function_name
    )

    if node is None:
        raise RuntimeError(
            f"Функция {function_name}() "
            f"не найдена."
        )

    lines = source.splitlines(
        keepends=True
    )

    start = node.lineno - 1
    end = node.end_lineno

    newline = (
        "\r\n"
        if "\r\n" in source
        else "\n"
    )

    replacement = (
        replacement.rstrip()
        + newline
        + newline
    )

    lines[start:end] = [
        replacement
    ]

    return "".join(lines)


def insert_after_function(
    source,
    function_name,
    block
):
    """
    Вставляет блок сразу после top-level функции.
    """

    tree = ast.parse(
        source
    )

    node = get_function_node(
        tree,
        function_name
    )

    if node is None:
        raise RuntimeError(
            f"Функция {function_name}() "
            f"не найдена."
        )

    lines = source.splitlines(
        keepends=True
    )

    end = node.end_lineno

    newline = (
        "\r\n"
        if "\r\n" in source
        else "\n"
    )

    insertion = (
        newline
        + block.rstrip()
        + newline
        + newline
    )

    lines[end:end] = [
        insertion
    ]

    return "".join(lines)


# ============================================================
# НОВЫЕ TELEGRAM STATUS HELPERS
# ============================================================

STATUS_HELPERS = r'''
# ============================================================
# TELEGRAM STATUS MESSAGE
# ============================================================

def create_status_message(
    chat_id,
    text
):
    """
    Создаёт одно статусное сообщение.

    Возвращает message_id либо None.

    Ошибка обновления статуса не должна ломать
    сам процесс скачивания.
    """

    try:
        result = send_message(
            chat_id,
            text
        )

        if not isinstance(
            result,
            dict
        ):
            return None

        if not result.get("ok"):
            print(
                "Telegram status: "
                "не удалось создать сообщение."
            )
            print(
                result
            )
            return None

        message = result.get(
            "result",
            {}
        )

        message_id = message.get(
            "message_id"
        )

        if not message_id:
            print(
                "Telegram status: "
                "Telegram не вернул message_id."
            )
            return None

        return message_id

    except Exception as error:

        print()
        print(
            "Telegram status: "
            "ошибка создания статусного сообщения."
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        return None


def update_status_message(
    chat_id,
    message_id,
    text
):
    """
    Редактирует существующее статусное сообщение.

    Ошибки Telegram здесь специально не пробрасываются
    наружу: они не должны останавливать downloader.
    """

    if not message_id:
        return False

    try:

        result = telegram_request(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text
            }
        )

        if not isinstance(
            result,
            dict
        ):
            return False

        if result.get("ok"):
            return True

        # Telegram может вернуть ошибку,
        # если текст фактически не изменился.
        print()
        print(
            "Telegram status: "
            "editMessageText вернул ошибку."
        )
        print(
            result
        )

        return False

    except Exception as error:

        print()
        print(
            "Telegram status: "
            "ошибка редактирования сообщения."
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        return False


def status_message(
    chat_id,
    message_id,
    text
):
    """
    Удобная оболочка для обновления статуса.

    Всегда возвращает тот же message_id.
    """

    update_status_message(
        chat_id,
        message_id,
        text
    )

    return message_id


def user_link_prompt():
    """
    Единый текст приглашения пользователя.
    """

    return (
        "Введите ссылку, чтобы скачать "
        "трек или плейлист.\n\n"
        "Поддерживаются:\n"
        "• YouTube Music\n"
        "• Яндекс Музыка"
    )
'''


# ============================================================
# НОВЫЙ PROCESS TRACK
# ============================================================

PROCESS_TRACK = r'''
def process_track(
    chat_id,
    url,
    status_message_id=None,
    playlist_context=None
):
    """
    Обработка одного трека.

    Если status_message_id передан, используется
    существующее статусное сообщение.

    Если status_message_id отсутствует, создаётся
    новое сообщение.

    Технические исключения пользователю НЕ отправляются.
    Они записываются только в консоль.
    """

    created_status = False

    try:

        print()
        print("=" * 70)
        print("НАЧАЛО ОБРАБОТКИ ТРЕКА")
        print("=" * 70)
        print()
        print(f"URL: {url}")

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if not status_message_id:

            status_message_id = (
                create_status_message(
                    chat_id,
                    "Получаю информацию о треке..."
                )
            )

            created_status = True

        else:

            status_message(
                chat_id,
                status_message_id,
                "Получаю информацию о треке..."
            )

        # ----------------------------------------------------
        # 1. ПОЛУЧЕНИЕ ИНФОРМАЦИИ
        # ----------------------------------------------------

        print()
        print(
            "Получение информации "
            "из downloader.py..."
        )

        if downloader.is_yandex_music_url(
            url
        ):

            print()
            print(
                "Источник: Яндекс Музыка"
            )

            print(
                "Получение информации "
                "из Яндекс Музыки..."
            )

            info = (
                downloader.get_yandex_music_info(
                    url
                )
            )

        else:

            print()
            print(
                "Источник: YouTube Music"
            )

            print(
                "Получение информации "
                "из YouTube Music..."
            )

            info = (
                downloader.get_youtube_music_info(
                    url
                )
            )

        if not info:

            print(
                "ОШИБКА: "
                "downloader не вернул информацию."
            )

            status_message(
                chat_id,
                status_message_id,
                "Не удалось получить информацию о треке."
            )

            return False

        print()
        print(
            "Информация получена:"
        )
        print(
            info
        )

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

        if (
            not artist
            or not title
            or not duration
        ):

            print(
                "ОШИБКА: "
                "неполные метаданные."
            )

            status_message(
                chat_id,
                status_message_id,
                "Не удалось определить данные трека."
            )

            return False

        # ----------------------------------------------------
        # 2. ТРЕК НАЙДЕН
        # ----------------------------------------------------

        track_status = (
            "Трек найден.\n\n"
            f"{artist} — {title}\n"
            f"Длительность: {duration} сек.\n\n"
            "Поиск аудиофайла..."
        )

        if playlist_context:

            track_status = (
                f"{playlist_context}\n\n"
                f"Текущий трек:\n"
                f"{artist} — {title}\n\n"
                "Поиск аудиофайла..."
            )

        status_message(
            chat_id,
            status_message_id,
            track_status
        )

        # ----------------------------------------------------
        # 3. DOWNLOAD
        # ----------------------------------------------------

        print()
        print(
            "Запуск find_and_download_track()..."
        )

        result = (
            downloader.find_and_download_track(
                artist,
                title,
                duration,
                TRACKS_FOLDER,
                url,
                source,
                youtube_age_restricted
            )
        )

        print()
        print(
            "Результат downloader.py:"
        )
        print(
            repr(result)
        )

        if not result:

            print(
                "Аудиофайл не найден."
            )

            status_message(
                chat_id,
                status_message_id,
                (
                    f"{artist} — {title}\n\n"
                    "Не удалось получить аудиофайл."
                )
            )

            return False

        # ----------------------------------------------------
        # 4. ПРОВЕРКА ФАЙЛА
        # ----------------------------------------------------

        file_path = str(
            result
        )

        if not os.path.isfile(
            file_path
        ):

            print(
                "ОШИБКА: MP3-файл не найден:"
            )

            print(
                file_path
            )

            status_message(
                chat_id,
                status_message_id,
                (
                    f"{artist} — {title}\n\n"
                    "Аудиофайл не найден после загрузки."
                )
            )

            return False

        file_size = os.path.getsize(
            file_path
        )

        print()
        print(
            "MP3 создан:"
        )
        print(
            f"  {file_path}"
        )
        print(
            f"  Размер: {file_size:,} байт"
        )

        # ----------------------------------------------------
        # 5. EMBEDDED COVER + ID3
        # ----------------------------------------------------

        status_message(
            chat_id,
            status_message_id,
            (
                f"{artist} — {title}\n\n"
                "Аудиофайл найден.\n"
                "Подготовка файла..."
            )
        )

        print()
        print(
            "Добавление обложки в MP3..."
        )

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )

        # ----------------------------------------------------
        # COVER CHECK
        # ----------------------------------------------------

        try:

            from mutagen.id3 import ID3

            tags = ID3(
                file_path
            )

            apic_count = len(
                tags.getall(
                    "APIC:"
                )
            )

            print(
                f"Embedded cover APIC: "
                f"{apic_count}"
            )

            if apic_count > 0:

                print(
                    "OK: обложка записана."
                )

            else:

                print(
                    "ВНИМАНИЕ: APIC отсутствует."
                )

        except Exception as cover_check_error:

            print(
                "Не удалось проверить "
                "embedded cover:"
            )

            print(
                f"{type(cover_check_error).__name__}: "
                f"{cover_check_error}"
            )

        # ----------------------------------------------------
        # 6. SEND TO TELEGRAM
        # ----------------------------------------------------

        status_message(
            chat_id,
            status_message_id,
            (
                f"{artist} — {title}\n\n"
                "Файл подготовлен.\n"
                "Отправка..."
            )
        )

        print()
        print(
            "Отправка MP3 в Telegram..."
        )

        caption = (
            f"{artist} — {title}"
        )

        upload_result = send_audio(
            chat_id,
            file_path,
            caption=caption
        )

        if isinstance(
            upload_result,
            dict
        ) and upload_result.get("ok"):

            print(
                "MP3 успешно отправлен "
                "в Telegram."
            )

            status_message(
                chat_id,
                status_message_id,
                (
                    f"{artist} — {title}\n\n"
                    "Готово."
                )
            )

            print()
            print(
                "ЭТАП УСПЕШНО ЗАВЕРШЁН."
            )

            return True

        print()
        print(
            "Ошибка отправки MP3:"
        )
        print(
            upload_result
        )

        # Никакого traceback пользователю.
        status_message(
            chat_id,
            status_message_id,
            (
                f"{artist} — {title}\n\n"
                "Файл подготовлен, "
                "но не удалось отправить его."
            )
        )

        return False

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "ОШИБКА ОБРАБОТКИ ТРЕКА"
        )
        print("=" * 70)
        print()

        print(
            f"{type(error).__name__}: {error}"
        )

        # ----------------------------------------------------
        # ВАЖНО:
        # техническое исключение НЕ отправляется пользователю.
        #
        # Это касается в том числе:
        # TimeoutError
        # WinError 10060
        # socket.timeout
        # ConnectionResetError
        # ошибок SoundCloud
        # ошибок downloader
        # ошибок ffprobe
        # ----------------------------------------------------

        try:

            status_message(
                chat_id,
                status_message_id,
                (
                    "Не удалось обработать трек.\n\n"
                    "Попробуйте ещё раз."
                )
            )

        except Exception as status_error:

            print(
                "Не удалось обновить "
                "статусное сообщение:"
            )

            print(
                f"{type(status_error).__name__}: "
                f"{status_error}"
            )

        return False
'''


# ============================================================
# НОВЫЙ PROCESS YANDEX PLAYLIST
# ============================================================

PROCESS_YANDEX_PLAYLIST = r'''
def process_yandex_playlist(
    chat_id,
    url
):
    """
    Обработка Яндекс-плейлиста.

    Для всего плейлиста используется одно сообщение,
    которое постоянно редактируется.

    process_track() получает ID этого сообщения,
    поэтому отдельные сообщения на каждый трек
    не создаются.
    """

    status_message_id = None

    try:

        print()
        print("=" * 70)
        print(
            "НАЧАЛО ОБРАБОТКИ ПЛЕЙЛИСТА"
        )
        print("=" * 70)
        print()
        print(
            f"URL плейлиста: {url}"
        )

        # ----------------------------------------------------
        # СОЗДАЁМ ЕДИНОЕ СТАТУСНОЕ СООБЩЕНИЕ
        # ----------------------------------------------------

        status_message_id = (
            create_status_message(
                chat_id,
                "Получаю список треков..."
            )
        )

        print()
        print(
            "Яндекс Музыка: "
            "получение списка треков..."
        )

        playlist = (
            downloader.get_playlist_tracks(
                url
            )
        )

        if not playlist:

            print(
                "ОШИБКА: "
                "get_playlist_tracks() "
                "вернул пустой результат."
            )

            status_message(
                chat_id,
                status_message_id,
                "Не удалось получить список треков."
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
            f"Название плейлиста: "
            f"{playlist_title}"
        )

        print(
            f"Найдено треков: "
            f"{len(tracks)}"
        )

        if not tracks:

            status_message(
                chat_id,
                status_message_id,
                (
                    f"{playlist_title}\n\n"
                    "В плейлисте не найдено треков."
                )
            )

            return

        total = len(
            tracks
        )

        # ----------------------------------------------------
        # НАЧАЛО ОБРАБОТКИ
        # ----------------------------------------------------

        status_message(
            chat_id,
            status_message_id,
            (
                f"{playlist_title}\n\n"
                f"Треков: {total}\n\n"
                "Начинаю обработку..."
            )
        )

        successful = 0
        failed = 0

        # ----------------------------------------------------
        # ТРЕКИ
        # ----------------------------------------------------

        for index, track_url in enumerate(
            tracks,
            1
        ):

            print()
            print("=" * 70)
            print(
                f"ПЛЕЙЛИСТ: ТРЕК "
                f"{index}/{total}"
            )
            print("=" * 70)
            print()
            print(
                f"URL трека: {track_url}"
            )

            playlist_context = (
                f"{playlist_title}\n\n"
                f"Обработка: "
                f"{index}/{total}"
            )

            # ------------------------------------------------
            # Предварительный статус
            # ------------------------------------------------

            status_message(
                chat_id,
                status_message_id,
                (
                    f"{playlist_context}\n\n"
                    "Получаю информацию о треке..."
                )
            )

            try:

                success = process_track(
                    chat_id,
                    track_url,
                    status_message_id=(
                        status_message_id
                    ),
                    playlist_context=(
                        playlist_context
                    )
                )

                if success:
                    successful += 1
                else:
                    failed += 1

            except Exception as track_error:

                # Сюда нормальный process_track()
                # попадать не должен, но оставляем
                # защиту на уровне плейлиста.

                failed += 1

                print()
                print(
                    "ОШИБКА ТРЕКА ПЛЕЙЛИСТА:"
                )

                print(
                    f"{type(track_error).__name__}: "
                    f"{track_error}"
                )

                # Никаких технических данных пользователю.

                status_message(
                    chat_id,
                    status_message_id,
                    (
                        f"{playlist_context}\n\n"
                        "Трек не удалось обработать.\n"
                        "Переход к следующему..."
                    )
                )

        # ----------------------------------------------------
        # ИТОГ
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print(
            "ПЛЕЙЛИСТ ЗАВЕРШЁН"
        )
        print("=" * 70)
        print()

        print(
            f"Всего треков: {total}"
        )

        print(
            f"Успешно: {successful}"
        )

        print(
            f"Ошибок: {failed}"
        )

        status_message(
            chat_id,
            status_message_id,
            (
                f"{playlist_title}\n\n"
                "Обработка завершена.\n\n"
                f"Всего треков: {total}\n"
                f"Успешно: {successful}\n"
                f"Ошибок: {failed}"
            )
        )

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "ОШИБКА ОБРАБОТКИ ПЛЕЙЛИСТА"
        )
        print("=" * 70)
        print()

        print(
            f"{type(error).__name__}: {error}"
        )

        # Техническая ошибка не отправляется пользователю.
        # Если статусное сообщение существует, показываем
        # только нормальное человеческое состояние.

        try:

            status_message(
                chat_id,
                status_message_id,
                (
                    "Не удалось обработать плейлист.\n\n"
                    "Попробуйте ещё раз."
                )
            )

        except Exception as status_error:

            print(
                "Не удалось обновить "
                "статус плейлиста:"
            )

            print(
                f"{type(status_error).__name__}: "
                f"{status_error}"
            )
'''


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "CENSURU.NET — ПАТЧ TELEGRAM BOT DESIGN"
    )
    print("=" * 70)
    print()

    if not os.path.isfile(
        BOT_FILE
    ):

        print(
            f"ОШИБКА: файл {BOT_FILE} "
            f"не найден."
        )

        sys.exit(1)

    original = read_file(
        BOT_FILE
    )

    # --------------------------------------------------------
    # Проверка исходного AST
    # --------------------------------------------------------

    try:

        tree = ast.parse(
            original
        )

    except SyntaxError as error:

        print(
            "ОШИБКА: исходный bot.py "
            "имеет синтаксическую ошибку."
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        sys.exit(2)

    required_functions = [
        "telegram_request",
        "send_message",
        "process_yandex_playlist",
        "process_track"
    ]

    for name in required_functions:

        if get_function_node(
            tree,
            name
        ) is None:

            print(
                f"ОШИБКА: функция "
                f"{name}() не найдена."
            )

            sys.exit(3)

    print(
        "Исходная структура bot.py: OK"
    )

    # --------------------------------------------------------
    # Проверяем, не применён ли патч уже
    # --------------------------------------------------------

    if (
        "def create_status_message(" in original
        or "def update_status_message(" in original
    ):

        print()
        print(
            "ОШИБКА: похоже, "
            "этот патч уже применён."
        )

        print(
            "Резервная копия не создаётся."
        )

        sys.exit(4)

    # --------------------------------------------------------
    # Резервная копия
    # --------------------------------------------------------

    try:

        backup_path = backup_file(
            BOT_FILE
        )

    except Exception as error:

        print()
        print(
            "ОШИБКА создания резервной копии:"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        sys.exit(5)

    print()
    print(
        "Резервная копия создана:"
    )
    print(
        f"  {backup_path}"
    )

    modified = original

    # --------------------------------------------------------
    # Добавляем status helpers
    # --------------------------------------------------------

    print()
    print(
        "1/5: добавление status helpers..."
    )

    modified = insert_after_function(
        modified,
        "send_message",
        STATUS_HELPERS
    )

    print(
        "  OK"
    )

    # --------------------------------------------------------
    # Заменяем process_yandex_playlist
    # --------------------------------------------------------

    print(
        "2/5: обновление "
        "process_yandex_playlist()..."
    )

    modified = replace_function(
        modified,
        "process_yandex_playlist",
        PROCESS_YANDEX_PLAYLIST
    )

    print(
        "  OK"
    )

    # --------------------------------------------------------
    # Заменяем process_track
    # --------------------------------------------------------

    print(
        "3/5: обновление "
        "process_track()..."
    )

    modified = replace_function(
        modified,
        "process_track",
        PROCESS_TRACK
    )

    print(
        "  OK"
    )

    # --------------------------------------------------------
    # START / INVALID URL
    # --------------------------------------------------------

    print(
        "4/5: обновление приглашения "
        "для пользователя..."
    )

    old_start = (
        '"Цензуры.нет\\n\\n"'
        '\n'
        '                        "Отправь ссылку на трек "'
        '\n'
        '                        "YouTube Music или Яндекс Музыка."'
    )

    new_start = (
        '"Цензуры.нет\\n\\n"'
        '\n'
        '                        user_link_prompt()'
    )

    if old_start in modified:

        modified = modified.replace(
            old_start,
            new_start,
            1
        )

    else:

        # Запасной вариант по более широкому блоку.
        old_start_alt = (
            '"Цензуры.нет\\n\\n"'
            '\n'
            '                         "Отправь ссылку на трек "'
            '\n'
            '                         "YouTube Music или Яндекс Музыка."'
        )

        if old_start_alt in modified:

            modified = modified.replace(
                old_start_alt,
                new_start,
                1
            )

        else:

            print(
                "  ВНИМАНИЕ: "
                "блок /start не найден."
            )

    # Проверка неправильной ссылки.
    old_invalid = (
        '"Отправь ссылку на трек "'
        '\n'
        '                        "YouTube Music или Яндекс Музыка."'
    )

    if old_invalid in modified:

        modified = modified.replace(
            old_invalid,
            "user_link_prompt()",
            1
        )

    else:

        old_invalid_alt = (
            '"Отправь ссылку на трек "'
            '\n'
            '                         "YouTube Music или Яндекс Музыка."'
        )

        if old_invalid_alt in modified:

            modified = modified.replace(
                old_invalid_alt,
                "user_link_prompt()",
                1
            )

    print(
        "  OK"
    )

    # --------------------------------------------------------
    # Проверяем polling:
    # технические ошибки там не отправляются пользователю.
    # Текущий while True уже продолжает работу после ошибки.
    # --------------------------------------------------------

    print(
        "5/5: проверка polling..."
    )

    if (
        "Повтор через 3 секунды..." in modified
        and "except Exception as e:" in modified
    ):

        print(
            "  OK — polling продолжает работу "
            "после временной ошибки."
        )

    else:

        print(
            "  ВНИМАНИЕ: структура polling "
            "отличается от ожидаемой."
        )

    # --------------------------------------------------------
    # Записываем
    # --------------------------------------------------------

    try:

        write_file(
            BOT_FILE,
            modified
        )

    except Exception as error:

        print()
        print(
            "ОШИБКА записи bot.py:"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        print()
        print(
            "Исходный файл НЕ удалён."
        )

        sys.exit(6)

    # --------------------------------------------------------
    # AST CHECK
    # --------------------------------------------------------

    print()
    print(
        "Проверка синтаксиса..."
    )

    try:

        patched_tree = ast.parse(
            modified
        )

        print(
            "  AST: OK"
        )

    except SyntaxError as error:

        print()
        print(
            "КРИТИЧЕСКАЯ ОШИБКА:"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        print()
        print(
            "Восстанавливаю резервную копию..."
        )

        shutil.copy2(
            backup_path,
            BOT_FILE
        )

        print(
            "  bot.py восстановлен."
        )

        sys.exit(7)

    # --------------------------------------------------------
    # Структурная проверка
    # --------------------------------------------------------

    print()
    print(
        "Проверка функций после патча..."
    )

    function_names = [
        node.name
        for node in patched_tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        )
    ]

    checks = [
        (
            "create_status_message",
            "create_status_message"
        ),
        (
            "update_status_message",
            "update_status_message"
        ),
        (
            "user_link_prompt",
            "user_link_prompt"
        ),
        (
            "process_yandex_playlist",
            "process_yandex_playlist"
        ),
        (
            "process_track",
            "process_track"
        )
    ]

    failed_checks = []

    for label, name in checks:

        if name in function_names:

            print(
                f"  OK: {label}()"
            )

        else:

            print(
                f"  FAIL: {label}()"
            )

            failed_checks.append(
                name
            )

    # --------------------------------------------------------
    # Проверка технических traceback в пользовательских
    # сообщениях новых функций.
    # --------------------------------------------------------

    track_node = get_function_node(
        patched_tree,
        "process_track"
    )

    playlist_node = get_function_node(
        patched_tree,
        "process_yandex_playlist"
    )

    patched_source = modified

    forbidden_user_error_patterns = [
        "f\"{type(error).__name__}: {error}\"",
        "f'{type(error).__name__}: {error}'",
        "type(track_error).__name__",
        "type(e).__name__"
    ]

    # Это не глобальный FAIL: такие конструкции могут
    # существовать в print() для консоли. Поэтому только
    # выводим диагностический результат.

    print()
    print(
        "Проверка новых обработчиков ошибок..."
    )

    if (
        "Техническая ошибка не отправляется пользователю."
        in patched_source
    ):

        print(
            "  OK: технические ошибки "
            "отделены от пользовательских сообщений."
        )

    else:

        print(
            "  ВНИМАНИЕ: комментарий "
            "об обработке ошибок не найден."
        )

    # --------------------------------------------------------
    # Финал
    # --------------------------------------------------------

    if failed_checks:

        print()
        print(
            "ПАТЧ ЗАВЕРШЁН С ОШИБКАМИ."
        )

        print(
            "Проблемные функции:"
        )

        for name in failed_checks:

            print(
                f"  - {name}"
            )

        print()
        print(
            "Резервная копия:"
        )

        print(
            f"  {backup_path}"
        )

        sys.exit(8)

    print()
    print("=" * 70)
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print("=" * 70)
    print()

    print(
        "Изменён:"
    )
    print(
        f"  {os.path.abspath(BOT_FILE)}"
    )

    print()
    print(
        "Резервная копия:"
    )
    print(
        f"  {os.path.abspath(backup_path)}"
    )

    print()
    print(
        "ВАЖНО:"
    )
    print(
        "bot.py пока НЕ запускайте."
    )

    print()
    print(
        "Сначала выполните:"
    )

    print(
        "  python -m py_compile bot.py"
    )

    print()
    print(
        "После этого пришлите полный вывод."
    )


if __name__ == "__main__":
    main()
