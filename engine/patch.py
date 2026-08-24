# -*- coding: utf-8 -*-

"""
CENSURU.NET — ОБЪЕДИНЕНИЕ ОБЩЕЙ SOURCE-ЛОГИКИ

Этап:
    sources_mp3party.py
    sources_mp3tm.py
    sources_audiostart.py

переходят на общий:

    sources_utils.py

Переносимые функции:
    normalize()
    normalize_words()
    clean_filename()
    candidate_text_score()
    is_duration_acceptable()
    get_duration()

ВАЖНО:
    downloader.py НЕ изменяется.

    sources_soundcloud.py НЕ изменяется.

    Перед изменением каждого файла создаётся backup.
"""


from __future__ import annotations

import ast
import importlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ENGINE_DIR = Path(__file__).resolve().parent

SOURCE_UTILS = ENGINE_DIR / "sources_utils.py"

SOURCE_FILES = {
    "sources_mp3party.py": ENGINE_DIR / "sources_mp3party.py",
    "sources_mp3tm.py": ENGINE_DIR / "sources_mp3tm.py",
    "sources_audiostart.py": ENGINE_DIR / "sources_audiostart.py",
}


# ============================================================
# COMMON FUNCTIONS
# ============================================================

COMMON_FUNCTIONS = (
    "normalize",
    "normalize_words",
    "clean_filename",
    "candidate_text_score",
    "is_duration_acceptable",
    "get_duration",
)


# ============================================================
# HELPERS
# ============================================================

def fail(message):
    print()
    print("ОШИБКА:")
    print(message)
    print()
    raise SystemExit(1)


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
            f"Синтаксическая ошибка:\n"
            f"{path.name}\n"
            f"строка {e.lineno}\n"
            f"столбец {e.offset}\n"
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
                ast.AsyncFunctionDef,
            ),
        )
    }


def backup_file(path):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = path.with_name(
        f"{path.stem}.backup_unify_utils_"
        f"{timestamp}{path.suffix}"
    )

    shutil.copy2(
        path,
        backup,
    )

    return backup


def find_imports(tree):
    result = []

    for node in tree.body:

        if isinstance(
            node,
            ast.ImportFrom,
        ):

            names = []

            for alias in node.names:
                names.append(
                    (
                        alias.name,
                        alias.asname,
                    )
                )

            result.append(
                (
                    node.module,
                    names,
                )
            )

    return result


def has_import_from(
    tree,
    module_name,
    function_name,
):
    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if node.module != module_name:
            continue

        for alias in node.names:

            if alias.name == function_name:
                return True

    return False


def remove_function_nodes(
    text,
    names,
    path,
):
    """
    Удаляет только верхнеуровневые функции.
    """

    tree = parse(
        text,
        path,
    )

    functions = get_functions(
        tree
    )

    found = [
        name
        for name in names
        if name in functions
    ]

    if not found:
        return text, []

    lines = text.splitlines(
        keepends=True
    )

    nodes = [
        functions[name]
        for name in found
    ]

    nodes.sort(
        key=lambda node: node.lineno,
        reverse=True,
    )

    for node in nodes:

        start = node.lineno - 1
        end = node.end_lineno

        del lines[start:end]

    result = "".join(lines)

    # Сжимаем только чрезмерные пустые строки.
    cleaned = []
    blank_count = 0

    for line in result.splitlines():

        if not line.strip():

            blank_count += 1

            if blank_count <= 2:
                cleaned.append("")

        else:

            blank_count = 0
            cleaned.append(line)

    result = (
        "\n".join(cleaned).rstrip()
        + "\n"
    )

    return result, found


def add_utils_imports(
    text,
    function_names,
    path,
):
    """
    Добавляет:

        from sources_utils import ...

    после module docstring / __future__.
    """

    tree = parse(
        text,
        path,
    )

    missing = [
        name
        for name in function_names
        if not has_import_from(
            tree,
            "sources_utils",
            name,
        )
    ]

    if not missing:
        return text

    lines = text.splitlines(
        keepends=True
    )

    body = tree.body

    insert_line = 0

    # Module docstring.
    if body:

        first = body[0]

        if (
            isinstance(
                first,
                ast.Expr,
            )
            and isinstance(
                getattr(
                    first,
                    "value",
                    None,
                ),
                ast.Constant,
            )
            and isinstance(
                first.value.value,
                str,
            )
        ):
            insert_line = first.end_lineno

    # __future__ imports.
    while insert_line < len(body):

        node = body[insert_line]

        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
        ):
            insert_line = node.end_lineno
        else:
            break

    import_lines = (
        "\n"
        "from sources_utils import "
        + ", ".join(
            missing
        )
        + "\n"
    )

    lines.insert(
        insert_line,
        import_lines,
    )

    return "".join(lines)


