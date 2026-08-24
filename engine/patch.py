# -*- coding: utf-8 -*-

"""
CENSURU.NET — ИСПРАВЛЕНИЕ SOURCE-МОДУЛЕЙ

Приводит:
    sources_mp3party.py
    sources_mp3tm.py
    sources_audiostart.py

к использованию общего:
    sources_utils.py

ВАЖНО:
    downloader.py НЕ изменяется.
    sources_soundcloud.py НЕ изменяется.

Перед изменением каждого source-файла
создаётся резервная копия.
"""

from __future__ import annotations

import ast
import importlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parent

UTILS_FILE = ENGINE_DIR / "sources_utils.py"

SOURCE_FILES = {
    "sources_mp3party": ENGINE_DIR / "sources_mp3party.py",
    "sources_mp3tm": ENGINE_DIR / "sources_mp3tm.py",
    "sources_audiostart": ENGINE_DIR / "sources_audiostart.py",
}


COMMON_FUNCTIONS = {
    "normalize",
    "normalize_words",
    "clean_filename",
    "candidate_text_score",
    "is_duration_acceptable",
    "get_duration",
}


def fail(message):
    print()
    print("ОШИБКА:")
    print(message)
    print()
    raise SystemExit(1)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception as e:
            fail(f"Не удалось прочитать {path.name}: {e}")


def write_text(path, text):
    path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )


def parse(text, path):
    try:
        return ast.parse(
            text,
            filename=str(path),
        )
    except SyntaxError as e:
        fail(
            f"{path.name}: синтаксическая ошибка "
            f"в строке {e.lineno}: {e.msg}"
        )


def top_level_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def get_defined_names(tree):
    names = set()

    for node in tree.body:

        if isinstance(node, ast.FunctionDef):
            names.add(node.name)

        elif isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
            ),
        ):
            targets = []

            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]

            for target in targets:

                if isinstance(target, ast.Name):
                    names.add(target.id)

    return names


def get_imported_names(tree):
    names = set()

    for node in tree.body:

        if isinstance(node, ast.Import):

            for alias in node.names:
                names.add(
                    alias.asname
                    or alias.name.split(".")[0]
                )

        elif isinstance(node, ast.ImportFrom):

            for alias in node.names:
                names.add(
                    alias.asname
                    or alias.name
                )

    return names


def get_used_names(tree):
    used = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.Name):
            used.add(node.id)

    return used


def backup(path):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = path.with_name(
        f"{path.stem}.backup_fix_source_modules_"
        f"{timestamp}{path.suffix}"
    )

    shutil.copy2(
        path,
        backup_path,
    )

    return backup_path


def remove_top_level_functions(
    text,
    path,
    function_names,
):
    tree = parse(text, path)

    functions = top_level_functions(tree)

    targets = [
        functions[name]
        for name in function_names
        if name in functions
    ]

    if not targets:
        return text, []

    lines = text.splitlines(
        keepends=True
    )

    targets.sort(
        key=lambda node: node.lineno,
        reverse=True,
    )

    removed = []

    for node in targets:

        start = node.lineno - 1
        end = node.end_lineno

        del lines[start:end]

        removed.append(node.name)

    result = "".join(lines)

    # Не оставляем огромные блоки пустых строк.
    result = result.replace(
        "\n\n\n\n\n",
        "\n\n\n",
    )

    return result, removed


def remove_old_utils_imports(
    text,
    path,
):
    tree = parse(text, path)

    lines = text.splitlines(
        keepends=True
    )

    ranges = []

    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if node.module not in (
            "source_utils",
            "sources_utils",
        ):
            continue

        controlled = any(
            alias.name in COMMON_FUNCTIONS
            for alias in node.names
        )

        if controlled:
            ranges.append(
                (
                    node.lineno - 1,
                    node.end_lineno,
                )
            )

    for start, end in reversed(ranges):
        del lines[start:end]

    return "".join(lines)


def add_utils_import(
    text,
    path,
    functions,
):
    if not functions:
        return text

    tree = parse(text, path)

    # Проверяем, нет ли уже корректного импорта.
    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if node.module != "sources_utils":
            continue

        imported = {
            alias.name
            for alias in node.names
        }

        missing = [
            name
            for name in functions
            if name not in imported
        ]

        if not missing:
            return text

    lines = text.splitlines(
        keepends=True
    )

    insert_at = 0

    body = tree.body

    # Module docstring.
    if body:

        first = body[0]

        if (
            isinstance(first, ast.Expr)
            and isinstance(
                first.value,
                ast.Constant,
            )
            and isinstance(
                first.value.value,
                str,
            )
        ):
            insert_at = first.end_lineno

    # __future__ imports.
    while insert_at < len(body):

        node = body[insert_at]

        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
        ):
            insert_at = node.end_lineno
        else:
            break

    import_line = (
        "\nfrom sources_utils import "
        + ", ".join(functions)
        + "\n"
    )

    lines.insert(
        insert_at,
        import_line,
    )

    return "".join(lines)


