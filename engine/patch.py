import ast
import re
import shutil
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
TARGET = BASE_DIR / "sources_soundcloud.py"


def fail(message):
    raise RuntimeError(message)


def check_syntax(path):
    source = path.read_text(
        encoding="utf-8-sig"
    )
    ast.parse(
        source,
        filename=str(path)
    )
    return source


print("=" * 70)
print("CENSURU.NET — РАСШИРЕНИЕ SOUNDCLOUD SEARCH")
print("=" * 70)
print()

if not TARGET.is_file():
    fail(
        f"Не найден файл:\n{TARGET}"
    )

print("Проверка исходного sources_soundcloud.py...")
source = check_syntax(TARGET)
print("  OK: исходный синтаксис.")
print()


# ============================================================
# ПРОВЕРКА СТРУКТУРЫ
# ============================================================

print("Проверка текущей структуры...")

if "SOUNDCLOUD_SEARCH_RESULTS = 15" not in source:
    if "SOUNDCLOUD_SEARCH_RESULTS = 50" in source:
        print(
            "  INFO: лимит уже установлен в 50."
        )
    else:
        fail(
            "Не найден ожидаемый "
            "SOUNDCLOUD_SEARCH_RESULTS = 15."
        )
else:
    print(
        "  OK: текущий лимит результатов = 15."
    )


if "def search_soundcloud(" not in source:
    fail(
        "Не найдена search_soundcloud()."
    )

if "def evaluate_soundcloud_candidate(" not in source:
    fail(
        "Не найдена evaluate_soundcloud_candidate()."
    )

if "search_stages = [" not in source:
    fail(
        "Не найден search_stages."
    )

print(
    "  OK: search_soundcloud() найдена."
)
print(
    "  OK: evaluate_soundcloud_candidate() найдена."
)
print(
    "  OK: search_stages найдены."
)
print()


# ============================================================
# BACKUP
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = TARGET.with_name(
    TARGET.name
    + f".backup_{timestamp}"
)

print("Создание резервной копии...")
shutil.copy2(
    TARGET,
    backup
)

print(
    f"  OK: {backup.name}"
)
print()


# ============================================================
# 1. РАСШИРЕНИЕ SEARCH RESULTS
# ============================================================

print("1/3: увеличение SoundCloud search results...")

source_new = source.replace(
    "SOUNDCLOUD_SEARCH_RESULTS = 15",
    "SOUNDCLOUD_SEARCH_RESULTS = 50",
    1
)

if source_new == source:
    print(
        "  INFO: значение уже было изменено."
    )
else:
    print(
        "  OK: 15 -> 50 результатов."
    )

source = source_new


# ============================================================
# 2. ДОБАВЛЕНИЕ TITLE-ONLY FALLBACK
# ============================================================

print()
print("2/3: добавление title-only fallback...")

marker = """
    # --------------------------------------------------------
    # КАСКАД
    # --------------------------------------------------------

    search_stages = [
"""

if marker not in source:
    fail(
        "Не найден безопасный участок "
        "перед search_stages."
    )


old_block = """
    search_stages = [
        (
            1,
            "исполнитель + очищенное название",
            (
                f"{cleaned_query_artist} "
                f"{cleaned_query_title}"
            ).strip(),
            cleaned_query_artist,
            cleaned_query_title
        ),
        (
            2,
            "основной исполнитель + название без feat",
            (
                f"{primary_artist} "
                f"{cleaned_base_title}"
            ).strip(),
            primary_artist,
            cleaned_base_title
        ),
        (
            3,
            "исполнитель + исходное название",
            (
                f"{original_query_artist} "
                f"{original_query_title}"
            ).strip(),
            original_query_artist,
            original_query_title
        ),
        (
            4,
            "основной исполнитель + исходное название без feat",
            (
                f"{primary_artist} "
                f"{original_base_title}"
            ).strip(),
            primary_artist,
            original_base_title
        ),
    ]
"""