def remove_old_utils_imports(
    text,
    path,
):
    """
    Удаляет только старые импорты:

        from source_utils import ...
        from sources_utils import ...

    для функций, которые мы контролируем.

    Затем новый единый импорт добавляется заново.
    """

    tree = parse(
        text,
        path,
    )

    lines = text.splitlines(
        keepends=True
    )

    remove_ranges = []

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

        aliases = [
            alias.name
            for alias in node.names
        ]

        if not any(
            name in COMMON_FUNCTIONS
            for name in aliases
        ):
            continue

        remove_ranges.append(
            (
                node.lineno - 1,
                node.end_lineno,
            )
        )

    for start, end in reversed(
        remove_ranges
    ):
        del lines[start:end]

    return "".join(lines)


def ensure_import_block(
    text,
    required_functions,
    path,
):
    """
    После удаления старых импортов
    добавляет один аккуратный импорт.
    """

    tree = parse(
        text,
        path,
    )

    lines = text.splitlines(
        keepends=True
    )

    body = tree.body

    insert_line = 0

    if body:

        first = body[0]

        if (
            isinstance(
                first,
                ast.Expr,
            )
            and isinstance(
                getattr(
                    first,
                    "value",
                    None,
                ),
                ast.Constant,
            )
            and isinstance(
                first.value.value,
                str,
            )
        ):
            insert_line = first.end_lineno

    while insert_line < len(body):

        node = body[insert_line]

        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
        ):
            insert_line = node.end_lineno
        else:
            break

    import_line = (
        "\nfrom sources_utils import "
        + ", ".join(
            required_functions
        )
        + "\n"
    )

    lines.insert(
        insert_line,
        import_line,
    )

    return "".join(lines)


def collect_name_usage(
    tree,
):
    """
    Собирает обращения к именам.
    """

    used = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Name,
        ):
            used.add(
                node.id
            )

    return used


