# -*- coding: utf-8 -*-

import json
import io
import os
import socket
import ssl
import time
import threading
from urllib.parse import urlencode


# ============================================================
# ИМПОРТ CENSURU.NET DOWNLOADER
# ============================================================

try:
    import downloader
except Exception as e:
    print("=" * 70)
    print("ОШИБКА ИМПОРТА downloader.py")
    print("=" * 70)
    print()
    print(f"{type(e).__name__}: {e}")
    raise SystemExit(1)


# ============================================================
# НАСТРОЙКИ TELEGRAM
# ============================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_HOST = "api.telegram.org"
TELEGRAM_IP = "149.154.167.220"
TELEGRAM_PORT = 443

POLL_TIMEOUT = 30

# Папка, которую использует downloader.py
TRACKS_FOLDER = downloader.TRACKS_FOLDER


# ============================================================
# ПРОВЕРКА ТОКЕНА
# ============================================================

if not BOT_TOKEN:
    print("ОШИБКА: TELEGRAM_BOT_TOKEN не установлен.")
    print()
    print("В CMD:")
    print()
    print("set TELEGRAM_BOT_TOKEN=ТВОЙ_ТОКЕН")
    raise SystemExit(1)


# ============================================================
# ИЗВЛЕЧЕНИЕ EMBEDDED COVER ИЗ MP3
# ============================================================

def extract_embedded_cover(mp3_path):

    try:
        from mutagen.id3 import ID3

        tags = ID3(mp3_path)

        pictures = tags.getall(
            "APIC"
        )

        if not pictures:

            print(
                "Telegram thumbnail: "
                "APIC в MP3 отсутствует."
            )

            return None

        picture = pictures[0]

        data = picture.data

        if not data:

            print(
                "Telegram thumbnail: "
                "APIC найден, но данные пустые."
            )

            return None

        print()
        print(
            "Telegram thumbnail: "
            f"APIC найден ({len(data):,} байт)."
        )

        # ----------------------------------------------------
        # Обработка изображения
        # ----------------------------------------------------

        try:

            from PIL import Image
            import io

            image = Image.open(
                io.BytesIO(data)
            )

            print(
                "Telegram thumbnail: "
                f"исходный размер "
                f"{image.width}x{image.height}."
            )

            # Telegram thumbnail:
            # максимум 320x320.
            image.thumbnail(
                (320, 320),
                Image.Resampling.LANCZOS
            )

            if image.mode != "RGB":

                image = image.convert(
                    "RGB"
                )

            output = io.BytesIO()

            image.save(
                output,
                format="JPEG",
                quality=90,
                optimize=True
            )

            thumbnail = output.getvalue()

            print(
                "Telegram thumbnail: "
                f"подготовлен размер "
                f"{image.width}x{image.height}, "
                f"{len(thumbnail):,} байт."
            )

            if len(thumbnail) > 200000:

                print(
                    "Telegram thumbnail: "
                    "JPEG больше 200 КБ, "
                    "уменьшаем качество."
                )

                output = io.BytesIO()

                image.save(
                    output,
                    format="JPEG",
                    quality=75,
                    optimize=True
                )

                thumbnail = output.getvalue()

            if len(thumbnail) > 200000:

                print(
                    "Telegram thumbnail: "
                    "не удалось уложиться в 200 КБ."
                )

                return None

            return thumbnail

        except Exception as e:

            print(
                "Telegram thumbnail: "
                "ошибка обработки изображения:"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            return None

    except Exception as e:

        print(
            "Telegram thumbnail: "
            "не удалось извлечь APIC:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        return None



# ============================================================
# TELEGRAM API
# ============================================================

def telegram_request(method, params=None):

    if params is None:
        params = {}

    path = f"/bot{BOT_TOKEN}/{method}"

    if params:
        query = urlencode(
            params,
            encoding="utf-8"
        )

        path += "?" + query

    sock = socket.create_connection(
        (TELEGRAM_IP, TELEGRAM_PORT),
        timeout=POLL_TIMEOUT + 10
    )

    context = ssl.create_default_context()

    tls_sock = context.wrap_socket(
        sock,
        server_hostname=TELEGRAM_HOST
    )

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {TELEGRAM_HOST}\r\n"
        f"User-Agent: CENSURU.NET-Bot/1.0\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    tls_sock.sendall(
        request.encode("ascii")
    )

    response = b""

    while True:

        chunk = tls_sock.recv(8192)

        if not chunk:
            break

        response += chunk

    tls_sock.close()

    if b"\r\n\r\n" not in response:
        raise RuntimeError(
            "Telegram вернул некорректный HTTP-ответ."
        )

    header, body = response.split(
        b"\r\n\r\n",
        1
    )

    return json.loads(
        body.decode(
            "utf-8",
            errors="replace"
        )
    )


# ============================================================
# TELEGRAM HELPERS
# ============================================================

# ============================================================
# STATUS MESSAGE STATE
# ============================================================

_STATUS_MESSAGES = {}
_STATUS_LOCK = threading.Lock()

def send_message(chat_id, text):

    # --------------------------------------------------------
    # Обычные пользовательские сообщения.
    #
    # Если сообщение содержит техническое исключение,
    # не показываем его пользователю.
    # Ошибка остаётся только в консоли.
    # --------------------------------------------------------

    technical_error_patterns = (
        "TimeoutError:",
        "ConnectionError:",
        "ConnectionResetError:",
        "ConnectionAbortedError:",
        "ConnectionRefusedError:",
        "socket.timeout",
        "WinError 10060",
        "WinError 10061",
        "WinError 10054",
        "Traceback (most recent call last)",
    )

    text_string = str(
        text or ""
    )

    if any(
        pattern in text_string
        for pattern in technical_error_patterns
    ):
        print(
            "Telegram: техническая ошибка "
            "не отправлена пользователю."
        )

        return {
            "ok": False,
            "suppressed": True
        }

    # --------------------------------------------------------
    # Статусное сообщение.
    #
    # Все последовательные сообщения обработки одного чата
    # редактируют одно и то же сообщение.
    # --------------------------------------------------------

    try:

        status_states = globals().setdefault(
            "_STATUS_MESSAGES",
            {}
        )

        status_lock = globals().get(
            "_STATUS_LOCK"
        )

        if status_lock is None:
            import threading

            status_lock = threading.Lock()

            globals()[
                "_STATUS_LOCK"
            ] = status_lock

        with status_lock:

            status_message_id = (
                status_states.get(
                    chat_id
                )
            )

            if status_message_id:

                try:

                    result = edit_message(
                        chat_id,
                        status_message_id,
                        text_string
                    )

                    if result.get("ok"):

                        return result

                except Exception as edit_error:

                    print(
                        "Telegram: не удалось "
                        "отредактировать статус:"
                    )

                    print(
                        f"{type(edit_error).__name__}: "
                        f"{edit_error}"
                    )

                    status_states.pop(
                        chat_id,
                        None
                    )

            result = telegram_request(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text_string
                }
            )

            if result.get("ok"):

                message = result.get(
                    "result",
                    {}
                )

                message_id = message.get(
                    "message_id"
                )

                if message_id:

                    status_states[
                        chat_id
                    ] = message_id

            return result

    except Exception:

        raise




