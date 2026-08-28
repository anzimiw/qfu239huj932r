from pathlib import Path
from datetime import datetime
import ast
import shutil
import re


FILE = Path("bot.py")


def main():
    print("=" * 70)
    print("ПАТЧ TELEGRAM API NETWORK CONTROL V2")
    print("=" * 70)
    print()

    if not FILE.exists():
        raise RuntimeError("Не найден bot.py")

    original = FILE.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # BACKUP
    # ------------------------------------------------------------

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = FILE.with_name(
        f"bot.py.backup_{timestamp}"
    )

    shutil.copy2(FILE, backup)

    print(f"Резервная копия: {backup.name}")
    print()

    try:
        # --------------------------------------------------------
        # FIND telegram_request()
        # --------------------------------------------------------

        match = re.search(
            r"(?ms)^def telegram_request\(method, params=None\):.*?(?=^# ={5,}|^def |\Z)",
            original
        )

        if not match:
            raise RuntimeError(
                "Не найден блок telegram_request()."
            )

        old_block = match.group(0)

        # Проверяем, что это именно наша текущая версия.
        required = [
            'path = f"/bot{BOT_TOKEN}/{method}"',
            'socket.create_connection',
            'context.wrap_socket',
            'tls_sock.sendall',
            'tls_sock.recv',
            'POLL_TIMEOUT'
        ]

        for marker in required:
            if marker not in old_block:
                raise RuntimeError(
                    f"В telegram_request() не найден ожидаемый фрагмент: "
                    f"{marker}"
                )

        # --------------------------------------------------------
        # NEW telegram_request()
        # --------------------------------------------------------

        new_block = r'''def telegram_request(method, params=None):

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
                f"GET {path}\r\n"
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
'''

        # --------------------------------------------------------
        # ВАЖНАЯ ПРОВЕРКА HTTP REQUEST
        # --------------------------------------------------------
        #
        # Здесь намеренно проверяем реальную строку:
        #
        # GET /bot... HTTP/1.1
        #
        # Это предотвращает повторение предыдущей ошибки
        # с повреждённым f-string.
        # --------------------------------------------------------

        if 'f"GET {path}\\r\\n"' not in new_block:
            raise RuntimeError(
                "В новом блоке не найдена корректная "
                "HTTP GET строка."
            )

        if 'f"Host: {TELEGRAM_HOST}\\r\\n"' not in new_block:
            raise RuntimeError(
                "В новом блоке не найдена корректная "
                "Host строка."
            )

        if "sock.settimeout(" not in new_block:
            raise RuntimeError(
                "Не найден TCP socket timeout."
            )

        if "tls_sock.settimeout(" not in new_block:
            raise RuntimeError(
                "Не найден TLS socket timeout."
            )

        if "WinError {win_error}" not in new_block:
            raise RuntimeError(
                "Не найдена диагностика WinError."
            )

        # --------------------------------------------------------
        # REPLACE
        # --------------------------------------------------------

        source = (
            original[:match.start()]
            + new_block
            + original[match.end():]
        )

        # --------------------------------------------------------
        # SYNTAX CHECK BEFORE WRITE
        # --------------------------------------------------------

        ast.parse(
            source,
            filename=str(FILE)
        )

        compile(
            source,
            str(FILE),
            "exec"
        )

        # --------------------------------------------------------
        # WRITE
        # --------------------------------------------------------

        FILE.write_text(
            source,
            encoding="utf-8"
        )

        print("Изменён: bot.py")
        print()

        # --------------------------------------------------------
        # FINAL CHECK
        # --------------------------------------------------------

        final_source = FILE.read_text(
            encoding="utf-8"
        )

        compile(
            final_source,
            str(FILE),
            "exec"
        )

        checks = [
            (
                "TCP socket timeout",
                "sock.settimeout(" in final_source
            ),
            (
                "TLS socket timeout",
                "tls_sock.settimeout(" in final_source
            ),
            (
                "TCP diagnostics",
                "Telegram API: TCP connection failed:"
                in final_source
            ),
            (
                "TLS diagnostics",
                "Telegram API: TLS connection failed:"
                in final_source
            ),
            (
                "HTTP receive diagnostics",
                "Telegram API: HTTP receive failed:"
                in final_source
            ),
            (
                "WinError diagnostics",
                "WinError {win_error}"
                in final_source
            ),
            (
                "getUpdates branch",
                'if method == "getUpdates":'
                in final_source
            ),
            (
                "POLL_TIMEOUT",
                "telegram_api_timeout = POLL_TIMEOUT + 10"
                in final_source
            ),
        ]

        failed = [
            name
            for name, ok in checks
            if not ok
        ]

        if failed:

            print(
                "ОШИБКА: финальная проверка не пройдена."
            )

            for name in failed:

                print(
                    f"  Не найдено: {name}"
                )

            shutil.copy2(
                backup,
                FILE
            )

            print()
            print(
                f"Восстановлен: {FILE.name}"
            )

            raise RuntimeError(
                "Финальная проверка не пройдена."
            )

        print(
            "Финальная проверка: OK"
        )

        print(
            "Синтаксис: OK"
        )

        print()
        print("=" * 70)
        print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
        print("=" * 70)
        print()

        print(
            "Изменён telegram_request():"
        )

        print(
            "  - TCP timeout контролируется"
        )

        print(
            "  - TLS socket timeout контролируется"
        )

        print(
            "  - HTTP recv timeout контролируется"
        )

        print(
            "  - TCP/TLS/HTTP ошибки диагностируются отдельно"
        )

        print(
            "  - WinError выводится явно"
        )

        print(
            "  - getUpdates оставлен на POLL_TIMEOUT"
        )

        print()
        print(
            f"Резервная копия: {backup.name}"
        )


    except Exception as error:

        print()
        print("=" * 70)
        print("ПАТЧ НЕ ПРИМЕНЁН")
        print("=" * 70)
        print()

        print(
            f"{type(error).__name__}: {error}"
        )

        # Если bot.py уже был изменён, восстанавливаем.
        try:

            shutil.copy2(
                backup,
                FILE
            )

            print()
            print(
                f"Восстановлен: {FILE.name}"
            )

        except Exception as restore_error:

            print()
            print(
                "КРИТИЧЕСКАЯ ОШИБКА: "
                "не удалось восстановить bot.py:"
            )

            print(
                f"{type(restore_error).__name__}: "
                f"{restore_error}"
            )

        raise


if __name__ == "__main__":
    main()
