# -*- coding: utf-8 -*-

"""
CENSURU.NET — ОЧИСТКА ОБЩЕЙ ЛОГИКИ SOURCE-МОДУЛЕЙ

Этап:
    - удаление candidate_text_score() из downloader.py
    - удаление is_duration_acceptable() из downloader.py
    - сохранение normalize()
    - сохранение normalize_words()
    - сохранение clean_filename()
    - удаление недостижимого повторного return False

ВАЖНО:
    downloader.py уже использует:
        search_mp3tm
        search_audiostart

    через импорты из:
        sources_mp3tm
        sources_audiostart

    Поэтому эти функции НЕ удаляются из публичного API downloader.py.
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

DOWNLOADER = ENGINE_DIR / "downloader.py"
SOURCE_UTILS = ENGINE_DIR / "source_utils.py"

MP3PARTY = ENGINE_DIR / "sources_mp3party.py"
MP3TM = ENGINE_DIR / "sources_mp3tm.py"
AUDIOSTART = ENGINE_DIR / "sources_audiostart.py"
SOUNDCLOUD = ENGINE_DIR / "sources_soundcloud.py"


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
            )
        )
    }


def backup_file(path):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = path.with_name(
        f"{path.stem}.backup_cleanup_sources_"
        f"{timestamp}{path.suffix}"
    )

    shutil.copy2(
        path,
        backup
    )

    return backup


def remove_functions(text, names):
    """
    Удаляет верхнеуровневые функции по AST.

    Удаление производится с конца файла к началу,
    поэтому номера строк остальных функций
    не ломаются.
    """

    tree = parse(
        text,
        DOWNLOADER
    )

    functions = get_functions(
        tree
    )

    missing = [
        name
        for name in names
        if name not in functions
    ]

    if missing:
        fail(
            "В downloader.py отсутствуют "
            "функции, которые патч должен удалить:\n"
            + "\n".join(
                f"  - {name}()"
                for name in missing
            )
        )

    lines = text.splitlines(
        keepends=True
    )

    nodes = [
        functions[name]
        for name in names
    ]

    # От последней функции к первой.
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

    result = []
    blank_count = 0

    for line in "".join(lines).splitlines():

        if not line.strip():

            blank_count += 1

            if blank_count <= 2:
                result.append("")

        else:

            blank_count = 0
            result.append(line)

    return (
        "\n".join(result).rstrip()
        + "\n"
    )


def remove_duplicate_return_false(text):
    """
    Удаляет только второй подряд return False
    внутри одного блока.

    Не пытается переписывать control flow.
    """

    lines = text.splitlines(
        keepends=True
    )

    result = []

    removed = 0

    for line in lines:

        stripped = line.strip()

        if (
            stripped == "return False"
            and result
            and result[-1].strip()
            == "return False"
        ):
            removed += 1
            continue

        result.append(line)

    return "".join(result), removed


def module_has_function(
    path,
    function_name
):
    text = read_text(
        path
    )

    tree = parse(
        text,
        path
    )

    return (
        function_name
        in get_functions(tree)
    )


def module_has_import(
    path,
    module_name,
    function_name
):
    text = read_text(
        path
    )

    tree = parse(
        text,
        path
    )

    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom
        ):
            continue

        if node.module != module_name:
            continue

        for alias in node.names:

            if alias.name == function_name:
                return True

    return False


def get_called_names(path):
    """
    Возвращает имена функций/объектов,
    вызываемых внутри файла.
    """

    text = read_text(
        path
    )

    tree = parse(
        text,
        path
    )

    calls = set()

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call
        ):
            continue

        func = node.func

        if isinstance(
            func,
            ast.Name
        ):
            calls.add(
                func.id
            )

        elif isinstance(
            func,
            ast.Attribute
        ):
            calls.add(
                func.attr
            )

    return calls


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "CENSURU.NET — ОЧИСТКА SOURCE-ЛОГИКИ"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1/10
    # --------------------------------------------------------

    print()
    print(
        "1/10: проверка файлов..."
    )

    required = (
        DOWNLOADER,
        SOURCE_UTILS,
        MP3PARTY,
        MP3TM,
        AUDIOSTART,
        SOUNDCLOUD,
    )

    for path in required:

        if not path.exists():
            fail(
                f"Не найден файл:\n{path}"
            )

        print(
            f"  OK: {path.name}"
        )

    # --------------------------------------------------------
    # 2/10
    # --------------------------------------------------------

    print()
    print(
        "2/10: проверка downloader.py..."
    )

    downloader_text = read_text(
        DOWNLOADER
    )

    downloader_tree = parse(
        downloader_text,
        DOWNLOADER
    )

    downloader_functions = (
        get_functions(
            downloader_tree
        )
    )

    print(
        "  OK: синтаксис корректен"
    )

    # --------------------------------------------------------
    # 3/10
    # --------------------------------------------------------

    print()
    print(
        "3/10: проверка текущего состояния..."
    )

    mp3tm_local = (
        "search_mp3tm"
        in downloader_functions
    )

    audiostart_local = (
        "search_audiostart"
        in downloader_functions
    )

    candidate_local = (
        "candidate_text_score"
        in downloader_functions
    )

    duration_local = (
        "is_duration_acceptable"
        in downloader_functions
    )

    print(
        "  search_mp3tm() в downloader: "
        + ("ДА" if mp3tm_local else "НЕТ")
    )

    print(
        "  search_audiostart() в downloader: "
        + ("ДА" if audiostart_local else "НЕТ")
    )

    print(
        "  candidate_text_score() в downloader: "
        + ("ДА" if candidate_local else "НЕТ")
    )

    print(
        "  is_duration_acceptable() в downloader: "
        + ("ДА" if duration_local else "НЕТ")
    )

    if not candidate_local:
        fail(
            "candidate_text_score() уже отсутствует "
            "в downloader.py.\n"
            "Похоже, этот этап уже был выполнен."
        )

    if not duration_local:
        fail(
            "is_duration_acceptable() уже отсутствует "
            "в downloader.py.\n"
            "Похоже, этот этап уже был выполнен."
        )

    # --------------------------------------------------------
    # 4/10
    # --------------------------------------------------------

    print()
    print(
        "4/10: проверка source_utils.py..."
    )

    for name in (
        "candidate_text_score",
        "is_duration_acceptable",
    ):

        if not module_has_function(
            SOURCE_UTILS,
            name
        ):
            fail(
                f"{name}() отсутствует "
                "в source_utils.py."
            )

        print(
            f"  OK: {name}()"
        )

    # --------------------------------------------------------
    # 5/10
    # --------------------------------------------------------

    print()
    print(
        "5/10: проверка source-модулей..."
    )

    source_checks = (
        (
            MP3PARTY,
            "candidate_text_score",
        ),
        (
            MP3PARTY,
            "is_duration_acceptable",
        ),
        (
            MP3TM,
            "candidate_text_score",
        ),
        (
            MP3TM,
            "is_duration_acceptable",
        ),
        (
            AUDIOSTART,
            "candidate_text_score",
        ),
        (
            AUDIOSTART,
            "is_duration_acceptable",
        ),
    )

    for path, function_name in source_checks:

        if not module_has_import(
            path,
            "source_utils",
            function_name
        ):
            fail(
                f"{path.name} не импортирует "
                f"{function_name} из source_utils."
            )

        print(
            f"  OK: {path.name} → "
            f"{function_name}"
        )

    # --------------------------------------------------------
    # 6/10
    # --------------------------------------------------------

    print()
    print(
        "6/10: создание резервной копии..."
    )

    backup = backup_file(
        DOWNLOADER
    )

    print(
        f"  OK: {backup}"
    )

    # --------------------------------------------------------
    # 7/10
    # --------------------------------------------------------

    print()
    print(
        "7/10: удаление общей логики..."
    )

    modified = remove_functions(
        downloader_text,
        (
            "candidate_text_score",
            "is_duration_acceptable",
        )
    )

    print(
        "  OK: candidate_text_score() удалена"
    )

    print(
        "  OK: is_duration_acceptable() удалена"
    )

    # --------------------------------------------------------
    # 8/10
    # --------------------------------------------------------

    print()
    print(
        "8/10: очистка недостижимого кода..."
    )

    modified, removed = (
        remove_duplicate_return_false(
            modified
        )
    )

    if removed:

        print(
            "  OK: удалена "
            f"{removed} недостижимая "
            "повторная строка return False"
        )

    else:

        print(
            "  OK: дублирующего "
            "return False не найдено"
        )

    # --------------------------------------------------------
    # 9/10
    # --------------------------------------------------------

    print()
    print(
        "9/10: AST / compile проверка..."
    )

    modified_tree = parse(
        modified,
        DOWNLOADER
    )

    modified_functions = (
        get_functions(
            modified_tree
        )
    )

    if (
        "candidate_text_score"
        in modified_functions
    ):
        fail(
            "candidate_text_score() всё ещё "
            "находится в downloader.py."
        )

    if (
        "is_duration_acceptable"
        in modified_functions
    ):
        fail(
            "is_duration_acceptable() всё ещё "
            "находится в downloader.py."
        )

    # Эти функции должны остаться
    # доступными через импортированные
    # source-модули.

    required_imports = (
        (
            "sources_mp3tm",
            "search_mp3tm",
        ),
        (
            "sources_audiostart",
            "search_audiostart",
        ),
    )

    for module_name, function_name in required_imports:

        found = False

        for node in modified_tree.body:

            if not isinstance(
                node,
                ast.ImportFrom
            ):
                continue

            if node.module != module_name:
                continue

            for alias in node.names:

                if alias.name == function_name:
                    found = True

        if not found:
            fail(
                f"Отсутствует импорт "
                f"{function_name} из "
                f"{module_name}."
            )

        print(
            f"  OK: {module_name}.{function_name}"
        )

    compile(
        modified,
        str(DOWNLOADER),
        "exec"
    )

    print(
        "  OK: AST корректен"
    )

    print(
        "  OK: compile() успешен"
    )

    # --------------------------------------------------------
    # WRITE
    # --------------------------------------------------------

    write_text(
        DOWNLOADER,
        modified
    )

    # --------------------------------------------------------
    # 10/10
    # --------------------------------------------------------

    print()
    print(
        "10/10: реальная проверка import downloader..."
    )

    engine_string = str(
        ENGINE_DIR
    )

    if engine_string not in sys.path:
        sys.path.insert(
            0,
            engine_string
        )

    for module_name in (
        "downloader",
        "source_utils",
        "sources_mp3party",
        "sources_mp3tm",
        "sources_audiostart",
        "sources_soundcloud",
    ):
        sys.modules.pop(
            module_name,
            None
        )

    try:

        downloader_module = (
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
            "Backup:"
        )

        print(
            f"  {backup}"
        )

        print()
        print(
            "Изменения НЕ откатываются автоматически."
        )

        return 1

    # --------------------------------------------------------
    # API CHECK
    # --------------------------------------------------------

    required_api = (
        "search_mp3tm",
        "search_audiostart",
    )

    for function_name in required_api:

        if not hasattr(
            downloader_module,
            function_name
        ):
            fail(
                f"После импорта downloader "
                f"не содержит {function_name}()."
            )

        print(
            f"  OK: downloader.{function_name}"
        )

    # Эти функции уже не должны быть
    # локальными определениями.
    #
    # Проверяем именно AST.

    final_text = read_text(
        DOWNLOADER
    )

    final_tree = parse(
        final_text,
        DOWNLOADER
    )

    final_functions = (
        get_functions(
            final_tree
        )
    )

    for function_name in (
        "search_mp3tm",
        "search_audiostart",
    ):

        if function_name in final_functions:
            fail(
                f"{function_name}() всё ещё "
                "определена внутри downloader.py."
            )

    print(
        "  OK: search_mp3tm() "
        "не является локальной функцией"
    )

    print(
        "  OK: search_audiostart() "
        "не является локальной функцией"
    )

    print()
    print("=" * 70)
    print(
        "ГОТОВО"
    )
    print("=" * 70)

    print()
    print(
        "Удалено из downloader.py:"
    )

    print(
        "  - candidate_text_score()"
    )

    print(
        "  - is_duration_acceptable()"
    )

    print()
    print(
        "Сохранено:"
    )

    print(
        "  - normalize()"
    )

    print(
        "  - normalize_words()"
    )

    print(
        "  - clean_filename()"
    )

    print()
    print(
        "MP3TM / AudioStart продолжают "
        "экспортироваться через downloader:"
    )

    print(
        "  downloader.search_mp3tm"
    )

    print(
        "  downloader.search_audiostart"
    )

    print()
    print(
        "Резервная копия:"
    )

    print(
        f"  {backup}"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
  )
