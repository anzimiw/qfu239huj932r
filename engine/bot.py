# -*- coding: utf-8 -*-

import telegram_queue

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

def _telegram_request_now(method, params=None):

    # ========================================================
    # TELEGRAM API NETWORK CONTROL V2
    #
    # Обычные API-запросы:
    #   TCP/TLS/HTTP timeout = 5 секунд
    #   максимум 2 попытки
    #   пауза между попытками = 0.5 сек.
    #
    # getUpdates:
    #   используется длинный POLL_TIMEOUT.
    #
    # Важно:
    #   timeout устанавливается не только на TCP connect,
    #   но и на уже созданные TCP/TLS sockets.
    #
    # Поэтому зависший TLS/HTTP recv() также не может
    # блокировать бота бесконечно.
    # ========================================================

    if params is None:
        params = {}

    path = f"/bot{BOT_TOKEN}/{method}"

    if params:
        query = urlencode(
            params,
            encoding="utf-8"
        )

        path += "?" + query

    if method == "getUpdates":
        telegram_api_retries = 3
        telegram_api_retry_delay = 3
        telegram_api_timeout = POLL_TIMEOUT + 10

    else:
        telegram_api_retries = 2
        telegram_api_retry_delay = 0.5
        telegram_api_timeout = 5

    last_error = None

    for attempt in range(
        1,
        telegram_api_retries + 1
    ):

        sock = None
        tls_sock = None

        try:

            if attempt > 1:

                print(
                    "Telegram API: повтор запроса "
                    f"{attempt}/{telegram_api_retries} "
                    f"через {telegram_api_retry_delay} сек."
                )

                time.sleep(
                    telegram_api_retry_delay
                )

            print(
                "Telegram API: TCP connection "
                f"attempt {attempt}/{telegram_api_retries}..."
            )

            # ------------------------------------------------
            # TCP CONNECT
            # ------------------------------------------------

            try:

                sock = socket.create_connection(
                    (
                        TELEGRAM_IP,
                        TELEGRAM_PORT
                    ),
                    timeout=telegram_api_timeout
                )

                # Важно:
                # timeout сохраняется и после установления TCP.
                sock.settimeout(
                    telegram_api_timeout
                )

                print(
                    "Telegram API: TCP connection OK."
                )

            except (
                TimeoutError,
                socket.timeout,
                ConnectionError,
                ConnectionResetError,
                ConnectionAbortedError,
                ConnectionRefusedError,
                OSError,
            ) as error:

                print(
                    "Telegram API: TCP connection failed:"
                )

                print(
                    f"{type(error).__name__}: {error}"
                )

                raise

            # ------------------------------------------------
            # TLS HANDSHAKE
            # ------------------------------------------------

            print(
                "Telegram API: TLS handshake..."
            )

            context = ssl.create_default_context()

            try:

                tls_sock = context.wrap_socket(
                    sock,
                    server_hostname=TELEGRAM_HOST
                )

                # Важно:
                # после TLS handshake timeout также сохраняется.
                tls_sock.settimeout(
                    telegram_api_timeout
                )

                print(
                    "Telegram API: TLS OK."
                )

            except (
                TimeoutError,
                socket.timeout,
                ConnectionError,
                ConnectionResetError,
                ConnectionAbortedError,
                ConnectionRefusedError,
                OSError,
            ) as error:

                print(
                    "Telegram API: TLS connection failed:"
                )

                print(
                    f"{type(error).__name__}: {error}"
                )

                raise

            # ------------------------------------------------
            # HTTP REQUEST
            # ------------------------------------------------

            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {TELEGRAM_HOST}\r\n"
                f"User-Agent: CENSURU.NET-Bot/1.0\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )

            print(
                "Telegram API: sending HTTP request..."
            )

            try:

                tls_sock.sendall(
                    request.encode("ascii")
                )

            except (
                TimeoutError,
                socket.timeout,
                ConnectionError,
                ConnectionResetError,
                ConnectionAbortedError,
                ConnectionRefusedError,
                OSError,
            ) as error:

                print(
                    "Telegram API: HTTP send failed:"
                )

                print(
                    f"{type(error).__name__}: {error}"
                )

                raise

            # ------------------------------------------------
            # HTTP RESPONSE
            # ------------------------------------------------

            print(
                "Telegram API: waiting for response..."
            )

            response = b""

            try:

                while True:

                    chunk = tls_sock.recv(
                        8192
                    )

                    if not chunk:
                        break

                    response += chunk

            except (
                TimeoutError,
                socket.timeout,
                ConnectionError,
                ConnectionResetError,
                ConnectionAbortedError,
                ConnectionRefusedError,
                OSError,
            ) as error:

                print(
                    "Telegram API: HTTP receive failed:"
                )

                print(
                    f"{type(error).__name__}: {error}"
                )

                raise

            if b"\r\n\r\n" not in response:

                raise RuntimeError(
                    "Telegram вернул "
                    "некорректный HTTP-ответ."
                )

            header, body = response.split(
                b"\r\n\r\n",
                1
            )

            result = json.loads(
                body.decode(
                    "utf-8",
                    errors="replace"
                )
            )

            print(
                "Telegram API: запрос успешен."
            )

            return result

        except (
            TimeoutError,
            socket.timeout,
            ConnectionError,
            ConnectionResetError,
            ConnectionAbortedError,
            ConnectionRefusedError,
            OSError,
        ) as error:

            last_error = error

            error_text = str(error)

            # ------------------------------------------------
            # Windows error diagnostics
            # ------------------------------------------------

            win_error = getattr(
                error,
                "winerror",
                None
            )

            if win_error is not None:

                error_label = (
                    f"WinError {win_error}"
                )

            else:

                error_label = (
                    f"{type(error).__name__}"
                )

            print()

            print(
                "Telegram API: сетевой сбой "
                f"на попытке {attempt}/"
                f"{telegram_api_retries}:"
            )

            print(
                f"{error_label}: {error_text}"
            )

            # ------------------------------------------------
            # WINERROR 10051
            #
            # Windows сообщает, что сеть/маршрут
            # временно недоступны.
            #
            # Бессмысленно делать длинные retries:
            # следующая попытка всё равно может сразу
            # получить тот же локальный сетевой сбой.
            #
            # Для последней попытки ошибка всё равно
            # будет выброшена ниже.
            # ------------------------------------------------

            if (
                win_error == 10051
                and attempt < telegram_api_retries
            ):

                print(
                    "Telegram API: Windows сообщает "
                    "об отсутствии сетевого маршрута."
                )

                print(
                    "Telegram API: следующая попытка "
                    "будет выполнена без увеличения timeout."
                )

            if attempt >= telegram_api_retries:

                raise

        except Exception:

            raise

        finally:

            if tls_sock is not None:

                try:

                    tls_sock.close()

                except Exception:

                    pass

            elif sock is not None:

                try:

                    sock.close()

                except Exception:

                    pass

    if last_error is not None:

        raise last_error

    raise RuntimeError(
        "Telegram API: запрос завершился "
        "без результата."
    )
