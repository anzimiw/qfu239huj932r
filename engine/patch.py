import ast
import re
import shutil
from datetime import datetime
from pathlib import Path


BOT_FILE = Path("bot.py")


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def check_syntax(path):
    source = path.read_text(
        encoding="utf-8-sig"
    )

    ast.parse(
        source,
        filename=str(path)
    )

    return source


def find_function(source, function_name):
    """
    Возвращает диапазон строк функции:
    (start_index, end_index)
    """
    tree = ast.parse(
        source,
        filename=str(BOT_FILE)
    )

    for node in tree.body:

        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ):
            start = node.lineno - 1

            if node.end_lineno is None:
                raise RuntimeError(
                    f"Не удалось определить конец {function_name}()."
                )

            end = node.end_lineno

            return start, end

    return None


def replace_function(source, function_name, new_function):
    result = find_function(
        source,
        function_name
    )

    if result is None:
        raise RuntimeError(
            f"Функция {function_name}() не найдена."
        )

    start, end = result

    lines = source.splitlines(
        keepends=True
    )

    replacement = (
        new_function.rstrip()
        + "\n\n"
    )

    lines[start:end] = [
        replacement
    ]

    return "".join(lines)


def count_text(source, text):
    return source.count(text)


# ============================================================
# НОВАЯ telegram_request()
# ============================================================

