# -*- coding: utf-8 -*-

"""
CENSURU.NET — ПЕРЕНОС AUDIOSTART
PATCH v1

Переносит search_audiostart() из downloader.py
в отдельный sources_audiostart.py.

Безопасность:
- backup создаётся до изменения downloader.py;
- существующий sources_audiostart.py не перезаписывается;
- новый downloader.py сначала проверяется через AST;
- только после успешной проверки записывается на диск;
- общие функции НЕ удаляются.
"""

from __future__ import annotations

import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ENGINE_DIR = Path(__file__).resolve().parent

DOWNLOADER = ENGINE_DIR / "downloader.py"
SOURCES_AUDIOSTART = ENGINE_DIR / "sources_audiostart.py"


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
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            pass

    fail(f"Не удалось прочитать файл:\n{path}")


def write_text(path, text):
    path.write_text(
        text,
        encoding="utf-8",
        newline="\n"
    )


def parse(text, filename):
    try:
        return ast.parse(
            text,
            filename=str(filename)
        )
    except SyntaxError as e:
        fail(
            f"Синтаксическая ошибка в {filename.name}:\n"
            f"строка {e.lineno}, столбец {e.offset}\n"
            f"{e.msg}"
        )


def get_functions(tree):
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
    lines = text.splitlines(keepends=True)

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(lines[start:end])


def get_called_names(node):
    result = set()

    for child in ast.walk(node):

        if isinstance(child, ast.Call):

            if isinstance(child.func, ast.Name):
                result.add(child.func.id)

            elif isinstance(child.func, ast.Attribute):
                result.add(child.func.attr)

    return result


def get_top_level_imports(tree):
    return [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom
            )
        )
    ]


def get_import_names(node):
    result = set()

    if isinstance(node, ast.Import):

        for alias in node.names:
            result.add(
                alias.asname
                or alias.name.split(".")[0]
            )

    elif isinstance(node, ast.ImportFrom):

        for alias in node.names:
            result.add(
                alias.asname
                or alias.name
            )

    return result