def edit_message(chat_id, message_id, text):

    return telegram_request(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
    )

def telegram_upload_file(
    method,
    chat_id,
    file_path,
    field_name="audio",
    caption=None
):

    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Файл не найден: {file_path}"
        )

    filename = os.path.basename(
        file_path
    )

    with open(
        file_path,
        "rb"
    ) as f:

        file_data = f.read()

    boundary = (
        "----CENSURUNET"
        + str(int(time.time() * 1000))
    )

    body = bytearray()

    def add_text_field(name, value):

        body.extend(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; '
                f'name="{name}"\r\n'
                f"\r\n"
                f"{value}\r\n"
            ).encode("utf-8")
        )

    def add_file_field(
        name,
        filename,
        data,
        content_type
    ):

        body.extend(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; '
                f'name="{name}"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n"
                f"\r\n"
            ).encode("utf-8")
        )

        body.extend(data)

        body.extend(
            b"\r\n"
        )

    # --------------------------------------------------------
    # CHAT ID
    # --------------------------------------------------------

    add_text_field(
        "chat_id",
        str(chat_id)
    )

    # --------------------------------------------------------
    # CAPTION
    # --------------------------------------------------------

    if caption:
        add_text_field(
            "caption",
            caption
        )

    # --------------------------------------------------------
    # AUDIO
    # --------------------------------------------------------

    add_file_field(
        field_name,
        filename,
        file_data,
        "audio/mpeg"
    )

    # --------------------------------------------------------
    # THUMBNAIL
    # --------------------------------------------------------

    thumbnail_data = None

    if method == "sendAudio":

        thumbnail_data = (
            extract_embedded_cover(
                file_path
            )
        )

    if thumbnail_data:

        print(
            "Telegram thumbnail: "
            "добавляем thumbnail в multipart."
        )

        add_file_field(
            "thumbnail",
            "cover.jpg",
            thumbnail_data,
            "image/jpeg"
        )

    else:

        print(
            "Telegram thumbnail: "
            "thumbnail не добавляется."
        )

    # --------------------------------------------------------
    # END MULTIPART
    # --------------------------------------------------------

    body.extend(
        f"--{boundary}--\r\n".encode(
            "ascii"
        )
    )

    print()
    print(
        f"Telegram upload: {filename}"
    )

    print(
        f"Telegram upload: "
        f"{len(file_data):,} байт"
    )

    print(
        f"Telegram multipart: "
        f"{len(body):,} байт"
    )

    print()
    print("Telegram upload: TCP connection...")

    upload_connect_start = time.time()

    sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=120
    )

    upload_connect_elapsed = (
        time.time() - upload_connect_start
    )

    print(
        "Telegram upload: TCP connection OK "
        f"({upload_connect_elapsed:.2f} сек.)"
    )

    try:

        print(
            "Telegram upload: TLS handshake..."
        )

        tls_start = time.time()

        context = ssl.create_default_context()

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )
        tls_sock.settimeout(180)

        tls_elapsed = (
            time.time() - tls_start
        )

        print(
            "Telegram upload: TLS OK "
            f"({tls_elapsed:.2f} сек.)"
        )
        print(
            "Telegram upload: socket timeout = 180 сек."
        )

        try:

            path = (
                f"/bot{BOT_TOKEN}/{method}"
            )

            request = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: {TELEGRAM_HOST}\r\n"
                f"User-Agent: CENSURU.NET-Bot/1.0\r\n"
                f"Content-Type: multipart/form-data; "
                f"boundary={boundary}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode("ascii")

            start_time = time.time()

            print(
                "Telegram upload: "
                "отправка HTTP headers..."
            )

            headers_start = time.time()

            tls_sock.sendall(
                request
            )

            headers_elapsed = (
                time.time() - headers_start
            )

            print(
                "Telegram upload: "
                "HTTP headers отправлены "
                f"({headers_elapsed:.2f} сек.)"
            )

            print(
                "Telegram upload: "
                "отправка multipart/MP3..."
            )

            body_start = time.time()

            tls_sock.sendall(
                body
            )

            body_elapsed = (
                time.time() - body_start
            )

            print(
                "Telegram upload: "
                "multipart/MP3 отправлен "
                f"({body_elapsed:.2f} сек.)"
            )

            elapsed = (
                time.time() - start_time
            )

            print(
                f"Telegram upload: "
                f"отправлено за {elapsed:.2f} сек."
            )

            response = b""

            print(
                "Telegram upload: "
                "ожидание HTTP-ответа Telegram..."
            )

            recv_start = time.time()

            while True:

                chunk = tls_sock.recv(
                    8192
                )

                if not chunk:
                    break

                response += chunk

                print(
                    "Telegram upload: "
                    f"получено ещё {len(chunk):,} байт."
                )

            recv_elapsed = (
                time.time() - recv_start
            )

            print(
                "Telegram upload: "
                f"HTTP response получен "
                f"({recv_elapsed:.2f} сек., "
                f"{len(response):,} байт)"
            )

        finally:

            tls_sock.close()

    except Exception:

        try:
            sock.close()
        except Exception:
            pass

        raise

    if b"\r\n\r\n" not in response:

        raise RuntimeError(
            "Telegram вернул некорректный HTTP-ответ."
        )

    header, response_body = response.split(
        b"\r\n\r\n",
        1
    )

    result = json.loads(
        response_body.decode(
            "utf-8",
            errors="replace"
        )
    )

    if not result.get("ok"):

        print()
        print(
            "Telegram upload ERROR:"
        )

        print(
            result
        )

    else:

        telegram_result = result.get(
            "result",
            {}
        )

        audio = telegram_result.get(
            "audio",
            {}
        )

        if method == "sendAudio":

            if "thumbnail" in audio:

                print()
                print(
                    "Telegram: THUMBNAIL "
                    "ПОЛУЧЕН В ОТВЕТЕ API."
                )

            else:

                print()
                print(
                    "Telegram: thumbnail "
                    "отсутствует в ответе API."
                )

    return result