# ============================================================
# TELEGRAM HELPERS
# ============================================================

# ============================================================
# STATUS MESSAGE STATE
# ============================================================

_STATUS_MESSAGES = {}

# Ожидающие выбора режима загрузки.
#
# Формат:
# {
#     chat_id: {
#         "url": "...",
#         "kind": "track" | "yandex_playlist" | "youtube_playlist"
#     }
# }
_PENDING_DOWNLOADS = {}

_STATUS_LOCK = threading.Lock()



def telegram_request(method, params=None):
    """
    Очередь исходящих Telegram API-запросов.

    getUpdates сюда не попадает:
    он вызывается напрямую из get_updates().
    """

    if method == "getUpdates":
        return _telegram_request_now(
            method,
            params
        )

    return telegram_queue.enqueue(
        "API:" + str(method),
        _telegram_request_now,
        method,
        params
    )


def edit_message(chat_id, message_id, text):

    return telegram_request(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
    )



def send_download_mode_menu(chat_id, url, kind):
    """
    Показывает пользователю четыре режима загрузки.

    kind:
      track
      yandex_playlist
      youtube_playlist
    """

    _PENDING_DOWNLOADS[chat_id] = {
        "url": url,
        "kind": kind
    }

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Обычный + LRC",
                    "callback_data": "mode:normal:1"
                },
                {
                    "text": "Обычный без LRC",
                    "callback_data": "mode:normal:0"
                }
            ],
            [
                {
                    "text": "Без цензуры + LRC",
                    "callback_data": "mode:uncensored:1"
                },
                {
                    "text": "Без цензуры без LRC",
                    "callback_data": "mode:uncensored:0"
                }
            ]
        ]
    }

    result = telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "Выберите режим скачивания:\n\n"
                "Обычный режим — YouTube / Yandex → YouTube fallback.\n"
                "Без цензуры — SoundCloud → MP3Party → MP3TM → AudioStart.\n\n"
                "LRC можно включить или отключить отдельно."
            ),
            "reply_markup": json.dumps(
                keyboard,
                ensure_ascii=False,
                separators=(",", ":")
            )
        }
    )

    if not result.get("ok"):
        print(
            "Ошибка отправки меню режима:",
            result
        )

    return result