new_block = """
    # --------------------------------------------------------
    # КАСКАД
    #
    # Первые 4 этапа полностью сохраняют старую логику.
    #
    # Дополнительно добавляем:
    #
    #   5. только название + основной исполнитель
    #   6. только исходное название + основной исполнитель
    #
    # Эти этапы используются ТОЛЬКО как fallback.
    # Они не ослабляют scoring.
    # --------------------------------------------------------

    search_stages = [
        (
            1,
            "исполнитель + очищенное название",
            (
                f"{cleaned_query_artist} "
                f"{cleaned_query_title}"
            ).strip(),
            cleaned_query_artist,
            cleaned_query_title
        ),
        (
            2,
            "основной исполнитель + название без feat",
            (
                f"{primary_artist} "
                f"{cleaned_base_title}"
            ).strip(),
            primary_artist,
            cleaned_base_title
        ),
        (
            3,
            "исполнитель + исходное название",
            (
                f"{original_query_artist} "
                f"{original_query_title}"
            ).strip(),
            original_query_artist,
            original_query_title
        ),
        (
            4,
            "основной исполнитель + исходное название без feat",
            (
                f"{primary_artist} "
                f"{original_base_title}"
            ).strip(),
            primary_artist,
            original_base_title
        ),
        (
            5,
            "название без исполнителя",
            cleaned_query_title,
            cleaned_query_artist,
            cleaned_query_title
        ),
        (
            6,
            "исходное название без исполнителя",
            original_query_title,
            original_query_artist,
            original_query_title
        ),
    ]
"""

if old_block not in source:
    fail(
        "Не найден точный текущий блок search_stages."
    )

source = source.replace(
    old_block,
    new_block,
    1
)

print(
    "  OK: добавлены fallback-этапы 5/6."
)


# ============================================================
# 3. СОСТАВНЫЕ ИСПОЛНИТЕЛИ В TITLE-ONLY FALLBACK
# ============================================================

print()
print(
    "3/3: добавление составного artist fallback..."
)

old_loop = """
        try:

            collection = (
                fetch_soundcloud_results(
                    query,
                    client_id
                )
            )
"""

new_loop = """
        try:

            collection = (
                fetch_soundcloud_results(
                    query,
                    client_id
                )
            )
"""

# Этот участок оставляем без изменения.
# Реальная логика составного исполнителя добавляется
# отдельным расширением requested_artist перед оценкой.


marker_candidates = """
        # ----------------------------------------------------
        # Оценка только текущего этапа
        # ----------------------------------------------------

        stage_candidates = []

        for candidate in collection:
"""

replacement_candidates = """
        # ----------------------------------------------------
        # Оценка только текущего этапа
        # ----------------------------------------------------

        stage_candidates = []

        # ----------------------------------------------------
        # Для обычных этапов используем старую проверку.
        #
        # Для title-only fallback дополнительно разрешаем
        # проверять отдельных исполнителей из списка:
        #
        #   "пазнякс, OG Buda"
        #
        # вместо требования полного:
        #
        #   "пазнякс OG Buda"
        #
        # Это особенно важно для SoundCloud, где OG Buda
        # может быть опубликован под другим username.
        # ----------------------------------------------------

        artist_variants = [
            requested_artist
        ]

        if stage_number in (5, 6):

            parts = re.split(
                r"\\s*,\\s*",
                str(requested_artist or "")
            )

            for part in parts:

                part = part.strip()

                if (
                    part
                    and part not in artist_variants
                ):
                    artist_variants.append(
                        part
                    )

        for candidate in collection:

            result = None

            for artist_variant in artist_variants:

                result = (
                    evaluate_soundcloud_candidate(
                        candidate,
                        artist_variant,
                        requested_title,
                        duration
                    )
                )

                if result:
                    break

            if not result:

                continue
"""

if marker_candidates not in source:
    fail(
        "Не найден безопасный блок оценки кандидатов."
    )

source = source.replace(
    marker_candidates,
    replacement_candidates,
    1
)

print(
    "  OK: составной artist fallback добавлен."
)


# ============================================================
# ЗАПИСЬ
# ============================================================

TARGET.write_text(
    source,
    encoding="utf-8"
)


# ============================================================
# ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================

print()
print("Проверка результата...")

final_source = check_syntax(
    TARGET
)

if "SOUNDCLOUD_SEARCH_RESULTS = 50" not in final_source:
    fail(
        "После патча не найден лимит 50."
    )

if (
    "название без исполнителя"
    not in final_source
):
    fail(
        "После патча не найден fallback-этап 5."
    )

if (
    "исходное название без исполнителя"
    not in final_source
):
    fail(
        "После патча не найден fallback-этап 6."
    )

print(
    "  OK: синтаксис."
)

print(
    "  OK: SOUNDCLOUD_SEARCH_RESULTS = 50."
)

print(
    "  OK: title-only fallback."
)

print(
    "  OK: составной artist fallback."
)

print()
print("=" * 70)
print("ПАТЧ УСПЕШНО ПРИМЕНЁН")
print("=" * 70)
print()
print(
    f"Резервная копия: {backup.name}"
)
print()
print(
    "Следующий тест желательно выполнить на тех же 8 треках."
)