def send_audio(
    chat_id,
    file_path,
    caption=None
):

    return telegram_upload_file(
        "sendAudio",
        chat_id,
        file_path,
        field_name="audio",
        caption=caption
    )


def send_document(
    chat_id,
    file_path
):

    return telegram_upload_file(
        "sendDocument",
        chat_id,
        file_path,
        field_name="document"
    )


def get_updates(offset=None):

    params = {
        "timeout": POLL_TIMEOUT
    }

    if offset is not None:
        params["offset"] = offset

    return telegram_request(
        "getUpdates",
        params
    )


# ============================================================
# ОБРАБОТКА ТРЕКА
# ============================================================


# ============================================================
# ОБРАБОТКА ПЛЕЙЛИСТА ЯНДЕКС МУЗЫКИ
# ============================================================

def process_yandex_playlist(chat_id, url):

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


def process_track(chat_id, url, playlist_progress=None):

    try:

        # ----------------------------------------------------
        # Новая одиночная ссылка должна получить новое
        # редактируемое статусное сообщение.
        #
        # Для трека внутри плейлиста существующее сообщение
        # сохраняем.
        # ----------------------------------------------------

        if not playlist_progress:

            globals().get(
                "_STATUS_MESSAGES",
                {}
            ).pop(
                chat_id,
                None
            )

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