def answer_callback_query(callback_query_id):
    return telegram_request(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_query_id
        }
    )


def start_download_request(
    chat_id,
    url,
    kind,
    mode,
    with_lrc
):
    print()
    print("=" * 70)
    print("ЗАПУСК ЗАПРОСА ПОСЛЕ ВЫБОРА РЕЖИМА")
    print("=" * 70)
    print()
    print(f"Тип: {kind}")
    print(f"Режим: {mode}")
    print(f"LRC: {with_lrc}")
    print(f"URL: {url}")

    if kind == "track":
        thread = threading.Thread(
            target=process_track,
            args=(
                chat_id,
                url
            ),
            kwargs={
                "mode": mode,
                "with_lrc": with_lrc
            },
            daemon=True
        )

    elif kind == "yandex_playlist":
        thread = threading.Thread(
            target=process_yandex_playlist,
            args=(
                chat_id,
                url
            ),
            kwargs={
                "mode": mode,
                "with_lrc": with_lrc
            },
            daemon=True
        )

    elif kind == "youtube_playlist":
        thread = threading.Thread(
            target=process_youtube_playlist,
            args=(
                chat_id,
                url
            ),
            kwargs={
                "mode": mode,
                "with_lrc": with_lrc
            },
            daemon=True
        )

    else:
        raise ValueError(
            f"Неизвестный тип запроса: {kind}"
        )

    thread.start()

def send_message(chat_id, text):

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

    try:

        status_states = globals().setdefault(
            "_STATUS_MESSAGES",
            {}
        )

        status_lock = globals().get(
            "_STATUS_LOCK"
        )

        if status_lock is None:

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


