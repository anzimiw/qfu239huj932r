import ast
import os
import re
import shutil
from datetime import datetime


BOT_FILE = "bot.py"


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def syntax_check(path):
    source = read_text(path)
    ast.parse(source, filename=path)


def find_function(source, function_name):
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                start = node.lineno - 1

                if node.decorator_list:
                    start = min(
                        decorator.lineno - 1
                        for decorator in node.decorator_list
                    )

                end = node.end_lineno

                lines = source.splitlines(keepends=True)

                return (
                    start,
                    end,
                    "".join(lines[start:end])
                )

    return None


def replace_function(source, function_name, new_function):
    found = find_function(source, function_name)

    if not found:
        raise RuntimeError(
            f"Функция {function_name}() не найдена."
        )

    start, end, old_function = found

    lines = source.splitlines(keepends=True)

    replacement = new_function.rstrip() + "\n\n"

    return (
        "".join(lines[:start])
        + replacement
        + "".join(lines[end:])
    )


TELEGRAM_CONSTANTS = r'''
# ============================================================
# TELEGRAM TIMEOUTS
# ============================================================

# Обычные запросы Telegram API:
TELEGRAM_REQUEST_CONNECT_TIMEOUT = 30
TELEGRAM_REQUEST_RESPONSE_TIMEOUT = 60

# Загрузка MP3:
# Отдельный timeout подключения и отдельный timeout
# ожидания ответа после отправки multipart.
TELEGRAM_UPLOAD_CONNECT_TIMEOUT = 60
TELEGRAM_UPLOAD_RESPONSE_TIMEOUT = 180
'''


NEW_TELEGRAM_REQUEST = r'''
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
        timeout=TELEGRAM_REQUEST_CONNECT_TIMEOUT
    )

    try:

        context = ssl.create_default_context()

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )

        try:

            tls_sock.settimeout(
                TELEGRAM_REQUEST_RESPONSE_TIMEOUT
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

        finally:

            tls_sock.close()

    finally:

        try:
            sock.close()
        except Exception:
            pass

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
'''


NEW_TELEGRAM_UPLOAD_FILE = r'''
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
                f'filename="{filename}"\r\n"
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

    # --------------------------------------------------------
    # CONNECT
    # --------------------------------------------------------

    print(
        "Telegram upload: "
        "подключение к Telegram..."
    )

    sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=TELEGRAM_UPLOAD_CONNECT_TIMEOUT
    )

    try:

        context = ssl.create_default_context()

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )

        try:

            # После установления TLS-соединения
            # используем отдельный timeout ожидания ответа.
            tls_sock.settimeout(
                TELEGRAM_UPLOAD_RESPONSE_TIMEOUT
            )

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
                "отправка HTTP-заголовков..."
            )

            tls_sock.sendall(
                request
            )

            print(
                "Telegram upload: "
                "отправка MP3..."
            )

            tls_sock.sendall(
                body
            )

            send_elapsed = (
                time.time() - start_time
            )

            print(
                f"Telegram upload: "
                f"данные отправлены за "
                f"{send_elapsed:.2f} сек."
            )

            print(
                "Telegram upload: "
                "ожидание ответа Telegram..."
            )

            response = b""

            while True:

                chunk = tls_sock.recv(
                    8192
                )

                if not chunk:
                    break

                response += chunk

        finally:

            tls_sock.close()

    except Exception:

        try:
            sock.close()
        except Exception:
            pass

        raise

    finally:

        try:
            sock.close()
        except Exception:
            pass

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
'''


