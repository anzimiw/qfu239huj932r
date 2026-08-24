# -*- coding: utf-8 -*-

"""
CENSURU.NET — перенос SoundCloud utility-логики
из downloader.py в sources_soundcloud.py.

Переносит:
    clean_soundcloud_text()
    soundcloud_query_variants()
    soundcloud_candidate_score()

А также необходимые SoundCloud-константы.

Перед изменением создаётся резервная копия downloader.py
и sources_soundcloud.py.
"""

import ast
import os
import shutil
from datetime import datetime


DOWNLOADER = "downloader.py"
SOUNDCLOUD = "sources_soundcloud.py"


FUNCTIONS = [
    "clean_soundcloud_text",
    "soundcloud_query_variants",
    "soundcloud_candidate_score",
]


CONSTANTS = [
    "SOUNDCLOUD_HEADERS",
    "SOUNDCLOUD_SEARCH_URL",
    "SOUNDCLOUD_DURATION_TOLERANCE",
    "SOUNDCLOUD_SEARCH_TIMEOUT",
    "SOUNDCLOUD_SEARCH_RESULTS",
    "SOUNDCLOUD_CLIENT_ID_TIMEOUT",
    "SOUNDCLOUD_CLIENT_ID_CACHE",
    "SOUNDCLOUD_SERVICE_MODIFIERS",
]


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parse(text, filename):
    return ast.parse(text, filename=filename)


def find_top_level_nodes(tree):
    result = {}

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.Assign,
                ast.AnnAssign,
            ),
        ):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                result[node.name] = node

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        result[target.id] = node

            elif isinstance(node, ast.AnnAssign):
                if isinstance(target := node.target, ast.Name):
                    result[target.id] = node

    return result


def source_segment(source, node):
    lines = source.splitlines(keepends=True)

    start = node.lineno - 1
    end = node.end_lineno

    return "".join(lines[start:end])


def remove_nodes(source, nodes):
    lines = source.splitlines(keepends=True)

    ranges = []

    for node in nodes:
        ranges.append(
            (
                node.lineno - 1,
                node.end_lineno,
            )
        )

    for start, end in sorted(
        ranges,
        reverse=True
    ):
        del lines[start:end]

    return "".join(lines)


def find_import_from(tree, module):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == module:
                return node

    return None


def ensure_imports(source):
    tree = parse(source, SOUNDCLOUD)

    required_imports = {
        "normalize",
        "normalize_words",
    }

    existing = set()

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "sources_utils":
                for alias in node.names:
                    existing.add(alias.name)

    missing = sorted(
        required_imports - existing
    )

    if not missing:
        return source

    lines = source.splitlines(keepends=True)

    import_line = (
        "from sources_utils import "
        + ", ".join(missing)
        + "\n"
    )

    insert_at = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("#")
            or not stripped
        ):
            insert_at = i + 1
            continue

        break

    lines.insert(
        insert_at,
        import_line
    )

    return "".join(lines)


def ensure_downloader_imports(source):
    tree = parse(source, DOWNLOADER)

    required = [
        "search_soundcloud",
        "download_from_soundcloud",
    ]

    node = find_import_from(
        tree,
        "sources_soundcloud"
    )

    if node is None:
        raise RuntimeError(
            "В downloader.py отсутствует "
            "from sources_soundcloud import ..."
        )

    existing = {
        alias.name
        for alias in node.names
    }

    missing = [
        name
        for name in required
        if name not in existing
    ]

    if not missing:
        return source

    lines = source.splitlines(keepends=True)

    line_index = node.lineno - 1

    original = lines[line_index].rstrip("\n")

    if original.endswith(")"):
        # Многострочный импорт.
        for offset in range(
            line_index,
            min(
                len(lines),
                node.end_lineno
            ),
        ):
            if lines[offset].strip() == ")":
                lines.insert(
                    offset,
                    "".join(
                        f"    {name},\n"
                        for name in missing
                    )
                )
                break
    else:
        lines[line_index] = (
            original
            + ", "
            + ", ".join(missing)
            + "\n"
        )

    return "".join(lines)


