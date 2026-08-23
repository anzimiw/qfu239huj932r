import ast
import os
import py_compile
import shutil
import sys
from datetime import datetime


# ============================================================
# НАСТРОЙКИ
# ============================================================

ENGINE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DOWNLOADER = os.path.join(
    ENGINE_DIR,
    "downloader.py"
)

SOUNDCLOUD_MODULE = os.path.join(
    ENGINE_DIR,
    "sources_soundcloud.py"
)

BACKUP_PREFIX = (
    "downloader.py.backup_soundcloud_"
)


# ============================================================
# ФУНКЦИИ, КОТОРЫЕ ПЕРЕНОСИМ
# ============================================================

MOVE_FUNCTIONS = (
    "get_soundcloud_client_id",
    "normalize_soundcloud_metadata",
    "evaluate_soundcloud_candidate",
    "fetch_soundcloud_results",
    "search_soundcloud",
    "download_from_soundcloud",
)


# ============================================================
# КОНСТАНТЫ, КОТОРЫЕ НУЖНЫ SOUNDCloud-МОДУЛЮ
# ============================================================

REQUIRED_CONSTANTS = (
    "SOUNDCLOUD_SEARCH_URL",
    "SOUNDCLOUD_HEADERS",
    "SOUNDCLOUD_DURATION_TOLERANCE",
    "SOUNDCLOUD_SEARCH_TIMEOUT",
    "SOUNDCLOUD_DOWNLOAD_TIMEOUT",
    "SOUNDCLOUD_SEARCH_RESULTS",
    "SOUNDCLOUD_CLIENT_ID_TIMEOUT",
    "SOUNDCLOUD_CLIENT_ID_CACHE",
    "YTDLP",
    "FFMPEG",
    "FFPROBE",
    "MIN_FILE_SIZE",
    "EXACT_MATCH_TOLERANCE",
    "SOUNDCLOUD_SERVICE_MODIFIERS",
)


# ============================================================
# БАЗОВЫЕ КОНСТАНТЫ
# ============================================================

DEFAULT_CONSTANTS = {
    "SOUNDCLOUD_SEARCH_URL": (
        '"https://api-v2.soundcloud.com/search/tracks"'
    ),

    "SOUNDCLOUD_DURATION_TOLERANCE": "10.0",

    "SOUNDCLOUD_SEARCH_TIMEOUT": "15",

    "SOUNDCLOUD_DOWNLOAD_TIMEOUT": "90",

    "SOUNDCLOUD_SEARCH_RESULTS": "15",

    "SOUNDCLOUD_CLIENT_ID_TIMEOUT": "15",

    "SOUNDCLOUD_CLIENT_ID_CACHE": "None",

    "EXACT_MATCH_TOLERANCE": "30.0",

    "SOUNDCLOUD_SERVICE_MODIFIERS": """(
    "remix",
    "remixed",
    "remaster",
    "remastered",
    "rework",
    "bootleg",
    "nightcore",
    "slowed",
    "sped up",
    "speed up",
    "edit",
    "live",
    "acoustic",
    "instrumental",
    "mashup",
    "flip",
    "extended",
    "radio edit",
    "version",
    "mix",
    "clean",
    "censored",
    "explicit",
    "uncensored",
    "ремикс",
    "ремастер",
    "ремикш",
    "переработка",
    "бутлег",
    "найткор",
    "ночкор",
    "замедление",
    "замедленный",
    "ускорение",
    "ускоренный",
    "эдит",
    "лайв",
    "акустика",
    "инструментал",
    "мэшап",
    "мешап",
    "флип",
    "кавер",
    "караоке",
    "расширенная версия",
    "клубная версия",
    "реверб",
)""",
}


# ============================================================
# ПРОВЕРКИ
# ============================================================

def fail(message):
    raise RuntimeError(
        message
    )


