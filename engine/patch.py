from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil


FILE = Path("bot.py")


if not FILE.exists():
    raise SystemExit("ОШИБКА: bot.py не найден.")


text = FILE.read_text(encoding="utf-8")


# ============================================================
# BACKUP
# ============================================================

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = FILE.with_name(
    f"bot.py.backup_modes_{stamp}"
)

shutil.copy2(FILE, backup)

print()
print("Резервная копия создана:")
print(f"  {backup.name}")


# ============================================================
# HELPER
# ============================================================

def replace_once(old, new, description):
    global text

    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"{description}: "
            f"ожидалось ровно 1 совпадение, найдено {count}."
        )

    text = text.replace(old, new, 1)

    print(f"{description}... OK")


# ============================================================
# 1. PENDING REQUESTS
# ============================================================

marker = "_STATUS_MESSAGES = {}"

if marker not in text:
    raise RuntimeError(
        "Не найден _STATUS_MESSAGES = {}."
    )

replacement = """_STATUS_MESSAGES = {}

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
"""

replace_once(
    marker,
    replacement,
    "1/12: добавлено хранилище ожидающих запросов"
)


# ============================================================
# 2. MODE MENU
# ============================================================

anchor = """def send_message(chat_id, text):"""

if anchor not in text:
    raise RuntimeError(
        "Не найден def send_message()."
    )

helper = r'''
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
            "reply_markup": keyboard
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

'''

text = text.replace(
    anchor,
    helper + anchor,
    1
)

print(
    "2/12: добавлены функции меню режима... OK"
)


# ============================================================
# 3. process_yandex_playlist SIGNATURE
# ============================================================

replace_once(
    "def process_yandex_playlist(chat_id, url):",
    """def process_yandex_playlist(
    chat_id,
    url,
    mode="uncensored",
    with_lrc=None
):""",
    "3/12: обновлена сигнатура process_yandex_playlist"
)


# ============================================================
# 4. process_youtube_playlist SIGNATURE
# ============================================================

replace_once(
    "def process_youtube_playlist(chat_id, url):",
    """def process_youtube_playlist(
    chat_id,
    url,
    mode="uncensored",
    with_lrc=None
):""",
    "4/12: обновлена сигнатура process_youtube_playlist"
)


# ============================================================
# 5. process_track SIGNATURE
# ============================================================

replace_once(
    "def process_track(chat_id, url, playlist_progress=None):",
    """def process_track(
    chat_id,
    url,
    playlist_progress=None,
    mode="uncensored",
    with_lrc=None
):""",
    "5/12: обновлена сигнатура process_track"
)


# ============================================================
# 6. process_track -> downloader
# ============================================================

old_downloader_call = """        result = downloader.find_and_download_track(
            artist,
            title,
            duration,
            TRACKS_FOLDER,
            url,
            source,
            youtube_age_restricted
        )"""

new_downloader_call = """        result = downloader.find_and_download_track(
            artist,
            title,
            duration,
            TRACKS_FOLDER,
            url,
            source,
            youtube_age_restricted,
            mode=mode
        )"""

replace_once(
    old_downloader_call,
    new_downloader_call,
    "6/12: mode передан в downloader"
)


# ============================================================
# 7. process_track -> LRC
# ============================================================

# downloader.process_single_track() уже управляет LRC.
# Здесь ничего дополнительно не вызываем.
#
# Но mode/with_lrc должны попасть в downloader.
#
# process_track() сейчас вызывает find_and_download_track()
# напрямую, поэтому LRC там физически не запускается.
#
# Для сохранения существующей архитектуры добавляем LRC
# непосредственно после успешного скачивания.
#
# Нам нужны album и filepath, которые уже имеются.


needle = """        downloader.embed_cover(
            file_path,
            info.get("cover_url"),
            artist,
            title,
            info.get("album", "")
        )
"""

if text.count(needle) != 1:
    raise RuntimeError(
        "7/12: не найден единственный блок embed_cover."
    )

lrc_block = needle + """
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
"""

text = text.replace(
    needle,
    lrc_block,
    1
)

print(
    "7/12: добавлена LRC-логика process_track... OK"
)


# ============================================================
# 8. process_track CALLS IN PLAYLISTS
# ============================================================

old_playlist_call = """                success = process_track(
                    chat_id,
                    track_url,
                    playlist_progress=(
                        index,
                        total_tracks
                    )
                )"""

new_playlist_call = """                success = process_track(
                    chat_id,
                    track_url,
                    playlist_progress=(
                        index,
                        total_tracks
                    ),
                    mode=mode,
                    with_lrc=with_lrc
                )"""

count = text.count(old_playlist_call)

if count != 2:
    raise RuntimeError(
        "8/12: ожидалось 2 вызова process_track "
        f"в плейлистах, найдено {count}."
    )

text = text.replace(
    old_playlist_call,
    new_playlist_call
)

print(
    "8/12: режим передан в оба обработчика плейлистов... OK"
)


# ============================================================
# 9. /start
# ============================================================

old_start = """                        "Цензуры.нет\\n\\n"
                        "Отправь ссылку на трек "
                        "YouTube Music или Яндекс Музыка."
"""

new_start = """                        "Цензуры.нет\\n\\n"
                        "Отправь ссылку на трек "
                        "или плейлист YouTube Music / Яндекс Музыка."
"""

replace_once(
    old_start,
    new_start,
    "9/12: обновлено приглашение /start"
)