def main():
    print("=" * 70)
    print("CENSURU.NET — ПЕРЕНОС SOUNDCLOUD UTILS")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # 1. Проверка файлов
    # --------------------------------------------------------

    print("1/10: проверка файлов...")

    for path in (DOWNLOADER, SOUNDCLOUD):
        if not os.path.exists(path):
            print(f"  ОШИБКА: {path} отсутствует")
            return 1

        print(f"  OK: {path}")

    # --------------------------------------------------------
    # 2. Проверка downloader
    # --------------------------------------------------------

    print()
    print("2/10: проверка downloader.py...")

    downloader = read_file(DOWNLOADER)

    try:
        downloader_tree = parse(
            downloader,
            DOWNLOADER
        )
    except SyntaxError as e:
        print(f"  ОШИБКА синтаксиса: {e}")
        return 1

    print("  OK: синтаксис корректен")

    # --------------------------------------------------------
    # 3. Поиск функций
    # --------------------------------------------------------

    print()
    print("3/10: поиск SoundCloud-функций...")

    downloader_nodes = find_top_level_nodes(
        downloader_tree
    )

    missing = [
        name
        for name in FUNCTIONS
        if name not in downloader_nodes
    ]

    if missing:
        print(
            "  ОШИБКА: не найдены:"
        )
        for name in missing:
            print(f"    - {name}()")
        return 1

    for name in FUNCTIONS:
        node = downloader_nodes[name]
        print(
            f"  OK: {name}() "
            f"(строки {node.lineno}-{node.end_lineno})"
        )

    # --------------------------------------------------------
    # 4. Проверка констант
    # --------------------------------------------------------

    print()
    print("4/10: проверка SoundCloud-констант...")

    missing_constants = [
        name
        for name in CONSTANTS
        if name not in downloader_nodes
    ]

    if missing_constants:
        print(
            "  ВНИМАНИЕ: отсутствуют в downloader.py:"
        )

        for name in missing_constants:
            print(f"    - {name}")

        print(
            "  Они будут взяты из sources_soundcloud.py "
            "только если уже существуют там."
        )

    for name in CONSTANTS:
        if name in downloader_nodes:
            print(f"  OK: {name}")

    # --------------------------------------------------------
    # 5. Проверка sources_soundcloud
    # --------------------------------------------------------

    print()
    print("5/10: проверка sources_soundcloud.py...")

    soundcloud = read_file(SOUNDCLOUD)

    try:
        soundcloud_tree = parse(
            soundcloud,
            SOUNDCLOUD
        )
    except SyntaxError as e:
        print(f"  ОШИБКА синтаксиса: {e}")
        return 1

    soundcloud_nodes = find_top_level_nodes(
        soundcloud_tree
    )

    existing_functions = [
        name
        for name in FUNCTIONS
        if name in soundcloud_nodes
    ]

    if existing_functions:
        print(
            "  ВНИМАНИЕ: функции уже существуют:"
        )

        for name in existing_functions:
            print(f"    - {name}()")

        print(
            "  Перенос будет отменён во избежание "
            "дубликатов."
        )

        return 1

    print(
        "  OK: все три функции отсутствуют, "
        "можно переносить"
    )

    # --------------------------------------------------------
    # 6. Создание backup
    # --------------------------------------------------------

    print()
    print("6/10: создание резервных копий...")

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_downloader = (
        f"downloader.backup_soundcloud_utils_"
        f"{timestamp}.py"
    )

    backup_soundcloud = (
        f"sources_soundcloud.backup_before_utils_"
        f"{timestamp}.py"
    )

    shutil.copy2(
        DOWNLOADER,
        backup_downloader
    )

    shutil.copy2(
        SOUNDCLOUD,
        backup_soundcloud
    )

    print(
        f"  OK: {os.path.abspath(backup_downloader)}"
    )

    print(
        f"  OK: {os.path.abspath(backup_soundcloud)}"
    )

    # --------------------------------------------------------
    # 7. Перенос функций
    # --------------------------------------------------------

    print()
    print("7/10: перенос SoundCloud-функций...")

    function_nodes = [
        downloader_nodes[name]
        for name in FUNCTIONS
    ]

    function_blocks = [
        source_segment(
            downloader,
            node
        ).rstrip()
        for node in function_nodes
    ]

    soundcloud = ensure_imports(
        soundcloud
    )

    soundcloud = (
        soundcloud.rstrip()
        + "\n\n\n"
        + "\n\n\n".join(function_blocks)
        + "\n"
    )

    downloader = remove_nodes(
        downloader,
        function_nodes
    )

    print("  OK: clean_soundcloud_text() перенесена")
    print("  OK: soundcloud_query_variants() перенесена")
    print("  OK: soundcloud_candidate_score() перенесена")

    # --------------------------------------------------------
    # 8. Перенос констант
    # --------------------------------------------------------

    print()
    print("8/10: проверка SoundCloud-констант...")

    soundcloud_tree = parse(
        soundcloud,
        SOUNDCLOUD
    )

    soundcloud_nodes = find_top_level_nodes(
        soundcloud_tree
    )

    constant_blocks = []

    for name in CONSTANTS:
        if name not in downloader_nodes:
            continue

        if name in soundcloud_nodes:
            print(
                f"  OK: {name} уже есть "
                "в sources_soundcloud.py"
            )
            continue

        node = downloader_nodes[name]

        constant_blocks.append(
            source_segment(
                read_file(backup_downloader),
                node
            ).rstrip()
        )

        print(
            f"  OK: {name} перенесена"
        )

    if constant_blocks:
        marker = "SOUNDCLOUD_SERVICE_MODIFIERS"

        if marker in soundcloud:
            insert_pos = soundcloud.find(
                marker
            )

            line_start = soundcloud.rfind(
                "\n",
                0,
                insert_pos
            )

            soundcloud = (
                soundcloud[:line_start]
                + "\n"
                + "\n\n".join(constant_blocks)
                + "\n"
                + soundcloud[line_start:]
            )
        else:
            soundcloud = (
                soundcloud.rstrip()
                + "\n\n\n"
                + "\n\n".join(constant_blocks)
                + "\n"
            )

    # --------------------------------------------------------
    # Удаление констант из downloader
    # --------------------------------------------------------

    downloader_tree_after_functions = parse(
        downloader,
        DOWNLOADER
    )

    nodes_after_functions = find_top_level_nodes(
        downloader_tree_after_functions
    )

    constant_nodes_to_remove = []

    for name in CONSTANTS:
        if name in nodes_after_functions:
            constant_nodes_to_remove.append(
                nodes_after_functions[name]
            )

    if constant_nodes_to_remove:
        downloader = remove_nodes(
            downloader,
            constant_nodes_to_remove
        )

    # --------------------------------------------------------
    # Убираем пустые двойные пробелы сверху
    # --------------------------------------------------------

    downloader = downloader.lstrip("\n")

    # --------------------------------------------------------
    # 9. Запись + AST
    # --------------------------------------------------------

    print()
    print("9/10: запись файлов и AST-проверка...")

    write_file(
        DOWNLOADER,
        downloader
    )

    write_file(
        SOUNDCLOUD,
        soundcloud
    )

    try:
        parse(
            downloader,
            DOWNLOADER
        )

        parse(
            soundcloud,
            SOUNDCLOUD
        )

    except SyntaxError as e:
        print(
            "  ОШИБКА: после изменения "
            f"обнаружен SyntaxError: {e}"
        )

        print(
            "  Backup-файлы сохранены."
        )

        return 1

    print("  OK: downloader.py AST корректен")
    print("  OK: sources_soundcloud.py AST корректен")

    # --------------------------------------------------------
    # 10. Реальный import
    # --------------------------------------------------------

    print()
    print("10/10: реальная проверка import...")

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import downloader; "
                "import sources_soundcloud; "
                "print('IMPORT_OK'); "
                "print('search_soundcloud:', "
                "hasattr(downloader, 'search_soundcloud')); "
                "print('download_from_soundcloud:', "
                "hasattr(downloader, 'download_from_soundcloud')); "
                "print('clean_soundcloud_text:', "
                "hasattr(downloader, 'clean_soundcloud_text')); "
                "print('soundcloud_query_variants:', "
                "hasattr(downloader, 'soundcloud_query_variants')); "
                "print('soundcloud_candidate_score:', "
                "hasattr(downloader, 'soundcloud_candidate_score')); "
                "print('SC clean in source:', "
                "hasattr(sources_soundcloud, 'clean_soundcloud_text')); "
                "print('SC variants in source:', "
                "hasattr(sources_soundcloud, 'soundcloud_query_variants')); "
                "print('SC score in source:', "
                "hasattr(sources_soundcloud, 'soundcloud_candidate_score'))"
            )
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    print(result.stdout)

    if result.returncode != 0:
        print(
            "ОШИБКА: import после изменения "
            "завершился с ошибкой."
        )

        if result.stderr:
            print(result.stderr)

        return 1

    if "IMPORT_OK" not in result.stdout:
        print(
            "ОШИБКА: IMPORT_OK не получен."
        )
        return 1

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print()
    print("Перенесено в sources_soundcloud.py:")
    print("  - clean_soundcloud_text()")
    print("  - soundcloud_query_variants()")
    print("  - soundcloud_candidate_score()")

    print()
    print("SoundCloud API-константы перенесены/оставлены")
    print("в sources_soundcloud.py.")

    print()
    print("В downloader.py сохранены:")
    print("  - search_soundcloud")
    print("  - download_from_soundcloud")

    print()
    print("Backup:")
    print(f"  {backup_downloader}")
    print(f"  {backup_soundcloud}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
