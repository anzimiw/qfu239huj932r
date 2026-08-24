# -*- coding: utf-8 -*-

"""
CENSURU.NET — ИСПРАВЛЕНИЕ ЗАВИСИМОСТЕЙ SOURCE-МОДУЛЕЙ

Этап:
    1. Создание source_utils.py
    2. Перенос общей логики:
         normalize()
         normalize_words()
         candidate_text_score()
         is_duration_acceptable()
         clean_filename()
         get_duration()
    3. Подключение source_utils.py к:
         sources_mp3party.py
         sources_mp3tm.py
         sources_audiostart.py
    4. Удаление дублирующихся локальных копий
    5. Проверка AST
    6. Проверка compile()
    7. Проверка реального импорта всех source-модулей

ВАЖНО:
    downloader.py НЕ изменяется.
"""

from __future__ import annotations

import ast
import importlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ENGINE_DIR = Path(__file__).resolve().parent

DOWNLOADER = ENGINE_DIR / "downloader.py"

SOURCE_UTILS = ENGINE_DIR / "source_utils.py"

MP3PARTY = ENGINE_DIR / "sources_mp3party.py"
MP3TM = ENGINE_DIR / "sources_mp3tm.py"
AUDIOSTART = ENGINE_DIR / "sources_audiostart.py"

SOURCE_FILES = (
    MP3PARTY,
    MP3TM,
    AUDIOSTART,
)


# ============================================================
# HELPERS
# ============================================================

def fail(message):
    print()
    print("ОШИБКА:")
    print(message)
    print()
    sys.exit(1)


def read_text(path):
    for encoding in (
        "utf-8",
        "utf-8-sig",
        "cp1251",
    ):
        try:
            return path.read_text(
                encoding=encoding
            )
        except UnicodeDecodeError:
            continue

    fail(
        f"Не удалось прочитать файл:\n{path}"
    )


def write_text(path, text):
    path.write_text(
        text,
        encoding="utf-8",
        newline="\n"
    )


def parse(text, path):
    try:
        return ast.parse(
            text,
            filename=str(path)
        )
    except SyntaxError as e:
        fail(
            f"Синтаксическая ошибка:\n"
            f"{path.name}\n"
            f"строка {e.lineno}, "
            f"столбец {e.offset}\n"
            f"{e.msg}"
        )


def get_top_level_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        )
    }


def get_function_source(text, node):
    lines = text.splitlines(
        keepends=True
    )

    return "".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def remove_top_level_function(
    text,
    node
):
    lines = text.splitlines(
        keepends=True
    )

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(
        lines[:start]
        + lines[end:]
    )


def clean_blank_lines(text):
    lines = text.splitlines()

    result = []
    blank_count = 0

    for line in lines:

        if not line.strip():

            blank_count += 1

            if blank_count <= 2:
                result.append("")

        else:

            blank_count = 0
            result.append(line)

    return "\n".join(
        result
    ).rstrip() + "\n"