def read_text(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return file.read()


def write_text(path, text):
    with open(
        path,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        file.write(text)


def compile_file(path):
    py_compile.compile(
        path,
        doraise=True
    )


def create_backup():
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = os.path.join(
        ENGINE_DIR,
        BACKUP_PREFIX + timestamp
    )

    shutil.copy2(
        DOWNLOADER,
        backup
    )

    return backup


# ============================================================
# AST
# ============================================================

def parse_source(source):
    try:
        return ast.parse(
            source
        )

    except SyntaxError as error:
        fail(
            "Исходный downloader.py содержит "
            f"синтаксическую ошибку:\n{error}"
        )


def get_top_level_functions(tree):
    result = {}

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        ):
            result[
                node.name
            ] = node

    return result


def get_top_level_assignments(tree):
    result = {}

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign
            )
        ):

            names = []

            if isinstance(
                node,
                ast.Assign
            ):

                for target in node.targets:

                    if isinstance(
                        target,
                        ast.Name
                    ):
                        names.append(
                            target.id
                        )

            else:

                target = node.target

                if isinstance(
                    target,
                    ast.Name
                ):
                    names.append(
                        target.id
                    )

            for name in names:
                result[
                    name
                ] = node

    return result


# ============================================================
# ИЗВЛЕЧЕНИЕ ИСХОДНОГО КОДА
# ============================================================

def extract_node_source(
    source,
    node
):
    lines = source.splitlines(
        keepends=True
    )

    start = node.lineno - 1

    end = node.end_lineno

    return "".join(
        lines[start:end]
    )


def extract_assignment_source(
    source,
    node
):
    return extract_node_source(
        source,
        node
    )


# ============================================================
# ПРОВЕРКА СТРУКТУРЫ
# ============================================================

def validate_functions(
    functions
):

    missing = [
        name
        for name in MOVE_FUNCTIONS
        if name not in functions
    ]

    if missing:

        fail(
            "В downloader.py не найдены "
            "ожидаемые SoundCloud-функции:\n"
            + "\n".join(
                "  - " + name
                for name in missing
            )
        )

    print(
        "  Все необходимые SoundCloud-функции найдены."
    )


# ============================================================
# ПОСТРОЕНИЕ SOUNDCloud-МОДУЛЯ
# ============================================================

def build_soundcloud_module(
    source,
    tree
):

    functions = get_top_level_functions(
        tree
    )

    assignments = get_top_level_assignments(
        tree
    )

    parts = []

    parts.append(
        """# ============================================================
# Censuru.net — SoundCloud source
#
# Этот файл содержит реальную рабочую логику SoundCloud,
# перенесённую из downloader.py.
#
# Не редактировать вручную во время выполнения патча.
# ============================================================

import os
import re
import html
import shutil
import subprocess
import requests

from urllib.parse import unquote


"""
    )

    # --------------------------------------------------------
    # Служебные пути / константы.
    # --------------------------------------------------------

    constant_sources = {}

    for name in REQUIRED_CONSTANTS:

        node = assignments.get(
            name
        )

        if node is not None:

            try:
                value_source = (
                    extract_assignment_source(
                        source,
                        node
                    )
                )

                constant_sources[
                    name
                ] = value_source.strip()

            except Exception:
                pass

    # --------------------------------------------------------
    # Принудительно создаём значения путей.
    #
    # Они не зависят от downloader.py.
    # --------------------------------------------------------

    parts.append(
        """ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_FOLDER = os.path.dirname(
    ENGINE_FOLDER
)

YTDLP = os.path.join(
    ENGINE_FOLDER,
    "yt-dlp.exe"
)

FFMPEG = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffmpeg.exe"
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)

MIN_FILE_SIZE = 10 * 1024

"""
    )

    # --------------------------------------------------------
    # SoundCloud headers.
    # --------------------------------------------------------

    parts.append(
        """SOUNDCLOUD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/json, text/plain, */*"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Referer": (
        "https://soundcloud.com/"
    )
}

"""
    )

    # --------------------------------------------------------
    # Константы.
    #
    # Берём существующие значения из downloader.py,
    # если они там есть.
    # --------------------------------------------------------

    for name in (
        "SOUNDCLOUD_SEARCH_URL",
        "SOUNDCLOUD_DURATION_TOLERANCE",
        "SOUNDCLOUD_SEARCH_TIMEOUT",
        "SOUNDCLOUD_DOWNLOAD_TIMEOUT",
        "SOUNDCLOUD_SEARCH_RESULTS",
        "SOUNDCLOUD_CLIENT_ID_TIMEOUT",
        "EXACT_MATCH_TOLERANCE",
        "SOUNDCLOUD_SERVICE_MODIFIERS",
    ):

        if name in constant_sources:

            parts.append(
                constant_sources[name]
                + "\n\n"
            )

        else:

            parts.append(
                f"{name} = "
                f"{DEFAULT_CONSTANTS[name]}\n\n"
            )

    parts.append(
        "SOUNDCLOUD_CLIENT_ID_CACHE = None\n\n"
    )

    # --------------------------------------------------------
    # Функции.
    #
    # Сначала зависимости,
    # затем публичные функции.
    # --------------------------------------------------------

    for name in (
        "get_soundcloud_client_id",
        "normalize_soundcloud_metadata",
        "evaluate_soundcloud_candidate",
        "fetch_soundcloud_results",
        "search_soundcloud",
        "download_from_soundcloud",
    ):

        node = functions.get(
            name
        )

        if node is None:
            fail(
                f"Функция {name} "
                "не найдена."
            )

        parts.append(
            "\n\n"
            + extract_node_source(
                source,
                node
            )
            + "\n"
        )

    return "".join(
        parts
    )