def _telegram_upload_file_now(
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

    # --------------------------------------------------------
    # TCP CONNECTION WITH RETRIES
    # --------------------------------------------------------

    TCP_CONNECT_ATTEMPTS = 3
    TCP_CONNECT_TIMEOUT = 120
    TCP_CONNECT_RETRY_DELAY = 3

    sock = None
    last_connect_error = None

    for connect_attempt in range(
        1,
        TCP_CONNECT_ATTEMPTS + 1
    ):

        try:

            print(
                "Telegram upload: TCP connection "
                f"attempt {connect_attempt}/"
                f"{TCP_CONNECT_ATTEMPTS}..."
            )

            attempt_start = time.time()

            sock = socket.create_connection(
                (
                    TELEGRAM_IP,
                    TELEGRAM_PORT
                ),
                timeout=TCP_CONNECT_TIMEOUT
            )

            upload_connect_elapsed = (
                time.time() - upload_connect_start
            )

            print(
                "Telegram upload: TCP connection OK "
                f"({upload_connect_elapsed:.2f} сек.)"
            )

            break

        except OSError as error:

            last_connect_error = error

            print(
                "Telegram upload: TCP connection "
                f"attempt {connect_attempt}/"
                f"{TCP_CONNECT_ATTEMPTS} failed:"
            )

            print(
                f"{type(error).__name__}: {error}"
            )

            if sock is not None:

                try:
                    sock.close()
                except Exception:
                    pass

                sock = None

            if (
                connect_attempt
                < TCP_CONNECT_ATTEMPTS
            ):

                print(
                    "Telegram upload: повтор TCP "
                    f"через {TCP_CONNECT_RETRY_DELAY} сек."
                )

                time.sleep(
                    TCP_CONNECT_RETRY_DELAY
                )


    if sock is None:

        if last_connect_error is not None:
            raise last_connect_error

        raise RuntimeError(
            "Telegram upload: "
            "TCP connection не установлено."
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
        tls_sock.settimeout(260)

        tls_elapsed = (
            time.time() - tls_start
        )

        print(
            "Telegram upload: TLS OK "
            f"({tls_elapsed:.2f} сек.)"
        )
        print(
            "Telegram upload: socket timeout = 260 сек."
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



def telegram_upload_file(
    method,
    chat_id,
    file_path,
    field_name="audio",
    caption=None
):
    """
    Очередь загрузки файлов.

    Реальный TCP/TLS/upload выполняется
    отдельным Telegram queue worker.
    """

    return telegram_queue.enqueue(
        "UPLOAD:" + str(method),
        _telegram_upload_file_now,
        method,
        chat_id,
        file_path,
        field_name,
        caption
    )


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

    return _telegram_request_now(
        "getUpdates",
        params
    )


# ============================================================
# ОБРАБОТКА ТРЕКА
# ============================================================


# ============================================================
# ОБРАБОТКА ПЛЕЙЛИСТА ЯНДЕКС МУЗЫКИ
# ============================================================

def process_yandex_playlist(
    chat_id,
    url,
    mode="uncensored",
    with_lrc=None
):

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
                    ),
                    mode=mode,
                    with_lrc=with_lrc
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

def process_youtube_playlist(
    chat_id,
    url,
    mode="uncensored",
    with_lrc=None
):

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
                    ),
                    mode=mode,
                    with_lrc=with_lrc
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


def process_track(
    chat_id,
    url,
    playlist_progress=None,
    mode="uncensored",
    with_lrc=None
):

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
        #
        # БЫСТРЫЙ ПУТЬ:
        #
        # YouTube + normal:
        #     metadata НЕ получаем.
        #     Сразу передаём исходный URL в downloader.py.
        #
        # Yandex + normal:
        #     metadata получаем, потому что они нужны
        #     для поиска соответствующего YouTube-трека.
        #
        # uncensored:
        #     metadata получаем всегда.
        # ----------------------------------------------------

        fast_youtube_normal = (
            mode == "normal"
            and downloader.is_youtube_music_url(url)
            and not downloader.is_yandex_music_url(url)
        )

        if fast_youtube_normal:

            print()
            print(
                "БЫСТРЫЙ ПУТЬ YOUTUBE."
            )
            print(
                "Метаданные YouTube "
                "перед скачиванием НЕ получаются."
            )

            info = {
                "artist": "",
                "title": "",
                "duration": 0,
                "album": "",
                "cover_url": None,
                "source": "youtube",
                "youtube_age_restricted": False,
                "fast_youtube": True
            }

        elif downloader.is_yandex_music_url(url):

            print()
            print(
                "Источник: Яндекс Музыка"
            )
            print(
                "Получение информации "
                "из Яндекс Музыки..."
            )

            info = downloader.get_yandex_music_info(
                url
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

        if (
            not info.get("fast_youtube", False)
            and (
                not artist
                or not title
                or not duration
            )
        ):

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

        # ----------------------------------------------------
        # 3. Выбор пути скачивания
        # ----------------------------------------------------

        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "Запуск YouTube Fast..."
            )

            filename = (
                f"{downloader.safe_filename(url.split('/')[-1])}.mp3"
            )

            # Имя файла здесь нельзя строить из metadata:
            # metadata специально НЕ получались.
            #
            # downloader.py сам определяет корректное имя
            # непосредственно из URL только после успешного
            # скачивания.

            result = downloader.download_youtube_fast_direct(
                url,
                TRACKS_FOLDER
            )

        else:

            result = downloader.find_and_download_track(
                artist,
                title,
                duration,
                TRACKS_FOLDER,
                url,
                source,
                youtube_age_restricted,
                mode=mode
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

        # ----------------------------------------------------
        # YOUTUBE FAST POST-PROCESSING
        #
        # В Fast-пути metadata до скачивания НЕ получаются.
        #
        # После успешного скачивания получаем metadata,
        # необходимые для дальнейшей обработки:
        #
        #   artist
        #   title
        #   duration
        #   album
        #   cover_url
        #
        # Затем используется существующая обработка:
        #
        #   embed_cover()
        #   process_lrc()
        #
        # ----------------------------------------------------

        if info.get(
            "fast_youtube",
            False
        ):

            print()
            print(
                "YouTube Fast: "
                "получение metadata "
                "ПОСЛЕ скачивания..."
            )

            post_info = (
                downloader.get_youtube_music_info(
                    url
                )
            )

            if post_info:

                print(
                    "YouTube Fast: "
                    "metadata получены."
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
                    f"YouTube Fast: "
                    f"artist = {artist}"
                )

                print(
                    f"YouTube Fast: "
                    f"title = {title}"
                )

                print(
                    f"YouTube Fast: "
                    f"duration = {duration}"
                )

                print(
                    "YouTube Fast: cover = "
                    + (
                        "найдена"
                        if info.get("cover_url")
                        else "не найдена"
                    )
                )

                # ------------------------------------------------
                # Переименование MP3.
                #
                # Это выполняется ДО process_lrc(),
                # чтобы имя LRC совпадало с MP3.
                # ------------------------------------------------

                if artist and title:

                    safe_artist = (
                        downloader.safe_filename(
                            artist
                        )
                    )

                    safe_title = (
                        downloader.safe_filename(
                            title
                        )
                    )

                    normal_name = (
                        f"{safe_artist} - "
                        f"{safe_title}.mp3"
                    )

                    normal_path = os.path.join(
                        TRACKS_FOLDER,
                        normal_name
                    )

                    normal_path = os.path.abspath(
                        normal_path
                    )

                    current_path = os.path.abspath(
                        file_path
                    )

                    if (
                        normal_path
                        != current_path
                    ):

                        if os.path.exists(
                            normal_path
                        ):

                            base_name = (
                                f"{safe_artist} - "
                                f"{safe_title}"
                            )

                            counter = 1

                            while True:

                                candidate = os.path.join(
                                    TRACKS_FOLDER,
                                    (
                                        f"{base_name} "
                                        f"({counter}).mp3"
                                    )
                                )

                                if not os.path.exists(
                                    candidate
                                ):

                                    normal_path = (
                                        candidate
                                    )

                                    break

                                counter += 1

                        try:

                            os.replace(
                                file_path,
                                normal_path
                            )

                            file_path = normal_path

                            print()
                            print(
                                "YouTube Fast: "
                                "MP3 переименован:"
                            )

                            print(
                                f"  {file_path}"
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

            else:

                print()
                print(
                    "YouTube Fast: "
                    "metadata после скачивания "
                    "получить не удалось."
                )

                print(
                    "Продолжаю обработку "
                    "скачанного MP3."
                )

        print()
        print("Добавление обложки в MP3...")

        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )

        effective_with_lrc = (
            downloader.DOWNLOAD_LRC
            if with_lrc is None
            else bool(with_lrc)
        )

        print(
            "LRC: "
            f"{'ВКЛЮЧЕН' if effective_with_lrc else 'ОТКЛЮЧЕН'}"
        )

        if effective_with_lrc:
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

            # ------------------------------------------------
            # Отправка LRC-файла
            # ------------------------------------------------
            #
            # LRC имеет то же имя, что и MP3:
            #
            #   Artist - Title.mp3
            #   Artist - Title.lrc
            #
            # Никаких промежуточных сообщений пользователю
            # между MP3 и LRC не отправляем.
            # ------------------------------------------------

            lrc_path = (
                os.path.splitext(file_path)[0]
                + ".lrc"
            )

            if os.path.isfile(lrc_path):

                print()
                print(
                    "LRC-файл найден:"
                )
                print(
                    f"  {lrc_path}"
                )

                lrc_size = os.path.getsize(
                    lrc_path
                )

                print(
                    f"  Размер: {lrc_size:,} байт"
                )

                print()
                print(
                    "Отправка LRC в Telegram..."
                )

                lrc_result = send_document(
                    chat_id,
                    lrc_path
                )

                if lrc_result.get("ok"):

                    print(
                        "LRC успешно отправлен в Telegram."
                    )

                else:

                    print(
                        "Ошибка отправки LRC:"
                    )

                    print(
                        lrc_result
                    )

            else:

                print()
                print(
                    "LRC-файл не найден."
                )
                print(
                    f"Ожидался: {lrc_path}"
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



# Telegram outgoing queue worker
telegram_queue.start()

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

            # ------------------------------------------------
            # CALLBACK: выбор режима скачивания
            # ------------------------------------------------

            callback_query = update.get(
                "callback_query"
            )

            if callback_query:
                callback_id = callback_query.get(
                    "id"
                )

                callback_data = callback_query.get(
                    "data",
                    ""
                )

                callback_message = callback_query.get(
                    "message",
                    {}
                )

                callback_chat = callback_message.get(
                    "chat",
                    {}
                )

                callback_chat_id = callback_chat.get(
                    "id"
                )

                print()
                print(
                    "[CALLBACK]",
                    callback_chat_id,
                    callback_data
                )

                if callback_id:
                    try:
                        answer_callback_query(
                            callback_id
                        )
                    except Exception as callback_error:
                        print(
                            "Ошибка answerCallbackQuery:",
                            callback_error
                        )

                if (
                    callback_chat_id
                    and callback_data.startswith(
                        "mode:"
                    )
                ):
                    parts = callback_data.split(
                        ":"
                    )

                    if len(parts) == 3:
                        selected_mode = parts[1]
                        selected_lrc = (
                            parts[2] == "1"
                        )

                        if selected_mode not in (
                            "normal",
                            "uncensored"
                        ):
                            print(
                                "ОШИБКА: неизвестный mode:",
                                selected_mode
                            )
                            continue

                        pending = _PENDING_DOWNLOADS.pop(
                            callback_chat_id,
                            None
                        )

                        if not pending:
                            send_message(
                                callback_chat_id,
                                "Запрос устарел. Отправьте ссылку заново."
                            )
                            continue

                        pending_url = pending["url"]
                        pending_kind = pending["kind"]

                        send_message(
                            callback_chat_id,
                            (
                                "Режим выбран.\n\n"
                                f"Режим: "
                                f"{'обычный' if selected_mode == 'normal' else 'без цензуры'}\n"
                                f"LRC: "
                                f"{'включён' if selected_lrc else 'выключен'}\n\n"
                                "Начинаю обработку..."
                            )
                        )

                        start_download_request(
                            callback_chat_id,
                            pending_url,
                            pending_kind,
                            selected_mode,
                            selected_lrc
                        )

                        continue

                continue

            # ------------------------------------------------
            # MESSAGE
            # ------------------------------------------------

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
                        "или плейлист YouTube Music / Яндекс Музыка."
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

                    send_download_mode_menu(
                        chat_id,
                        text,
                        "yandex_playlist"
                    )

                    continue

                else:

                    print(
                        "Источник плейлиста: "
                        "YouTube Music"
                    )

                    send_download_mode_menu(
                        chat_id,
                        text,
                        "youtube_playlist"
                    )

                    continue

            else:

                send_download_mode_menu(
                    chat_id,
                    text,
                    "track"
                )

                continue

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