# ============================================================
# START
# ============================================================

print("=" * 70)
print("CENSURU.NET — TELEGRAM BOT")
print("=" * 70)

print()
print(f"Bot API IP: {TELEGRAM_IP}")
print(f"Host/SNI:   {TELEGRAM_HOST}")
print()
print(f"TRACKS_FOLDER:")
print(f"  {TRACKS_FOLDER}")
print()

print("downloader.py: OK")


# ============================================================
# ПРОВЕРКА BOT API
# ============================================================

print()
print("Проверка Bot API...")

try:

    result = telegram_request(
        "getMe"
    )

    if not result.get("ok"):

        print("ОШИБКА Telegram API:")
        print(result)

        raise SystemExit(2)

    bot = result["result"]

    print()
    print("Bot API: OK")
    print(
        f"Бот: @{bot.get('username')}"
    )

except Exception as e:

    print()
    print("ОШИБКА подключения к Telegram:")
    print(
        f"{type(e).__name__}: {e}"
    )

    raise SystemExit(3)


# ============================================================
# LONG POLLING
# ============================================================

print()
print("-" * 70)
print("БОТ ЗАПУЩЕН")
print("-" * 70)

print()
print("Поддерживаемый ввод:")
print("  YouTube Music")
print("  Яндекс Музыка")
print()
print("Для остановки нажми Ctrl+C.")
print()


offset = None


while True:

    try:

        response = get_updates(
            offset
        )

        if not response.get("ok"):

            print(
                "Ошибка getUpdates:",
                response
            )

            time.sleep(3)
            continue

        updates = response.get(
            "result",
            []
        )

        for update in updates:

            offset = (
                update["update_id"] + 1
            )

            message = update.get(
                "message"
            )

            if not message:
                continue

            chat = message.get(
                "chat",
                {}
            )

            chat_id = chat.get(
                "id"
            )

            text = message.get(
                "text",
                ""
            ).strip()

            if not chat_id:
                continue

            print()
            print(
                f"[MESSAGE] {chat_id}: {text}"
            )

            # ------------------------------------------------
            # START
            # ------------------------------------------------

            if text == "/start":

                send_message(
                    chat_id,
                    (
                        "Цензуры.нет\n\n"
                        "Отправь ссылку на трек "
                        "YouTube Music или Яндекс Музыка."
                    )
                )

                continue

            # ------------------------------------------------
            # Проверка ссылки
            # ------------------------------------------------

            is_youtube = (
                "youtube.com" in text
                or "youtu.be" in text
            )

            is_yandex = (
                "music.yandex.ru" in text
                or "music.yandex.com" in text
            )

            if not is_youtube and not is_yandex:

                send_message(
                    chat_id,
                    (
                        "Отправь ссылку на трек "
                        "YouTube Music или Яндекс Музыка."
                    )
                )

                continue

            # ------------------------------------------------
            # Определяем: одиночный трек или плейлист
            # ------------------------------------------------

            if downloader.is_playlist_url(text):

                print()
                print(
                    "Обнаружен плейлист."
                )

                if downloader.is_yandex_music_url(text):

                    print(
                        "Источник плейлиста: "
                        "Яндекс Музыка"
                    )

                    thread = threading.Thread(
                        target=process_yandex_playlist,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )

                else:

                    print(
                        "Источник плейлиста: "
                        "YouTube Music"
                    )

                    # Текущую обработку YouTube-плейлистов
                    # пока не меняем.
                    thread = threading.Thread(
                        target=process_youtube_playlist,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )

            else:

                thread = threading.Thread(
                    target=process_track,
                    args=(
                        chat_id,
                        text
                    ),
                    daemon=True
                )

            thread.start()

    except KeyboardInterrupt:

        print()
        print("Бот остановлен.")
        break

    except Exception as e:

        print()
        print(
            "Ошибка polling:",
            f"{type(e).__name__}: {e}"
        )

        print(
            "Повтор через 3 секунды..."
        )

        time.sleep(3)