# ============================================================
# СОЗДАНИЕ IMPORT
# ============================================================

def add_import_to_downloader(
    source
):

    import_line = (
        "from sources_soundcloud import (\n"
        "    get_soundcloud_client_id,\n"
        "    normalize_soundcloud_metadata,\n"
        "    evaluate_soundcloud_candidate,\n"
        "    fetch_soundcloud_results,\n"
        "    search_soundcloud,\n"
        "    download_from_soundcloud,\n"
        ")\n"
    )

    if (
        "from sources_soundcloud import"
        in source
    ):
        return source

    lines = source.splitlines(
        keepends=True
    )

    # --------------------------------------------------------
    # Вставляем импорт после существующих import.
    # --------------------------------------------------------

    insert_at = 0

    for index, line in enumerate(
        lines
    ):

        stripped = line.strip()

        if (
            stripped.startswith(
                "import "
            )
            or stripped.startswith(
                "from "
            )
        ):
            insert_at = index + 1

    lines.insert(
        insert_at,
        "\n"
        + import_line
        + "\n"
    )

    return "".join(
        lines
    )


# ============================================================
# УДАЛЕНИЕ ФУНКЦИЙ ИЗ DOWNLOADER
# ============================================================

def remove_functions(
    source,
    tree
):

    lines = source.splitlines(
        keepends=True
    )

    nodes = []

    functions = get_top_level_functions(
        tree
    )

    for name in MOVE_FUNCTIONS:

        node = functions.get(
            name
        )

        if node is None:
            fail(
                f"Не найден AST-блок "
                f"функции {name}."
            )

        nodes.append(
            node
        )

    # Удаляем снизу вверх,
    # чтобы номера строк не смещались.
    nodes.sort(
        key=lambda node: node.lineno,
        reverse=True
    )

    for node in nodes:

        start = node.lineno - 1

        end = node.end_lineno

        del lines[
            start:end
        ]

    return "".join(
        lines
    )


# ============================================================
# ПРОВЕРКА РЕЗУЛЬТАТА
# ============================================================

def validate_downloader(
    source
):

    tree = parse_source(
        source
    )

    functions = get_top_level_functions(
        tree
    )

    for name in MOVE_FUNCTIONS:

        if name in functions:

            fail(
                "Функция "
                f"{name} "
                "не была удалена из downloader.py."
            )

    if (
        "from sources_soundcloud import"
        not in source
    ):

        fail(
            "Импорт sources_soundcloud "
            "не найден в downloader.py."
        )

    print(
        "  OK: SoundCloud-функции удалены "
        "из downloader.py."
    )

    print(
        "  OK: импорт sources_soundcloud добавлен."
    )


def validate_module():

    compile_file(
        SOUNDCLOUD_MODULE
    )

    module_source = read_text(
        SOUNDCLOUD_MODULE
    )

    tree = parse_source(
        module_source
    )

    functions = get_top_level_functions(
        tree
    )

    for name in MOVE_FUNCTIONS:

        if name not in functions:

            fail(
                "В sources_soundcloud.py "
                f"отсутствует функция {name}."
            )

    print(
        "  OK: sources_soundcloud.py"
    )

    print(
        "  OK: все SoundCloud-функции "
        "присутствуют."
    )