NEW_TELEGRAM_REQUEST = r'''def telegram_request(method, params=None):

    if params is None:
        params = {}

    path = f"/bot{BOT_TOKEN}/{method}"

    if params:
        query = urlencode(
            params,
            encoding="utf-8"
        )

        path += "?" + query

    print()
    print(
        f"Telegram request: {method}"
    )

    print(
        "Telegram request: "
        "устанавливаю TCP-соединение..."
    )

    sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=TELEGRAM_CONNECT_TIMEOUT
    )

    try:

        print(
            "Telegram request: "
            "TCP-соединение установлено."
        )

        context = ssl.create_default_context()

        print(
            "Telegram request: "
            "устанавливаю TLS..."
        )

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )

        # ----------------------------------------------------
        # Для getUpdates нужен увеличенный timeout,
        # потому что это long polling.
        # Для остальных API-запросов используется обычный
        # TELEGRAM_REQUEST_TIMEOUT.
        # ----------------------------------------------------

        if method == "getUpdates":

            tls_sock.settimeout(
                POLL_TIMEOUT + 10
            )

        else:

            tls_sock.settimeout(
                TELEGRAM_REQUEST_TIMEOUT
            )

        try:

            print(
                "Telegram request: "
                "TLS установлен."
            )

            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {TELEGRAM_HOST}\r\n"
                f"User-Agent: CENSURU.NET-Bot/1.0\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )

            print(
                "Telegram request: "
                "отправляю HTTP-запрос..."
            )

            tls_sock.sendall(
                request.encode("ascii")
            )

            print(
                "Telegram request: "
                "запрос отправлен, ожидаю ответ..."
            )

            response = b""

            while True:

                chunk = tls_sock.recv(
                    8192
                )

                if not chunk:
                    break

                response += chunk

            print(
                "Telegram request: "
                f"HTTP-ответ получен, "
                f"{len(response):,} байт."
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


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("CENSURU.NET — TELEGRAM TIMEOUT PATCH")
    print("=" * 70)
    print()

    if not BOT_FILE.is_file():

        print(
            f"ОШИБКА: файл не найден: {BOT_FILE}"
        )

        raise SystemExit(1)

    print("Проверка исходного bot.py...")

    try:
        original_source = check_syntax(
            BOT_FILE
        )

        print(
            "  OK: исходный синтаксис."
        )

    except Exception as e:

        print(
            f"  ОШИБКА синтаксиса: "
            f"{type(e).__name__}: {e}"
        )

        raise SystemExit(1)

    print()
    print("Проверка функций...")

    telegram_request_range = find_function(
        original_source,
        "telegram_request"
    )

    telegram_upload_range = find_function(
        original_source,
        "telegram_upload_file"
    )

    if telegram_request_range is None:

        print(
            "  ОШИБКА: telegram_request() не найдена."
        )

        raise SystemExit(1)

    print(
        "  OK: telegram_request() найдена."
    )

    if telegram_upload_range is None:

        print(
            "  ОШИБКА: telegram_upload_file() не найдена."
        )

        raise SystemExit(1)

    print(
        "  OK: telegram_upload_file() найдена."
    )

    # --------------------------------------------------------
    # Проверяем наличие POLL_TIMEOUT
    # --------------------------------------------------------

    if "POLL_TIMEOUT" not in original_source:

        print()
        print(
            "ОШИБКА: POLL_TIMEOUT не найден."
        )

        raise SystemExit(1)

    # --------------------------------------------------------
    # Создание backup
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_file = Path(
        f"bot.py.backup_{timestamp}"
    )

    print()
    print("Создание резервной копии...")

    shutil.copy2(
        BOT_FILE,
        backup_file
    )

    print(
        f"  OK: {backup_file.name}"
    )

    try:

        source = original_source

        # ====================================================
        # 1. Добавление timeout-констант
        # ====================================================

        print()
        print(
            "1/4: добавление Telegram timeout-констант..."
        )

        constants_block = """
# ============================================================
# TELEGRAM NETWORK TIMEOUTS
# ============================================================
#
# TCP_CONNECT:
#     Максимальное время установки TCP-соединения.
#
# REQUEST:
#     Обычные Telegram API-запросы:
#     sendMessage, editMessageText и т.п.
#
# UPLOAD:
#     Загрузка MP3 через sendAudio.
#
# getUpdates использует отдельно POLL_TIMEOUT + 10,
# потому что это long polling.
# ============================================================

TELEGRAM_CONNECT_TIMEOUT = 30
TELEGRAM_REQUEST_TIMEOUT = 60
TELEGRAM_UPLOAD_TIMEOUT = 180

"""

        if (
            "TELEGRAM_CONNECT_TIMEOUT"
            not in source
        ):

            pattern = re.compile(
                r"(^[ \t]*POLL_TIMEOUT[ \t]*=[^\n]*\n)",
                re.MULTILINE
            )

            match = pattern.search(
                source
            )

            if not match:
                raise RuntimeError(
                    "Не удалось найти строку POLL_TIMEOUT для "
                    "вставки timeout-констант."
                )

            insertion_point = match.end()

            source = (
                source[:insertion_point]
                + constants_block
                + source[insertion_point:]
            )

            print(
                "  OK: timeout-константы добавлены."
            )

        else:

            print(
                "  OK: timeout-константы уже существуют."
            )

        # ====================================================
        # 2. Замена telegram_request()
        # ====================================================

        print()
        print(
            "2/4: обновление telegram_request()..."
        )

        source = replace_function(
            source,
            "telegram_request",
            NEW_TELEGRAM_REQUEST
        )

        print(
            "  OK"
        )

        # ====================================================
        # 3. Обновление telegram_upload_file()
        # ====================================================

        print()
        print(
            "3/4: обновление telegram_upload_file()..."
        )

        # ----------------------------------------------------
        # TCP timeout
        # ----------------------------------------------------

        old_connect = """sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=60
    )"""

        new_connect = """print(
        "Telegram upload: "
        "устанавливаю TCP-соединение..."
    )

    sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=TELEGRAM_CONNECT_TIMEOUT
    )

    print(
        "Telegram upload: "
        "TCP-соединение установлено."
    )"""

        if old_connect in source:

            source = source.replace(
                old_connect,
                new_connect,
                1
            )

        else:

            # Уже изменённый вариант
            old_connect_2 = """sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=120
    )"""

            if old_connect_2 in source:

                new_connect_2 = """print(
        "Telegram upload: "
        "устанавливаю TCP-соединение..."
    )

    sock = socket.create_connection(
        (
            TELEGRAM_IP,
            TELEGRAM_PORT
        ),
        timeout=TELEGRAM_CONNECT_TIMEOUT
    )

    print(
        "Telegram upload: "
        "TCP-соединение установлено."
    )"""

                source = source.replace(
                    old_connect_2,
                    new_connect_2,
                    1
                )

            elif "timeout=TELEGRAM_CONNECT_TIMEOUT" in source:

                print(
                    "  TCP timeout уже настроен."
                )

            else:

                raise RuntimeError(
                    "Не удалось безопасно найти TCP-соединение "
                    "в telegram_upload_file()."
                )

        # ----------------------------------------------------
        # TLS timeout + диагностика
        # ----------------------------------------------------

        old_tls = """context = ssl.create_default_context()

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )

        try:"""

        new_tls = """context = ssl.create_default_context()

        print(
            "Telegram upload: "
            "устанавливаю TLS..."
        )

        tls_sock = context.wrap_socket(
            sock,
            server_hostname=TELEGRAM_HOST
        )

        tls_sock.settimeout(
            TELEGRAM_UPLOAD_TIMEOUT
        )

        print(
            "Telegram upload: "
            "TLS установлен."
        )

        try:"""

        if old_tls in source:

            source = source.replace(
                old_tls,
                new_tls,
                1
            )

        elif "tls_sock.settimeout(\n            TELEGRAM_UPLOAD_TIMEOUT" in source:

            print(
                "  TLS upload timeout уже настроен."
            )

        else:

            raise RuntimeError(
                "Не удалось безопасно найти TLS-блок "
                "в telegram_upload_file()."
            )

        # ----------------------------------------------------
        # Диагностика отправки multipart
        # ----------------------------------------------------

        old_send = """            start_time = time.time()

            tls_sock.sendall(
                request
            )

            tls_sock.sendall(
                body
            )

            elapsed = (
                time.time() - start_time
            )"""

        new_send = """            start_time = time.time()

            print(
                "Telegram upload: "
                "отправляю HTTP-заголовки..."
            )

            tls_sock.sendall(
                request
            )

            print(
                "Telegram upload: "
                "заголовки отправлены."
            )

            print(
                "Telegram upload: "
                "отправляю multipart body..."
            )

            tls_sock.sendall(
                body
            )

            print(
                "Telegram upload: "
                "multipart body полностью отправлен."
            )

            elapsed = (
                time.time() - start_time
            )"""

        if old_send in source:

            source = source.replace(
                old_send,
                new_send,
                1
            )

        elif (
            "multipart body полностью отправлен"
            in source
        ):

            print(
                "  Диагностика отправки уже добавлена."
            )

        else:

            raise RuntimeError(
                "Не удалось безопасно найти блок отправки "
                "multipart в telegram_upload_file()."
            )

        # ----------------------------------------------------
        # Диагностика ожидания ответа
        # ----------------------------------------------------

        old_response = """            response = b""

            while True:

                chunk = tls_sock.recv(
                    8192
                )"""

        new_response = """            print(
                "Telegram upload: "
                "ожидаю HTTP-ответ API..."
            )

            response = b""

            while True:

                chunk = tls_sock.recv(
                    8192
                )"""

        if old_response in source:

            source = source.replace(
                old_response,
                new_response,
                1
            )

        elif (
            "ожидаю HTTP-ответ API"
            in source
        ):

            print(
                "  Диагностика ожидания ответа уже добавлена."
            )

        else:

            raise RuntimeError(
                "Не удалось безопасно найти цикл получения "
                "HTTP-ответа в telegram_upload_file()."
            )

        # ----------------------------------------------------
        # После получения ответа
        # ----------------------------------------------------

        old_response_end = """                response += chunk

        finally:

            tls_sock.close()"""

        new_response_end = """                response += chunk

            print(
                "Telegram upload: "
                f"HTTP-ответ получен, "
                f"{len(response):,} байт."
            )

        finally:

            tls_sock.close()"""

        if old_response_end in source:

            source = source.replace(
                old_response_end,
                new_response_end,
                1
            )

        elif (
            "HTTP-ответ получен"
            in source
        ):

            print(
                "  Диагностика полученного ответа уже добавлена."
            )

        else:

            raise RuntimeError(
                "Не удалось безопасно найти конец цикла "
                "получения HTTP-ответа."
            )

        print(
            "  OK"
        )

        # ====================================================
        # 4. Финальная проверка
        # ====================================================

        print()
        print(
            "4/4: проверка результата..."
        )

        ast.parse(
            source,
            filename=str(BOT_FILE)
        )

        print(
            "  OK: синтаксис."
        )

        # ----------------------------------------------------
        # Проверяем функции
        # ----------------------------------------------------

        required_functions = [
            "telegram_request",
            "telegram_upload_file",
            "send_audio",
            "process_track",
            "process_yandex_playlist",
            "process_youtube_playlist",
        ]

        tree = ast.parse(
            source,
            filename=str(BOT_FILE)
        )

        functions = {
            node.name
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef)
            )
        }

        for function_name in required_functions:

            if function_name in functions:

                print(
                    f"  OK: {function_name}()"
                )

            else:

                raise RuntimeError(
                    f"После патча потеряна функция "
                    f"{function_name}()."
                )

        # ----------------------------------------------------
        # Проверка констант
        # ----------------------------------------------------

        for constant_name in (
            "TELEGRAM_CONNECT_TIMEOUT",
            "TELEGRAM_REQUEST_TIMEOUT",
            "TELEGRAM_UPLOAD_TIMEOUT",
        ):

            if constant_name not in source:

                raise RuntimeError(
                    f"Не найдена константа "
                    f"{constant_name}."
                )

        # ----------------------------------------------------
        # Запись
        # ----------------------------------------------------

        BOT_FILE.write_text(
            source,
            encoding="utf-8"
        )

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН.")
        print("=" * 70)
        print()
        print(
            f"TCP connect timeout: "
            f"{'30'} сек."
        )
        print(
            f"Telegram request timeout: "
            f"{'60'} сек."
        )
        print(
            f"Telegram upload timeout: "
            f"{'180'} сек."
        )
        print()
        print(
            "Для getUpdates сохраняется:"
        )
        print(
            "  POLL_TIMEOUT + 10 сек."
        )
        print()
        print(
            f"Резервная копия: "
            f"{backup_file.name}"
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
            "Восстановление из резервной копии..."
        )

        shutil.copy2(
            backup_file,
            BOT_FILE
        )

        print(
            "OK: исходный bot.py восстановлен."
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