def validate_source_utils():
    text = read_text(
        SOURCE_UTILS
    )

    tree = parse(
        text,
        SOURCE_UTILS,
    )

    functions = get_functions(
        tree
    )

    missing = [
        name
        for name in COMMON_FUNCTIONS
        if name not in functions
    ]

    if missing:
        fail(
            "В sources_utils.py отсутствуют:\n"
            + "\n".join(
                f"  - {name}()"
                for name in missing
            )
        )

    print(
        "  OK: sources_utils.py содержит "
        "всю общую логику"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "CENSURU.NET — ОБЪЕДИНЕНИЕ SOURCE UTILS"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1/11
    # --------------------------------------------------------

    print()
    print(
        "1/11: проверка файлов..."
    )

    if not SOURCE_UTILS.exists():
        fail(
            "Не найден sources_utils.py."
        )

    print(
        "  OK: sources_utils.py"
    )

    for name, path in SOURCE_FILES.items():

        if not path.exists():
            fail(
                f"Не найден {name}."
            )

        print(
            f"  OK: {name}"
        )

    # --------------------------------------------------------
    # 2/11
    # --------------------------------------------------------

    print()
    print(
        "2/11: проверка sources_utils.py..."
    )

    validate_source_utils()

    # --------------------------------------------------------
    # 3/11
    # --------------------------------------------------------

    print()
    print(
        "3/11: анализ source-модулей..."
    )

    source_data = {}

    for name, path in SOURCE_FILES.items():

        text = read_text(
            path
        )

        tree = parse(
            text,
            path,
        )

        functions = get_functions(
            tree
        )

        source_data[name] = {
            "text": text,
            "tree": tree,
            "functions": functions,
        }

        print(
            f"  {name}: "
            f"{len(functions)} функций"
        )

    # --------------------------------------------------------
    # 4/11
    # --------------------------------------------------------

    print()
    print(
        "4/11: определение необходимой общей логики..."
    )

    required_imports = {}

    for name, data in source_data.items():

        used = collect_name_usage(
            data["tree"]
        )

        functions = data["functions"]

        needed = []

        for function_name in COMMON_FUNCTIONS:

            if (
                function_name in functions
            ):
                needed.append(
                    function_name
                )

            elif (
                function_name in used
            ):
                needed.append(
                    function_name
                )

        # Убираем дубли.
        needed = list(
            dict.fromkeys(
                needed
            )
        )

        required_imports[name] = needed

        print(
            f"  {name}:"
        )

        if needed:

            for function_name in needed:
                print(
                    f"    → {function_name}"
                )

        else:

            print(
                "    → общей логики нет"
            )

    # --------------------------------------------------------
    # 5/11
    # --------------------------------------------------------

    print()
    print(
        "5/11: создание резервных копий..."
    )

    backups = []

    for name, path in SOURCE_FILES.items():

        backup = backup_file(
            path
        )

        backups.append(
            backup
        )

        print(
            f"  OK: {backup.name}"
        )

    # --------------------------------------------------------
    # 6/11
    # --------------------------------------------------------

    print()
    print(
        "6/11: удаление локальных копий..."
    )

    modified_files = {}

    for name, data in source_data.items():

        path = SOURCE_FILES[name]

        text = data["text"]

        local_functions = [
            function_name
            for function_name in COMMON_FUNCTIONS
            if function_name
            in data["functions"]
        ]

        if not local_functions:

            print(
                f"  {name}: локальных копий нет"
            )

            modified_files[name] = text

            continue

        modified, removed = (
            remove_function_nodes(
                text,
                local_functions,
                path,
            )
        )

        modified_files[name] = modified

        for function_name in removed:

            print(
                f"  OK: {name} → "
                f"удалена {function_name}()"
            )

    # --------------------------------------------------------
    # 7/11
    # --------------------------------------------------------

    print()
    print(
        "7/11: очистка старых импортов..."
    )

    for name in modified_files:

        path = SOURCE_FILES[name]

        modified_files[name] = (
            remove_old_utils_imports(
                modified_files[name],
                path,
            )
        )

        print(
            f"  OK: {name}"
        )

    # --------------------------------------------------------
    # 8/11
    # --------------------------------------------------------

    print()
    print(
        "8/11: добавление imports из "
        "sources_utils..."
    )

    for name in modified_files:

        path = SOURCE_FILES[name]

        needed = required_imports[name]

        if not needed:

            print(
                f"  {name}: imports не нужны"
            )

            continue

        modified_files[name] = (
            ensure_import_block(
                modified_files[name],
                needed,
                path,
            )
        )

        print(
            f"  OK: {name} → "
            "from sources_utils import ..."
        )

    # --------------------------------------------------------
    # 9/11
    # --------------------------------------------------------

    print()
    print(
        "9/11: AST / compile проверка..."
    )

    for name, text in modified_files.items():

        path = SOURCE_FILES[name]

        tree = parse(
            text,
            path,
        )

        functions = get_functions(
            tree
        )

        for function_name in COMMON_FUNCTIONS:

            if (
                function_name
                in functions
            ):
                fail(
                    f"{name}: "
                    f"{function_name}() "
                    "всё ещё определена локально."
                )

        compile(
            text,
            str(path),
            "exec",
        )

        print(
            f"  OK: {name}"
        )

    # --------------------------------------------------------
    # WRITE
    # --------------------------------------------------------

    for name, text in modified_files.items():

        write_text(
            SOURCE_FILES[name],
            text,
        )

    # --------------------------------------------------------
    # 10/11
    # --------------------------------------------------------

    print()
    print(
        "10/11: проверка реального импорта..."
    )

    engine_string = str(
        ENGINE_DIR
    )

    if engine_string not in sys.path:
        sys.path.insert(
            0,
            engine_string,
        )

    modules = (
        "sources_utils",
        "sources_mp3party",
        "sources_mp3tm",
        "sources_audiostart",
    )

    for module_name in modules:

        sys.modules.pop(
            module_name,
            None,
        )

    try:

        importlib.import_module(
            "sources_utils"
        )

        print(
            "  OK: import sources_utils"
        )

        for module_name in (
            "sources_mp3party",
            "sources_mp3tm",
            "sources_audiostart",
        ):

            module = importlib.import_module(
                module_name
            )

            print(
                f"  OK: import {module_name}"
            )

            if module_name == "sources_mp3party":

                if not hasattr(
                    module,
                    "search_mp3party",
                ):
                    fail(
                        "sources_mp3party.py "
                        "не экспортирует "
                        "search_mp3party()."
                    )

            elif module_name == "sources_mp3tm":

                if not hasattr(
                    module,
                    "search_mp3tm",
                ):
                    fail(
                        "sources_mp3tm.py "
                        "не экспортирует "
                        "search_mp3tm()."
                    )

            elif module_name == "sources_audiostart":

                if not hasattr(
                    module,
                    "search_audiostart",
                ):
                    fail(
                        "sources_audiostart.py "
                        "не экспортирует "
                        "search_audiostart()."
                    )

    except Exception as e:

        print()
        print(
            "ОШИБКА ПРИ ИМПОРТЕ SOURCE-МОДУЛЕЙ"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Резервные копии сохранены."
        )

        for backup in backups:
            print(
                f"  {backup}"
            )

        print()
        print(
            "Автоматический откат НЕ выполняется."
        )

        return 1

    # --------------------------------------------------------
    # 11/11
    # --------------------------------------------------------

    print()
    print(
        "11/11: проверка downloader..."
    )

    sys.modules.pop(
        "downloader",
        None,
    )

    try:

        downloader = (
            importlib.import_module(
                "downloader"
            )
        )

    except Exception as e:

        print()
        print(
            "ОШИБКА ПРИ ИМПОРТЕ DOWNLOADER"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print()
        print(
            "Это означает, что source-модули "
            "синтаксически корректны, "
            "но их изменение затронуло "
            "зависимость downloader.py."
        )

        print()
        print(
            "Резервные копии:"
        )

        for backup in backups:
            print(
                f"  {backup}"
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
                f"downloader не содержит "
                f"{function_name}()."
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
        "Теперь общая логика источников "
        "находится в:"
    )

    print(
        "  sources_utils.py"
    )

    print()
    print(
        "А source-модули используют её "
        "через imports."
    )

    print()
    print(
        "downloader.py не изменялся."
    )

    print()
    print(
        "Следующий этап после проверки:"
    )

    print(
        "  удалить дублирующую общую "
        "логику из downloader.py."
    )

    print()
    print(
        "Резервные копии:"
    )

    for backup in backups:
        print(
            f"  {backup}"
        )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
              )