# ============================================================
# 10. POLLING: CALLBACK QUERY
# ============================================================

marker = """            message = update.get(
                "message"
            )

            if not message:
                continue
"""

if text.count(marker) != 1:
    raise RuntimeError(
        "10/12: не найден основной блок message."
    )

callback_handler = r'''            # ------------------------------------------------
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

'''

text = text.replace(
    marker,
    callback_handler + """            message = update.get(
                "message"
            )

            if not message:
                continue
""",
    1
)

print(
    "10/12: добавлена обработка callback_query... OK"
)


# ============================================================
# 11. REPLACE DIRECT THREAD START
# ============================================================

old_playlist_thread = """                    thread = threading.Thread(
                        target=process_yandex_playlist,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )"""

new_playlist_thread = """                    send_download_mode_menu(
                        chat_id,
                        text,
                        "yandex_playlist"
                    )

                    continue"""

replace_once(
    old_playlist_thread,
    new_playlist_thread,
    "11/12a: Yandex-плейлист переведён на выбор режима"
)


old_youtube_thread = """                    # Текущую обработку YouTube-плейлистов
                    # пока не меняем.
                    thread = threading.Thread(
                        target=process_youtube_playlist,
                        args=(
                            chat_id,
                            text
                        ),
                        daemon=True
                    )"""

new_youtube_thread = """                    send_download_mode_menu(
                        chat_id,
                        text,
                        "youtube_playlist"
                    )

                    continue"""

replace_once(
    old_youtube_thread,
    new_youtube_thread,
    "11/12b: YouTube-плейлист переведён на выбор режима"
)


old_track_thread = """                thread = threading.Thread(
                    target=process_track,
                    args=(
                        chat_id,
                        text
                    ),
                    daemon=True
                )"""

new_track_thread = """                send_download_mode_menu(
                    chat_id,
                    text,
                    "track"
                )

                continue"""

replace_once(
    old_track_thread,
    new_track_thread,
    "11/12c: одиночный трек переведён на выбор режима"
)


# ============================================================
# 12. VALIDATION
# ============================================================

FILE.write_text(
    text,
    encoding="utf-8"
)

print(
    "12/12: изменения записаны... OK"
)


# ------------------------------------------------------------
# AST
# ------------------------------------------------------------

source = FILE.read_text(
    encoding="utf-8"
)

try:
    ast.parse(
        source,
        filename=str(FILE)
    )
except SyntaxError as e:
    print()
    print("AST: ОШИБКА")
    print(e)
    print()
    print("Восстановление backup...")

    shutil.copy2(
        backup,
        FILE
    )

    raise SystemExit(1)

print()
print("AST: OK")


# ------------------------------------------------------------
# py_compile
# ------------------------------------------------------------

try:
    py_compile.compile(
        str(FILE),
        doraise=True
    )
except Exception as e:
    print()
    print("py_compile: ОШИБКА")
    print(e)
    print()
    print("Восстановление backup...")

    shutil.copy2(
        backup,
        FILE
    )

    raise SystemExit(1)

print("py_compile: OK")


# ------------------------------------------------------------
# FINAL STRUCTURE CHECK
# ------------------------------------------------------------

check = FILE.read_text(
    encoding="utf-8"
)

required = [
    'def process_track(',
    'mode="uncensored"',
    'with_lrc=None',
    'def process_yandex_playlist(',
    'def process_youtube_playlist(',
    '_PENDING_DOWNLOADS = {}',
    'send_download_mode_menu(',
    'answer_callback_query(',
    'start_download_request(',
    '"mode:normal:1"',
    '"mode:normal:0"',
    '"mode:uncensored:1"',
    '"mode:uncensored:0"',
    'mode=mode',
    'with_lrc=with_lrc',
    'callback_query',
]

missing = [
    item
    for item in required
    if item not in check
]

if missing:
    print()
    print("Проверка структуры: ОШИБКА")
    for item in missing:
        print("  отсутствует:", item)

    print()
    print("Восстановление backup...")
    shutil.copy2(
        backup,
        FILE
    )

    raise SystemExit(1)

print("Проверка структуры: OK")


# ------------------------------------------------------------
# SIGNS WITHOUT IMPORT
# ------------------------------------------------------------

tree = ast.parse(
    check,
    filename=str(FILE)
)

functions = {
    node.name: node
    for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}

for name in (
    "process_track",
    "process_yandex_playlist",
    "process_youtube_playlist",
):
    if name not in functions:
        print(
            f"Проверка функции {name}: ОШИБКА"
        )

        shutil.copy2(
            backup,
            FILE
        )

        raise SystemExit(1)

    print(
        f"Проверка функции {name}: OK"
    )


print()
print("=" * 70)
print("ПАТЧ bot.py УСПЕШНО ЗАВЕРШЁН")
print("=" * 70)
print()
print("Backup:")
print(f"  {backup.name}")
print()
print("Маршрутизация:")
print()
print("  normal:")
print("    YouTube / Yandex")
print("        -> YouTube fallback")
print("        -> yt-dlp")
print()
print("  uncensored:")
print("    SoundCloud")
print("        -> MP3Party")
print("        -> MP3TM")
print("        -> AudioStart")
print()
print("LRC:")
print("    True  -> включён")
print("    False -> выключен")
print("    None  -> старое значение DOWNLOAD_LRC")
print()
print("Telegram:")
print("    ссылка -> меню 4 режимов -> обработка")