def remove_function(text, node):
    lines = text.splitlines(keepends=True)

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(
        lines[:start] +
        lines[end:]
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

    return "\n".join(result).rstrip() + "\n"


# ============================================================
# SAFE IMPORT INSERTION
# ============================================================

def add_import_safely(text):

    import_line = (
        "from sources_audiostart "
        "import search_audiostart"
    )

    if import_line in text:
        return text

    tree = parse(
        text,
        DOWNLOADER
    )

    lines = text.splitlines(
        keepends=True
    )

    top_level_imports = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom
            )
        )
    ]

    if top_level_imports:

        last_import = max(
            top_level_imports,
            key=lambda node: node.end_lineno
        )

        insert_at = last_import.end_lineno

        lines.insert(
            insert_at,
            import_line + "\n"
        )

        return "".join(lines)

    # Если импортов нет — ставим после module docstring.

    insert_at = 0

    if tree.body:

        first = tree.body[0]

        if (
            isinstance(first, ast.Expr)
            and isinstance(
                getattr(first, "value", None),
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
        import_line + "\n"
    )

    return "".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("CENSURU.NET — ПЕРЕНОС AUDIOSTART")
    print("PATCH v1")
    print("=" * 70)

    # --------------------------------------------------------
    # 1
    # --------------------------------------------------------

    print()
    print("1/8: проверка downloader.py...")

    if not DOWNLOADER.exists():
        fail(
            f"Не найден downloader.py:\n"
            f"{DOWNLOADER}"
        )

    original = read_text(
        DOWNLOADER
    )

    tree = parse(
        original,
        DOWNLOADER
    )

    print(
        "  OK: синтаксис корректен"
    )

    # --------------------------------------------------------
    # 2
    # --------------------------------------------------------

    print()
    print("2/8: поиск search_audiostart()...")

    functions = get_functions(
        tree
    )

    if "search_audiostart" not in functions:

        fail(
            "search_audiostart() "
            "не найдена в downloader.py.\n\n"
            "Файл не изменён."
        )

    search_node = functions[
        "search_audiostart"
    ]

    print(
        "  OK: search_audiostart() найдена "
        f"(строки "
        f"{search_node.lineno}-"
        f"{search_node.end_lineno})"
    )

    # --------------------------------------------------------
    # 3
    # --------------------------------------------------------

    print()
    print("3/8: анализ search_audiostart()...")

    search_source = get_function_source(
        original,
        search_node
    )

    calls = get_called_names(
        search_node
    )

    print(
        "  OK: функция содержит "
        "AudioStart-специфичную логику"
    )

    print(
        f"  Найдено вызываемых имён: "
        f"{len(calls)}"
    )

    # --------------------------------------------------------
    # 4
    # --------------------------------------------------------

    print()
    print("4/8: проверка sources_audiostart.py...")

    if SOURCES_AUDIOSTART.exists():

        existing = read_text(
            SOURCES_AUDIOSTART
        )

        existing_tree = parse(
            existing,
            SOURCES_AUDIOSTART
        )

        existing_functions = get_functions(
            existing_tree
        )

        if "search_audiostart" in existing_functions:

            fail(
                "sources_audiostart.py уже содержит "
                "search_audiostart().\n\n"
                "Возможно, AudioStart уже вынесен."
            )

        print(
            "  ВНИМАНИЕ: sources_audiostart.py "
            "уже существует."
        )

        print(
            "  search_audiostart() в нём не найдена."
        )

        print(
            "  Для безопасности перенос отменён."
        )

        print(
            "  Если это пустая заготовка — "
            "удали её и запусти патч повторно."
        )

        return 1

    print(
        "  OK: файл отсутствует, "
        "можно создать"
    )

    # --------------------------------------------------------
    # 5
    # --------------------------------------------------------

    print()
    print("5/8: создание резервной копии...")

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = ENGINE_DIR / (
        "downloader.py.backup_audiostart_"
        f"{timestamp}"
    )

    shutil.copy2(
        DOWNLOADER,
        backup
    )

    print(
        "  OK: резервная копия создана:"
    )

    print(
        f"  {backup}"
    )

    # --------------------------------------------------------
    # 6
    # --------------------------------------------------------

    print()
    print(
        "6/8: создание sources_audiostart.py..."
    )

    imports = get_top_level_imports(
        tree
    )

    used_names = set(calls)

    required_imports = []

    for node in imports:

        names = get_import_names(
            node
        )

        if names & used_names:

            text = ast.unparse(
                node
            )

            if text not in required_imports:
                required_imports.append(
                    text
                )

    # Общие функции НЕ удаляем из downloader.py.
    #
    # Если search_audiostart() использует их,
    # переносим их копию в модуль.
    #
    # Позже, после разделения всех источников,
    # проведём отдельную чистку.

    shared_functions = {
        "normalize",
        "normalize_words",
        "candidate_text_score",
        "is_duration_acceptable",
    }

    needed_shared = []

    for name in shared_functions:

        if (
            name in calls
            and name in functions
        ):
            needed_shared.append(
                name
            )

    module = []

    module.append(
        "# -*- coding: utf-8 -*-"
    )

    module.append("")
    module.append('"""')
    module.append(
        "CENSURU.NET — ИСТОЧНИК AUDIOSTART"
    )
    module.append("")
    module.append(
        "Поиск и выбор треков AudioStart."
    )
    module.append("")
    module.append(
        "Логика вынесена из downloader.py."
    )
    module.append('"""')
    module.append("")

    # --------------------------------------------------------
    # IMPORTS
    # --------------------------------------------------------

    if required_imports:

        module.extend(
            required_imports
        )

        module.append("")

    # --------------------------------------------------------
    # SHARED
    # --------------------------------------------------------

    if needed_shared:

        module.append(
            "# ============================================================"
        )

        module.append(
            "# ОБЩИЕ ФУНКЦИИ, НЕОБХОДИМЫЕ AUDIOSTART"
        )

        module.append(
            "# ============================================================"
        )

        module.append("")

        for name in needed_shared:

            node = functions[name]

            module.append(
                get_function_source(
                    original,
                    node
                ).rstrip()
            )

            module.append("")

    # --------------------------------------------------------
    # AUDIOSTART
    # --------------------------------------------------------

    module.append(
        "# ============================================================"
    )

    module.append(
        "# AUDIOSTART SEARCH"
    )

    module.append(
        "# ============================================================"
    )

    module.append("")

    module.append(
        search_source.rstrip()
    )

    module.append("")

    source_text = clean_blank_lines(
        "\n".join(module)
    )

    # Обязательная проверка ДО записи.

    parse(
        source_text,
        SOURCES_AUDIOSTART
    )

    write_text(
        SOURCES_AUDIOSTART,
        source_text
    )

    print(
        "  OK: sources_audiostart.py создан"
    )

    print(
        "  OK: синтаксис корректен"
    )

    # --------------------------------------------------------
    # 7
    # --------------------------------------------------------

    print()
    print(
        "7/8: изменение downloader.py..."
    )

    modified = remove_function(
        original,
        search_node
    )

    modified = clean_blank_lines(
        modified
    )

    # Добавляем импорт только после
    # верхнеуровневых импортов.

    modified = add_import_safely(
        modified
    )

    # --------------------------------------------------------
    # ПРОВЕРКА ДО ЗАПИСИ
    # --------------------------------------------------------

    try:

        modified_tree = ast.parse(
            modified,
            filename=str(DOWNLOADER)
        )

    except SyntaxError as e:

        print()
        print(
            "КРИТИЧЕСКАЯ ОШИБКА:"
        )

        print(
            f"строка {e.lineno}: {e.msg}"
        )

        print()
        print(
            "downloader.py НЕ перезаписан."
        )

        print(
            f"Backup:\n{backup}"
        )

        if SOURCES_AUDIOSTART.exists():
            SOURCES_AUDIOSTART.unlink()

        return 1

    modified_functions = get_functions(
        modified_tree
    )

    if "search_audiostart" in modified_functions:

        print(
            "ОШИБКА: search_audiostart() "
            "не была удалена."
        )

        print(
            f"Backup:\n{backup}"
        )

        return 1

    import_line = (
        "from sources_audiostart "
        "import search_audiostart"
    )

    if import_line not in modified:

        print(
            "ОШИБКА: импорт sources_audiostart "
            "не добавлен."
        )

        print(
            f"Backup:\n{backup}"
        )

        return 1

    # Только теперь записываем.

    write_text(
        DOWNLOADER,
        modified
    )

    print(
        "  OK: search_audiostart() удалена"
    )

    print(
        "  OK: импорт добавлен"
    )

    print(
        "  OK: downloader.py записан"
    )

    # --------------------------------------------------------
    # 8
    # --------------------------------------------------------

    print()
    print(
        "8/8: финальная проверка..."
    )

    final_downloader = read_text(
        DOWNLOADER
    )

    final_source = read_text(
        SOURCES_AUDIOSTART
    )

    final_downloader_tree = parse(
        final_downloader,
        DOWNLOADER
    )

    final_source_tree = parse(
        final_source,
        SOURCES_AUDIOSTART
    )

    final_downloader_functions = get_functions(
        final_downloader_tree
    )

    final_source_functions = get_functions(
        final_source_tree
    )

    # --------------------------------------------------------
    # Проверка функции
    # --------------------------------------------------------

    if (
        "search_audiostart"
        in final_downloader_functions
    ):

        fail(
            "search_audiostart() всё ещё "
            "находится в downloader.py."
        )

    print(
        "  OK: search_audiostart() отсутствует "
        "в downloader.py"
    )

    if (
        "search_audiostart"
        not in final_source_functions
    ):

        fail(
            "search_audiostart() отсутствует "
            "в sources_audiostart.py."
        )

    print(
        "  OK: search_audiostart() находится "
        "в sources_audiostart.py"
    )

    # --------------------------------------------------------
    # Проверка импорта
    # --------------------------------------------------------

    if (
        "from sources_audiostart "
        "import search_audiostart"
        not in final_downloader
    ):

        fail(
            "Импорт search_audiostart "
            "не найден."
        )

    print(
        "  OK: импорт search_audiostart присутствует"
    )

    # --------------------------------------------------------
    # Циклический импорт
    # --------------------------------------------------------

    for line in final_source.splitlines():

        stripped = line.strip()

        if (
            stripped == "import downloader"
            or stripped.startswith(
                "from downloader import"
            )
        ):

            fail(
                "sources_audiostart.py "
                "импортирует downloader.py."
            )

    print(
        "  OK: циклической зависимости нет"
    )

    # --------------------------------------------------------
    # compile()
    # --------------------------------------------------------

    compile(
        final_downloader,
        str(DOWNLOADER),
        "exec"
    )

    compile(
        final_source,
        str(SOURCES_AUDIOSTART),
        "exec"
    )

    print(
        "  OK: compile() обоих файлов успешен"
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "AUDIOSTART УСПЕШНО ВЫНЕСЕН"
    )
    print("=" * 70)

    print()
    print(
        "Создан:"
    )

    print(
        f"  {SOURCES_AUDIOSTART}"
    )

    print()
    print(
        "Изменён:"
    )

    print(
        f"  {DOWNLOADER}"
    )

    print()
    print(
        "Backup:"
    )

    print(
        f"  {backup}"
    )

    print()
    print(
        "Текущая структура:"
    )

    print()
    print(
        "  downloader.py"
    )

    print(
        "       │"
    )

    print(
        "       ├── SoundCloud"
    )

    print(
        "       │       ↓"
    )

    print(
        "       │   sources_soundcloud.py"
    )

    print(
        "       │"
    )

    print(
        "       ├── MP3Party"
    )

    print(
        "       │       ↓"
    )

    print(
        "       │   sources_mp3party.py"
    )

    print(
        "       │"
    )

    print(
        "       ├── MP3TM"
    )

    print(
        "       │       ↓"
    )

    print(
        "       │   sources_mp3tm.py"
    )

    print(
        "       │"
    )

    print(
        "       └── AudioStart"
    )

    print(
        "               ↓"
    )

    print(
        "           sources_audiostart.py"
    )

    print()
    print(
        "Общие функции пока не удалялись."
    )

    print(
        "Их разберём отдельным этапом."
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