def main():

    print("=" * 70)
    print("CENSURU.NET — TELEGRAM TIMEOUT PATCH")
    print("=" * 70)
    print()

    if not os.path.isfile(BOT_FILE):
        raise RuntimeError(
            f"Не найден файл: {BOT_FILE}"
        )

    print("Проверка исходного bot.py...")

    syntax_check(BOT_FILE)

    print("  OK: исходный синтаксис.")
    print()

    source = read_text(BOT_FILE)

    print("Проверка функций...")

    request_found = find_function(
        source,
        "telegram_request"
    )

    upload_found = find_function(
        source,
        "telegram_upload_file"
    )

    if not request_found:
        raise RuntimeError(
            "Не найдена telegram_request()."
        )

    print(
        "  OK: telegram_request() найдена."
    )

    if not upload_found:
        raise RuntimeError(
            "Не найдена telegram_upload_file()."
        )

    print(
        "  OK: telegram_upload_file() найдена."
    )

    print()

    # --------------------------------------------------------
    # Проверяем, что константы ещё не установлены.
    # --------------------------------------------------------

    if "TELEGRAM_UPLOAD_RESPONSE_TIMEOUT" in source:

        raise RuntimeError(
            "Timeout-константы уже присутствуют в bot.py. "
            "Патч повторно применять не нужно."
        )

    # --------------------------------------------------------
    # BACKUP
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_file = (
        f"{BOT_FILE}.backup_{timestamp}"
    )

    print("Создание резервной копии...")

    shutil.copy2(
        BOT_FILE,
        backup_file
    )

    print(
        f"  OK: {backup_file}"
    )

    try:

        # ----------------------------------------------------
        # 1. TIMEOUT CONSTANTS
        # ----------------------------------------------------

        print()
        print(
            "1/3: добавление Telegram timeout-констант..."
        )

        marker = (
            "# ============================================================\n"
            "# TELEGRAM TIMEOUTS\n"
            "# ============================================================\n"
        )

        # Ставим перед telegram_request().
        request_pos = source.find(
            "def telegram_request("
        )

        if request_pos < 0:
            raise RuntimeError(
                "Не найдена точка вставки timeout-констант."
            )

        source = (
            source[:request_pos]
            + TELEGRAM_CONSTANTS.strip()
            + "\n\n"
            + source[request_pos:]
        )

        print("  OK")

        # ----------------------------------------------------
        # 2. telegram_request()
        # ----------------------------------------------------

        print()
        print(
            "2/3: обновление telegram_request()..."
        )

        source = replace_function(
            source,
            "telegram_request",
            NEW_TELEGRAM_REQUEST
        )

        print("  OK")

        # ----------------------------------------------------
        # 3. telegram_upload_file()
        # ----------------------------------------------------

        print()
        print(
            "3/3: полная замена telegram_upload_file()..."
        )

        source = replace_function(
            source,
            "telegram_upload_file",
            NEW_TELEGRAM_UPLOAD_FILE
        )

        print("  OK")

        # ----------------------------------------------------
        # WRITE
        # ----------------------------------------------------

        write_text(
            BOT_FILE,
            source
        )

        # ----------------------------------------------------
        # FINAL CHECK
        # ----------------------------------------------------

        print()
        print("Проверка результата...")

        syntax_check(BOT_FILE)

        result = read_text(BOT_FILE)

        if not find_function(
            result,
            "telegram_request"
        ):
            raise RuntimeError(
                "После патча telegram_request() не найдена."
            )

        if not find_function(
            result,
            "telegram_upload_file"
        ):
            raise RuntimeError(
                "После патча telegram_upload_file() не найдена."
            )

        required_constants = [
            "TELEGRAM_REQUEST_CONNECT_TIMEOUT",
            "TELEGRAM_REQUEST_RESPONSE_TIMEOUT",
            "TELEGRAM_UPLOAD_CONNECT_TIMEOUT",
            "TELEGRAM_UPLOAD_RESPONSE_TIMEOUT",
        ]

        for constant in required_constants:

            if constant not in result:

                raise RuntimeError(
                    f"Не найдена timeout-константа: {constant}"
                )

        print("  OK: синтаксис.")
        print("  OK: telegram_request().")
        print("  OK: telegram_upload_file().")
        print("  OK: timeout-константы.")

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН.")
        print("=" * 70)

        print()
        print(
            "Новые значения:"
        )

        print(
            "  Telegram request connect: 30 сек."
        )

        print(
            "  Telegram request response: 60 сек."
        )

        print(
            "  Telegram upload connect: 60 сек."
        )

        print(
            "  Telegram upload response: 180 сек."
        )

        print()
        print(
            f"Резервная копия: {backup_file}"
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("ОШИБКА ПАТЧА")
        print("=" * 70)
        print()
        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Выполняется автоматический откат..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        print(
            "  OK: bot.py восстановлен из резервной копии."
        )

        print()
        print(
            "Резервная копия:"
        )

        print(
            f"  {backup_file}"
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