def add_standard_imports(
    text,
    path,
    module_name,
):
    """
    Добавляет только те стандартные/внешние импорты,
    которые реально нужны соответствующему source-модулю.
    """

    tree = parse(text, path)

    imported = get_imported_names(tree)
    used = get_used_names(tree)

    required = []

    if (
        module_name in {
            "sources_mp3party",
            "sources_mp3tm",
            "sources_audiostart",
        }
        and "requests" in used
        and "requests" not in imported
    ):
        required.append(
            "import requests"
        )

    if (
        "re" in used
        and "re" not in imported
    ):
        required.append(
            "import re"
        )

    if (
        "html" in used
        and "html" not in imported
    ):
        required.append(
            "import html"
        )

    if (
        "base64" in used
        and "base64" not in imported
    ):
        required.append(
            "import base64"
        )

    if not required:
        return text

    lines = text.splitlines(
        keepends=True
    )

    body = tree.body

    insert_at = 0

    if body:

        first = body[0]

        if (
            isinstance(first, ast.Expr)
            and isinstance(
                first.value,
                ast.Constant,
            )
            and isinstance(
                first.value.value,
                str,
            )
        ):
            insert_at = first.end_lineno

    future_end = insert_at

    while future_end < len(body):

        node = body[future_end]

        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
        ):
            insert_at = node.end_lineno
            future_end += 1
        else:
            break

    block = "\n" + "\n".join(required) + "\n"

    lines.insert(
        insert_at,
        block,
    )

    return "".join(lines)


def validate_utils():
    text = read_text(UTILS_FILE)
    tree = parse(text, UTILS_FILE)
    functions = top_level_functions(tree)

    missing = sorted(
        COMMON_FUNCTIONS
        - set(functions)
    )

    if missing:
        fail(
            "В sources_utils.py отсутствуют:\n"
            + "\n".join(
                f"  - {name}()"
                for name in missing
            )
        )

    compile(
        text,
        str(UTILS_FILE),
        "exec",
    )


def validate_source(
    module_name,
    path,
):
    text = read_text(path)
    tree = parse(text, path)

    compile(
        text,
        str(path),
        "exec",
    )

    functions = top_level_functions(tree)

    expected = {
        "sources_mp3party": "search_mp3party",
        "sources_mp3tm": "search_mp3tm",
        "sources_audiostart": "search_audiostart",
    }

    required = expected[module_name]

    if required not in functions:
        fail(
            f"{path.name}: отсутствует "
            f"{required}()"
        )