def backup_file(path, suffix):
    if not path.exists():
        fail(
            f"Файл не найден:\n{path}"
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = path.with_name(
        f"{path.stem}.backup_{suffix}_{timestamp}"
        f"{path.suffix}"
    )

    shutil.copy2(
        path,
        backup
    )

    return backup


# ============================================================
# SOURCE UTILS
# ============================================================

SOURCE_UTILS_TEXT = r'''# -*- coding: utf-8 -*-

"""
CENSURU.NET — ОБЩИЕ ФУНКЦИИ ИСТОЧНИКОВ

Общая логика для:
    sources_mp3party.py
    sources_mp3tm.py
    sources_audiostart.py

Источник-специфичная логика поиска находится
в соответствующем sources_*.py.
"""

import html
import os
import re
import subprocess

from urllib.parse import unquote


# ============================================================
# PATHS
# ============================================================

ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)


# ============================================================
# SETTINGS
# ============================================================

DURATION_TOLERANCE = 3.0


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    text = html.unescape(
        str(text)
    )

    text = unquote(
        text
    )

    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
        .replace("_", " ")
    )

    text = re.sub(
        r"\(MP3\.tm\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\(audiostart\.net\)",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.lower()

    text = re.sub(
        r"\bof\s+buda\b",
        "og buda",
        text
    )

    text = re.sub(
        r"\bfeaturing\b",
        "feat",
        text
    )

    text = re.sub(
        r"\bft\.?\b",
        "feat",
        text
    )

    text = re.sub(
        r"\bfeat\.?\b",
        " ",
        text
    )

    text = re.sub(
        r"[,;|/\\]+",
        " ",
        text
    )

    text = re.sub(
        r"[()[\]{}]",
        " ",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def normalize_words(text):
    return {
        word
        for word in normalize(text).split()
        if word
    }


# ============================================================
# FILENAME
# ============================================================

def clean_filename(text):
    text = unquote(
        text
    )

    text = re.sub(
        r"\(MP3\.tm\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.replace(
        "_",
        " "
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================================
# CANDIDATE SCORING
# ============================================================

def candidate_text_score(
    filename,
    artist,
    title
):
    """
    Общая оценка кандидата для:

        MP3Party
        MP3TM
        AudioStart

    SoundCloud использует отдельную
    soundcloud_candidate_score().
    """

    candidate = normalize(
        filename
    )

    wanted_artist = normalize(
        artist
    )

    wanted_title = normalize(
        title
    )

    candidate_words = normalize_words(
        candidate
    )

    artist_words = normalize_words(
        wanted_artist
    )

    title_words = normalize_words(
        wanted_title
    )

    if (
        not artist_words
        or not title_words
    ):
        return -100000

    artist_ratio = (
        len(
            artist_words
            & candidate_words
        )
        / len(artist_words)
    )

    title_ratio = (
        len(
            title_words
            & candidate_words
        )
        / len(title_words)
    )

    if (
        artist_ratio < 0.5
        or title_ratio < 0.5
    ):
        return -100000

    score = 0

    score += (
        500
        if artist_ratio == 1
        else 300
        if artist_ratio >= 0.75
        else 100
    )

    score += (
        500
        if title_ratio == 1
        else 300
        if title_ratio >= 0.75
        else 100
    )

    if wanted_title in candidate:
        score += 250

    if wanted_artist in candidate:
        score += 250

    if (
        wanted_artist
        + " "
        + wanted_title
        in candidate
    ):
        score += 400

    if (
        wanted_title
        + " "
        + wanted_artist
        in candidate
    ):
        score += 350

    score -= (
        len(
            candidate_words
            - (
                artist_words
                | title_words
            )
        )
        * 15
    )

    return score


# ============================================================
# DURATION
# ============================================================

def is_duration_acceptable(
    candidate_duration,
    target_duration,
    tolerance=DURATION_TOLERANCE
):
    if (
        candidate_duration is None
        or target_duration is None
    ):
        return True

    return (
        abs(
            candidate_duration
            - target_duration
        )
        <= tolerance
    )


def get_duration(url):
    try:

        result = subprocess.run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                url
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

        if (
            result.returncode == 0
            and result.stdout.strip()
        ):
            return float(
                result.stdout.strip()
            )

    except Exception:
        pass

    return None
'''


# ============================================================
# SOURCE-SPECIFIC FUNCTIONS
# ============================================================

COMMON_FUNCTIONS = {
    "normalize",
    "normalize_words",
    "clean_filename",
    "candidate_text_score",
    "is_duration_acceptable",
    "get_duration",
}


def validate_downloader_common_functions():
    text = read_text(
        DOWNLOADER
    )

    tree = parse(
        text,
        DOWNLOADER
    )

    functions = get_top_level_functions(
        tree
    )

    missing = []

    for name in (
        "normalize",
        "normalize_words",
        "candidate_text_score",
        "is_duration_acceptable",
        "clean_filename",
    ):

        if name not in functions:
            missing.append(name)

    if missing:

        fail(
            "В downloader.py отсутствуют "
            "ожидаемые общие функции:\n"
            + "\n".join(
                f"  - {name}"
                for name in missing
            )
        )

    print(
        "  OK: общие функции найдены "
        "в downloader.py"
    )


def update_source_file(
    path,
    import_names
):
    text = read_text(
        path
    )

    tree = parse(
        text,
        path
    )

    functions = get_top_level_functions(
        tree
    )

    # Проверяем, что функции существуют
    # и действительно являются верхнеуровневыми.

    present = [
        name
        for name in import_names
        if name in functions
    ]

    # Удаляем только функции, которые
    # действительно находятся в этом source-файле.

    modified = text

    for name in sorted(
        present,
        key=lambda value:
        functions[value].lineno,
        reverse=True
    ):

        # После предыдущего удаления AST-координаты
        # становятся неактуальными.
        #
        # Поэтому для каждого удаления заново парсим
        # текущий текст.

        current_tree = parse(
            modified,
            path
        )

        current_functions = (
            get_top_level_functions(
                current_tree
            )
        )

        if name not in current_functions:
            continue

        modified = remove_top_level_function(
            modified,
            current_functions[name]
        )

        modified = clean_blank_lines(
            modified
        )

    # --------------------------------------------------------
    # IMPORT
    # --------------------------------------------------------

    import_line = (
        "from source_utils import (\n"
        + "\n".join(
            f"    {name},"
            for name in import_names
        )
        + "\n)"
    )

    if (
        "from source_utils import"
        not in modified
    ):

        current_tree = parse(
            modified,
            path
        )

        lines = modified.splitlines(
            keepends=True
        )

        # Ищем начало файла после docstring.
        insert_at = 0

        if current_tree.body:

            first = current_tree.body[0]

            if (
                isinstance(
                    first,
                    ast.Expr
                )
                and isinstance(
                    getattr(
                        first,
                        "value",
                        None
                    ),
                    ast.Constant
                )
                and isinstance(
                    first.value.value,
                    str
                )
            ):
                insert_at = first.end_lineno

        lines.insert(
            insert_at,
            "\n"
            + import_line
            + "\n"
        )

        modified = "".join(
            lines
        )

    else:

        # Уже существующий импорт source_utils
        # оставляем как есть.
        pass

    modified = clean_blank_lines(
        modified
    )

    # Финальная AST-проверка.
    parse(
        modified,
        path
    )

    write_text(
        path,
        modified
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "CENSURU.NET — ИСПРАВЛЕНИЕ SOURCE-МОДУЛЕЙ"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1/8
    # --------------------------------------------------------

    print()
    print(
        "1/8: проверка downloader.py..."
    )

    if not DOWNLOADER.exists():
        fail(
            "downloader.py не найден."
        )

    downloader_text = read_text(
        DOWNLOADER
    )

    parse(
        downloader_text,
        DOWNLOADER
    )

    print(
        "  OK: синтаксис корректен"
    )

    # --------------------------------------------------------
    # 2/8
    # --------------------------------------------------------

    print()
    print(
        "2/8: проверка общих функций..."
    )

    validate_downloader_common_functions()

    # --------------------------------------------------------
    # 3/8
    # --------------------------------------------------------

    print()
    print(
        "3/8: проверка source-модулей..."
    )

    for path in SOURCE_FILES:

        if not path.exists():
            fail(
                f"Не найден:\n{path}"
            )

        parse(
            read_text(path),
            path
        )

        print(
            f"  OK: {path.name}"
        )

    # --------------------------------------------------------
    # 4/8
    # --------------------------------------------------------

    print()
    print(
        "4/8: создание резервных копий..."
    )

    backups = []

    # Важно:
    # downloader.py НЕ меняется, поэтому backup ему
    # на этом этапе не нужен.

    for path in SOURCE_FILES:

        backup = backup_file(
            path,
            "source_deps"
        )

        backups.append(
            backup
        )

        print(
            f"  OK: {backup.name}"
        )

    if SOURCE_UTILS.exists():

        backup = backup_file(
            SOURCE_UTILS,
            "source_deps_old"
        )

        backups.append(
            backup
        )

        print(
            f"  OK: {backup.name}"
        )

    # --------------------------------------------------------
    # 5/8
    # --------------------------------------------------------

    print()
    print(
        "5/8: создание source_utils.py..."
    )

    source_utils_tree = parse(
        SOURCE_UTILS_TEXT,
        SOURCE_UTILS
    )

    source_utils_functions = (
        get_top_level_functions(
            source_utils_tree
        )
    )

    for name in COMMON_FUNCTIONS:

        if name not in source_utils_functions:

            fail(
                "В новой source_utils.py "
                f"отсутствует {name}()."
            )

    write_text(
        SOURCE_UTILS,
        SOURCE_UTILS_TEXT
    )

    print(
        "  OK: source_utils.py создан"
    )

    print(
        "  OK: все общие функции присутствуют"
    )

    # --------------------------------------------------------
    # 6/8
    # --------------------------------------------------------

    print()
    print(
        "6/8: подключение source_utils..."
    )

    # MP3Party:
    # normalize
    # normalize_words
    # candidate_text_score
    # is_duration_acceptable
    # get_duration

    update_source_file(
        MP3PARTY,
        (
            "normalize",
            "normalize_words",
            "candidate_text_score",
            "is_duration_acceptable",
            "get_duration",
        )
    )

    print(
        "  OK: sources_mp3party.py"
    )

    # MP3TM:
    # normalize
    # normalize_words
    # clean_filename
    # candidate_text_score
    # is_duration_acceptable
    # get_duration

    update_source_file(
        MP3TM,
        (
            "normalize",
            "normalize_words",
            "clean_filename",
            "candidate_text_score",
            "is_duration_acceptable",
            "get_duration",
        )
    )

    print(
        "  OK: sources_mp3tm.py"
    )

    # AudioStart:
    # normalize
    # normalize_words
    # candidate_text_score
    # is_duration_acceptable
    # get_duration

    update_source_file(
        AUDIOSTART,
        (
            "normalize",
            "normalize_words",
            "candidate_text_score",
            "is_duration_acceptable",
            "get_duration",
        )
    )

    print(
        "  OK: sources_audiostart.py"
    )

    # --------------------------------------------------------
    # 7/8
    # --------------------------------------------------------

    print()
    print(
        "7/8: AST / compile проверка..."
    )

    paths_to_check = (
        SOURCE_UTILS,
        MP3PARTY,
        MP3TM,
        AUDIOSTART,
    )

    for path in paths_to_check:

        text = read_text(
            path
        )

        parse(
            text,
            path
        )

        compile(
            text,
            str(path),
            "exec"
        )

        print(
            f"  OK: {path.name}"
        )

    # downloader.py тоже проверяем,
    # но НЕ изменяем.

    compile(
        downloader_text,
        str(DOWNLOADER),
        "exec"
    )

    print(
        "  OK: downloader.py "
        "(не изменён)"
    )

    # --------------------------------------------------------
    # 8/8
    # --------------------------------------------------------

    print()
    print(
        "8/8: проверка реального импорта..."
    )

    # engine должен быть в sys.path.
    engine_string = str(
        ENGINE_DIR
    )

    if engine_string not in sys.path:
        sys.path.insert(
            0,
            engine_string
        )

    modules = (
        "source_utils",
        "sources_mp3party",
        "sources_mp3tm",
        "sources_audiostart",
        "sources_soundcloud",
    )

    for module_name in modules:

        # Если модуль уже был загружен,
        # удаляем его из sys.modules, чтобы
        # проверить именно текущий файл.

        if module_name in sys.modules:
            del sys.modules[
                module_name
            ]

        try:

            importlib.import_module(
                module_name
            )

        except Exception as e:

            print()
            print(
                f"  ОШИБКА ИМПОРТА: "
                f"{module_name}"
            )

            print(
                f"  {type(e).__name__}: {e}"
            )

            print()
            print(
                "Изменения source-модулей "
                "НЕ откатываются автоматически."
            )

            print(
                "Backup-файлы созданы перед изменением."
            )

            print()

            for backup in backups:
                print(
                    f"  {backup}"
                )

            return 1

        print(
            f"  OK: import {module_name}"
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "SOURCE-МОДУЛИ УСПЕШНО ПОДГОТОВЛЕНЫ"
    )
    print("=" * 70)

    print()
    print(
        "Создан:"
    )

    print(
        f"  {SOURCE_UTILS}"
    )

    print()
    print(
        "Исправлены:"
    )

    print(
        f"  {MP3PARTY}"
    )

    print(
        f"  {MP3TM}"
    )

    print(
        f"  {AUDIOSTART}"
    )

    print()
    print(
        "НЕ изменён:"
    )

    print(
        f"  {DOWNLOADER}"
    )

    print()
    print(
        "Общая логика теперь находится в:"
    )

    print(
        "  source_utils.py"
    )

    print()
    print(
        "Проверены реальные импорты:"
    )

    for module_name in modules:
        print(
            f"  - {module_name}"
        )

    print()
    print(
        "Следующий этап — удаление старых "
        "search_mp3tm() и search_audiostart() "
        "из downloader.py."
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
)