# ============================================================
# ОСНОВНОЙ ПАТЧ
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "CENSURU.NET — ПЕРЕНОС SOUNDCLOUD"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # Проверяем downloader.
    # --------------------------------------------------------

    if not os.path.isfile(
        DOWNLOADER
    ):

        fail(
            "Не найден downloader.py:\n"
            + DOWNLOADER
        )

    print()
    print(
        "1/7: чтение downloader.py..."
    )

    original_source = read_text(
        DOWNLOADER
    )

    tree = parse_source(
        original_source
    )

    functions = get_top_level_functions(
        tree
    )

    print(
        "  OK: синтаксис."
    )

    print(
        f"  Найдено функций: "
        f"{len(functions)}"
    )

    # --------------------------------------------------------
    # Проверяем SoundCloud-функции.
    # --------------------------------------------------------

    print()
    print(
        "2/7: проверка SoundCloud..."
    )

    validate_functions(
        functions
    )

    for name in MOVE_FUNCTIONS:

        node = functions[name]

        print(
            f"  OK: {name} "
            f"(строки "
            f"{node.lineno}-{node.end_lineno})"
        )

    # --------------------------------------------------------
    # Backup.
    # --------------------------------------------------------

    print()
    print(
        "3/7: создание резервной копии..."
    )

    backup = create_backup()

    print(
        "Backup создан:"
    )

    print(
        backup
    )

    # --------------------------------------------------------
    # Создаём новый SoundCloud-модуль.
    # --------------------------------------------------------

    print()
    print(
        "4/7: создание sources_soundcloud.py..."
    )

    module_source = build_soundcloud_module(
        original_source,
        tree
    )

    write_text(
        SOUNDCLOUD_MODULE,
        module_source
    )

    print(
        "  OK: sources_soundcloud.py создан."
    )

    # --------------------------------------------------------
    # Меняем downloader.
    # --------------------------------------------------------

    print()
    print(
        "5/7: перенос функций из downloader.py..."
    )

    new_source = remove_functions(
        original_source,
        tree
    )

    new_source = add_import_to_downloader(
        new_source
    )

    write_text(
        DOWNLOADER,
        new_source
    )

    print(
        "  OK: SoundCloud-блок перенесён."
    )

    # --------------------------------------------------------
    # Проверяем downloader.
    # --------------------------------------------------------

    print()
    print(
        "6/7: проверка downloader.py..."
    )

    try:

        compile_file(
            DOWNLOADER
        )

        validate_downloader(
            new_source
        )

    except Exception:

        print()
        print(
            "ОШИБКА: откат downloader.py..."
        )

        shutil.copy2(
            backup,
            DOWNLOADER
        )

        # Новый модуль удаляем,
        # если он был создан этим запуском.
        try:

            if os.path.exists(
                SOUNDCLOUD_MODULE
            ):

                os.remove(
                    SOUNDCLOUD_MODULE
                )

        except Exception:
            pass

        print(
            "Backup восстановлен."
        )

        raise

    # --------------------------------------------------------
    # Проверяем SoundCloud-модуль.
    # --------------------------------------------------------

    print()
    print(
        "7/7: проверка sources_soundcloud.py..."
    )

    try:

        validate_module()

    except Exception:

        print()
        print(
            "ОШИБКА: SoundCloud-модуль "
            "не прошёл проверку."
        )

        print(
            "Восстанавливаю downloader.py..."
        )

        shutil.copy2(
            backup,
            DOWNLOADER
        )

        try:

            if os.path.exists(
                SOUNDCLOUD_MODULE
            ):

                os.remove(
                    SOUNDCLOUD_MODULE
                )

        except Exception:
            pass

        print(
            "Backup восстановлен."
        )

        raise

    # --------------------------------------------------------
    # Финальная проверка.
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "ПЕРЕНОС SOUNDCLOUD УСПЕШНО ЗАВЕРШЁН"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "downloader.py:"
    )

    print(
        "  SoundCloud-функции теперь "
        "импортируются из sources_soundcloud.py."
    )

    print()
    print(
        "sources_soundcloud.py:"
    )

    print(
        "  содержит реальную рабочую "
        "SoundCloud-логику."
    )

    print()
    print(
        "Резервная копия:"
    )

    print(
        backup
    )

    print()
    print(
        "ВАЖНО:"
    )

    print(
        "Остальной downloader.py "
        "не переносился и не менялся."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print()
        print(
            "=" * 70
        )

        print(
            "ОШИБКА ПРИ ПЕРЕНОСЕ SOUNDCLOUD"
        )

        print(
            "=" * 70
        )

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        sys.exit(1)