def main():

    print("=" * 70)
    print(
        "CENSURU.NET — ИСПРАВЛЕНИЕ SOURCE-МОДУЛЕЙ"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1/10
    # --------------------------------------------------------

    print()
    print(
        "1/10: проверка файлов..."
    )

    if not UTILS_FILE.exists():
        fail(
            "Не найден sources_utils.py"
        )

    for path in SOURCE_FILES.values():

        if not path.exists():
            fail(
                f"Не найден {path.name}"
            )

    print(
        "  OK: все необходимые файлы найдены"
    )

    # --------------------------------------------------------
    # 2/10
    # --------------------------------------------------------

    print()
    print(
        "2/10: проверка sources_utils.py..."
    )

    validate_utils()

    print(
        "  OK: общая логика найдена"
    )

    # --------------------------------------------------------
    # 3/10
    # --------------------------------------------------------

    print()
    print(
        "3/10: анализ source-модулей..."
    )

    source_info = {}

    for module_name, path in SOURCE_FILES.items():

        text = read_text(path)
        tree = parse(text, path)

        functions = top_level_functions(tree)

        local_common = sorted(
            COMMON_FUNCTIONS
            & set(functions)
        )

        source_info[module_name] = {
            "text": text,
            "tree": tree,
            "functions": functions,
            "local_common": local_common,
        }

        print(
            f"  {path.name}:"
        )

        if local_common:

            for name in local_common:
                print(
                    f"    локальная копия: {name}()"
                )

        else:

            print(
                "    локальных копий общей логики нет"
            )

    # --------------------------------------------------------
    # 4/10
    # --------------------------------------------------------

    print()
    print(
        "4/10: создание резервных копий..."
    )

    backups = []

    for path in SOURCE_FILES.values():

        backup_path = backup(path)
        backups.append(backup_path)

        print(
            f"  OK: {backup_path.name}"
        )

    # --------------------------------------------------------
    # 5/10
    # --------------------------------------------------------

    print()
    print(
        "5/10: удаление дублирующей логики..."
    )

    modified = {}

    for module_name, info in source_info.items():

        path = SOURCE_FILES[module_name]

        text = info["text"]

        text, removed = remove_top_level_functions(
            text,
            path,
            COMMON_FUNCTIONS,
        )

        modified[module_name] = text

        if removed:

            for name in removed:
                print(
                    f"  OK: {path.name} → "
                    f"удалена {name}()"
                )

        else:

            print(
                f"  OK: {path.name} → "
                "дублирующей логики нет"
            )

    # --------------------------------------------------------
    # 6/10
    # --------------------------------------------------------

    print()
    print(
        "6/10: исправление импортов sources_utils..."
    )

    for module_name in modified:

        path = SOURCE_FILES[module_name]

        modified[module_name] = (
            remove_old_utils_imports(
                modified[module_name],
                path,
            )
        )

        # После удаления локальных функций
        # определяем, какие общие функции
        # реально используются.
        tree = parse(
            modified[module_name],
            path,
        )

        used = get_used_names(tree)

        needed = [
            name
            for name in (
                "normalize",
                "normalize_words",
                "clean_filename",
                "candidate_text_score",
                "is_duration_acceptable",
                "get_duration",
            )
            if name in used
        ]

        modified[module_name] = add_utils_import(
            modified[module_name],
            path,
            needed,
        )

        if needed:

            print(
                f"  OK: {path.name} → "
                "sources_utils"
            )

        else:

            print(
                f"  OK: {path.name} → "
                "общий import не требуется"
            )

    # --------------------------------------------------------
    # 7/10
    # --------------------------------------------------------

    print()
    print(
        "7/10: проверка внешних импортов..."
    )

    for module_name in modified:

        path = SOURCE_FILES[module_name]

        modified[module_name] = (
            add_standard_imports(
                modified[module_name],
                path,
                module_name,
            )
        )

        print(
            f"  OK: {path.name}"
        )

    # --------------------------------------------------------
    # 8/10
    # --------------------------------------------------------

    print()
    print(
        "8/10: AST / compile..."
    )

    for module_name, text in modified.items():

        path = SOURCE_FILES[module_name]

        tree = parse(text, path)

        functions = top_level_functions(tree)

        for name in COMMON_FUNCTIONS:

            if name in functions:
                fail(
                    f"{path.name}: "
                    f"{name}() всё ещё "
                    "определена локально."
                )

        required = {
            "sources_mp3party": "search_mp3party",
            "sources_mp3tm": "search_mp3tm",
            "sources_audiostart": "search_audiostart",
        }[module_name]

        if required not in functions:
            fail(
                f"{path.name}: "
                f"{required}() потеряна."
            )

        compile(
            text,
            str(path),
            "exec",
        )

        print(
            f"  OK: {path.name}"
        )

    # --------------------------------------------------------
    # WRITE
    # --------------------------------------------------------

    for module_name, text in modified.items():

        write_text(
            SOURCE_FILES[module_name],
            text,
        )

    # --------------------------------------------------------
    # 9/10
    # --------------------------------------------------------

    print()
    print(
        "9/10: реальный import source-модулей..."
    )

    engine = str(ENGINE_DIR)

    if engine not in sys.path:
        sys.path.insert(
            0,
            engine,
        )

    modules = [
        "sources_utils",
        "sources_mp3party",
        "sources_mp3tm",
        "sources_audiostart",
    ]

    for module in modules:
        sys.modules.pop(
            module,
            None,
        )

    try:

        importlib.import_module(
            "sources_utils"
        )

        print(
            "  OK: sources_utils"
        )

        for module_name in (
            "sources_mp3party",
            "sources_mp3tm",
            "sources_audiostart",
        ):

            module = importlib.import_module(
                module_name
            )

            required = {
                "sources_mp3party": "search_mp3party",
                "sources_mp3tm": "search_mp3tm",
                "sources_audiostart": "search_audiostart",
            }[module_name]

            if not hasattr(
                module,
                required,
            ):
                fail(
                    f"{module_name}: "
                    f"{required}() отсутствует "
                    "после импорта."
                )

            print(
                f"  OK: {module_name}"
            )

    except Exception as e:

        print()
        print(
            "ОШИБКА ПРИ ИМПОРТЕ:"
        )
        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Резервные копии:"
        )

        for path in backups:
            print(
                f"  {path}"
            )

        return 1

    # --------------------------------------------------------
    # 10/10
    # --------------------------------------------------------

    print()
    print(
        "10/10: проверка downloader..."
    )

    sys.modules.pop(
        "downloader",
        None,
    )

    try:

        downloader = importlib.import_module(
            "downloader"
        )

    except Exception as e:

        print()
        print(
            "ОШИБКА: downloader.py "
            "не импортируется."
        )
        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Резервные копии source-модулей:"
        )

        for path in backups:
            print(
                f"  {path}"
            )

        return 1

    for function_name in (
        "search_mp3party",
        "search_mp3tm",
        "search_audiostart",
    ):

        if not hasattr(
            downloader,
            function_name,
        ):
            fail(
                f"downloader.{function_name} "
                "отсутствует."
            )

        print(
            f"  OK: downloader.{function_name}"
        )

    print()
    print("=" * 70)
    print(
        "ГОТОВО"
    )
    print("=" * 70)

    print()
    print(
        "Общая логика теперь находится "
        "в sources_utils.py."
    )

    print(
        "MP3Party / MP3TM / AudioStart "
        "используют общий модуль."
    )

    print(
        "downloader.py не изменён."
    )

    print(
        "sources_soundcloud.py не изменён."
    )

    print()
    print(
        "Backup-файлы:"
    )

    for path in backups:
        print(
            f"  {path}"
        )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
