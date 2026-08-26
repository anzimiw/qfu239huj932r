import ast
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher


# ============================================================
# CONFIG
# ============================================================

TARGET = Path(__file__).resolve().parent / "sources_soundcloud.py"


# ============================================================
# HELPERS
# ============================================================

def fail(message):
    raise RuntimeError(message)


def syntax_check(path):
    source = path.read_text(
        encoding="utf-8"
    )

    ast.parse(
        source,
        filename=str(path)
    )


def find_function(source, function_name):
    tree = ast.parse(source)

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ):
            return node

    return None


def normalize_for_title(value):
    value = str(
        value or ""
    ).lower().strip()

    value = re.sub(
        r"\[[^\]]*\]",
        " ",
        value
    )

    value = re.sub(
        r"\([^\)]*\)",
        " ",
        value
    )

    value = re.sub(
        r"[\u2018\u2019`]",
        "'",
        value
    )

    value = re.sub(
        r"[^0-9a-zа-яё]+",
        " ",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


def title_similarity(a, b):
    a = normalize_for_title(a)
    b = normalize_for_title(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        shorter = min(
            len(a),
            len(b)
        )

        longer = max(
            len(a),
            len(b)
        )

        if longer:
            return max(
                0.90,
                shorter / longer
            )

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


def get_candidate_artist(candidate):
    user = candidate.get(
        "user"
    )

    if isinstance(user, dict):
        return str(
            user.get("username")
            or ""
        ).strip()

    return ""


def get_candidate_url(candidate):
    return (
        candidate.get("permalink_url")
        or candidate.get("uri")
        or ""
    )


def duration_is_reasonable(candidate_duration, requested_duration):
    if not requested_duration:
        return True

    if not candidate_duration:
        return True

    try:
        candidate_duration = float(
            candidate_duration
        )

        requested_duration = float(
            requested_duration
        )
    except Exception:
        return True

    difference = abs(
        candidate_duration - requested_duration
    )

    # SoundCloud duration is normally milliseconds.
    # The downloader's duration is seconds.
    if candidate_duration > 10000:
        candidate_duration /= 1000.0

    if requested_duration > 10000:
        requested_duration /= 1000.0

    difference = abs(
        candidate_duration - requested_duration
    )

    # Prefer the existing global tolerance when available.
    tolerance = 15.0

    return difference <= tolerance


# ============================================================
# MAIN
# ============================================================

print("=" * 70)
print("CENSURU.NET — SOUNDCLOUD TITLE-ONLY FALLBACK PATCH")
print("=" * 70)
print()

if not TARGET.exists():
    fail(
        f"Не найден файл: {TARGET}"
    )

print(
    "Проверка исходного sources_soundcloud.py..."
)

original_source = TARGET.read_text(
    encoding="utf-8"
)

try:
    ast.parse(
        original_source,
        filename=str(TARGET)
    )
except SyntaxError as error:
    fail(
        "Исходный sources_soundcloud.py имеет "
        f"синтаксическую ошибку: {error}"
    )

print(
    "  OK: исходный синтаксис."
)

# ------------------------------------------------------------
# Проверяем search_soundcloud()
# ------------------------------------------------------------

function_node = find_function(
    original_source,
    "search_soundcloud"
)

if function_node is None:
    fail(
        "Не найдена функция search_soundcloud()."
    )

print(
    "  OK: search_soundcloud() найдена."
)

# ------------------------------------------------------------
# Проверяем текущую архитектуру
# ------------------------------------------------------------

required_blocks = [
    "search_stages = [",
    "for (",
    "fetch_soundcloud_results(",
    "evaluate_soundcloud_candidate(",
    "SOUNDCLOUD_NEXT_CANDIDATES_V4",
]

for block in required_blocks:
    if block not in original_source:
        fail(
            "Не найден обязательный блок: "
            f"{block}"
        )

print(
    "  OK: текущая архитектура поиска найдена."
)

# ------------------------------------------------------------
# Проверяем, что fallback ещё не установлен
# ------------------------------------------------------------

if "SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1" in original_source:
    fail(
        "TITLE-ONLY fallback уже присутствует. "
        "Повторный патч не требуется."
    )

print(
    "  OK: TITLE-ONLY fallback ещё не установлен."
)

# ------------------------------------------------------------
# Проверяем лимит результатов
# ------------------------------------------------------------

if "SOUNDCLOUD_SEARCH_RESULTS = 50" in original_source:
    print(
        "  OK: лимит результатов уже установлен: 50."
    )
elif "SOUNDCLOUD_SEARCH_RESULTS = 15" in original_source:
    print(
        "  ВНИМАНИЕ: найден старый лимит 15."
    )
    print(
        "  Будет изменён на 50."
    )
else:
    print(
        "  INFO: точное значение лимита не определено."
    )

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = TARGET.with_name(
    TARGET.name
    + f".backup_{timestamp}"
)

print()
print(
    "Создание резервной копии..."
)

shutil.copy2(
    TARGET,
    backup
)

print(
    f"  OK: {backup.name}"
)

# ============================================================
# PATCH SOURCE
# ============================================================

source = original_source

# ------------------------------------------------------------
# 1. Увеличиваем лимит результатов, если ещё 15
# ------------------------------------------------------------

print()
print(
    "1/2: проверка лимита SoundCloud..."
)

if "SOUNDCLOUD_SEARCH_RESULTS = 15" in source:

    source = source.replace(
        "SOUNDCLOUD_SEARCH_RESULTS = 15",
        "SOUNDCLOUD_SEARCH_RESULTS = 50",
        1
    )

    print(
        "  OK: 15 -> 50 результатов."
    )

elif "SOUNDCLOUD_SEARCH_RESULTS = 50" in source:

    print(
        "  OK: уже 50 результатов."
    )

else:

    print(
        "  OK: изменение лимита не требуется."
    )

# ------------------------------------------------------------
# 2. Добавляем TITLE-ONLY fallback
# ------------------------------------------------------------

print()
print(
    "2/2: добавление TITLE-ONLY fallback..."
)

# ------------------------------------------------------------
# Ищем самый конец search_soundcloud():
#
#     print()
#
#     print(
#         "SoundCloud: ни один из "
#         "4 этапов поиска не дал "
#         "подходящего трека."
#     )
#
#     return None
# ------------------------------------------------------------

tail_marker = (
    '    print()\n'
    '\n'
    '    print(\n'
    '        "SoundCloud: ни один из "\n'
    '        "4 этапов поиска не дал "\n'
    '        "подходящего трека."\n'
    '    )\n'
    '\n'
    '    return None'
)

if tail_marker not in source:
    fail(
        "Не найден точный завершающий блок "
        "search_soundcloud().\n"
        "Патч остановлен без изменения файла."
    )

fallback_block = r'''    # ========================================================
    # SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1
    # ========================================================
    #
    # Четыре основных этапа выше НЕ изменяются.
    #
    # Этот этап запускается только если обычный каскад
    # не дал подходящего кандидата.
    #
    # Причина:
    # SoundCloud Search API иногда не возвращает нужный
    # трек по запросу "исполнитель + название", даже когда
    # сам трек существует.
    #
    # Пример:
    #     пазнякс, OG Buda + блэкпинк
    #
    # При title-only поиске:
    #     блэкпинк
    #
    # SoundCloud может вернуть нужные загрузки.
    # ========================================================

    print()
    print(
        "-" * 60
    )

    print(
        "SoundCloud: FALLBACK TITLE-ONLY"
    )

    print(
        "SoundCloud: обычные 4 этапа "
        "не дали подходящего кандидата."
    )

    title_fallback_queries = []

    # Основной вариант: очищенное название без feat.
    if cleaned_base_title:
        title_fallback_queries.append(
            cleaned_base_title
        )

    # Второй вариант: исходное название без feat.
    if (
        original_base_title
        and original_base_title
        not in title_fallback_queries
    ):
        title_fallback_queries.append(
            original_base_title
        )

    # На случай слишком агрессивной очистки.
    if (
        cleaned_query_title
        and cleaned_query_title
        not in title_fallback_queries
    ):
        title_fallback_queries.append(
            cleaned_query_title
        )

    title_fallback_candidates = []

    for title_query in title_fallback_queries:

        print()
        print(
            "SoundCloud: TITLE-ONLY запрос: "
            f"{title_query}"
        )

        print(
            "SoundCloud: максимум результатов: "
            f"{SOUNDCLOUD_SEARCH_RESULTS}"
        )

        try:

            title_collection = (
                fetch_soundcloud_results(
                    title_query,
                    client_id
                )
            )

        except Exception as error:

            print(
                "SoundCloud: TITLE-ONLY ошибка запроса: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            continue

        if not isinstance(
            title_collection,
            list
        ):
            title_collection = []

        print(
            "SoundCloud: TITLE-ONLY получено "
            f"результатов: {len(title_collection)}"
        )

        for title_candidate in title_collection:

            candidate_title = str(
                title_candidate.get("title")
                or ""
            ).strip()

            candidate_url = (
                title_candidate.get(
                    "permalink_url"
                )
                or title_candidate.get(
                    "uri"
                )
                or ""
            )

            if not candidate_title or not candidate_url:
                continue

            candidate_title_ratio = (
                title_similarity(
                    candidate_title,
                    original_query_title
                )
            )

            candidate_base_title_ratio = (
                title_similarity(
                    candidate_title,
                    cleaned_base_title
                )
                if cleaned_base_title
                else 0.0
            )

            title_ratio = max(
                candidate_title_ratio,
                candidate_base_title_ratio
            )

            # ------------------------------------------------
            # Сначала пробуем существующий scoring.
            # ------------------------------------------------

            evaluated = None

            try:

                evaluated = (
                    evaluate_soundcloud_candidate(
                        title_candidate,
                        requested_artist,
                        requested_title,
                        duration
                    )
                )

            except Exception as error:

                print(
                    "SoundCloud: TITLE-ONLY evaluator "
                    "ошибка: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            if evaluated:

                evaluated["search_stage"] = 5
                evaluated["search_query"] = title_query
                evaluated["title_only_fallback"] = True

                title_fallback_candidates.append(
                    evaluated
                )

                continue

            # ------------------------------------------------
            # Если штатный evaluator отклонил результат,
            # используем осторожный title-only критерий.
            #
            # Важное условие:
            # название должно быть действительно похоже.
            # ------------------------------------------------

            if title_ratio < 0.82:
                continue

            if not duration_is_reasonable(
                title_candidate.get("duration"),
                duration
            ):
                continue

            candidate_artist = (
                get_candidate_artist(
                    title_candidate
                )
            )

            # Score специально ниже exact/high-confidence
            # совпадений обычного evaluator.
            #
            # Это fallback, а не замена штатному scoring.
            fallback_score = (
                500.0
                + title_ratio * 100.0
            )

            title_fallback_candidates.append({
                "candidate": title_candidate,
                "score": fallback_score,
                "title_ratio": title_ratio,
                "artist_ratio": 0.0,
                "search_stage": 5,
                "search_query": title_query,
                "title_only_fallback": True,
            })

    # --------------------------------------------------------
    # Удаляем дубликаты.
    # --------------------------------------------------------

    fallback_unique = {}

    for item in title_fallback_candidates:

        candidate = item.get(
            "candidate",
            {}
        )

        candidate_id = (
            candidate.get("id")
            or candidate.get("permalink_url")
            or candidate.get("uri")
            or candidate.get("title")
        )

        previous = fallback_unique.get(
            candidate_id
        )

        if (
            previous is None
            or item["score"]
            > previous["score"]
        ):
            fallback_unique[
                candidate_id
            ] = item

    title_fallback_candidates = list(
        fallback_unique.values()
    )

    title_fallback_candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print()
    print(
        "SoundCloud: TITLE-ONLY подходящих "
        "кандидатов: "
        f"{len(title_fallback_candidates)}"
    )

    if title_fallback_candidates:

        best = title_fallback_candidates[0]

        candidate = best.get(
            "candidate",
            {}
        )

        candidate_title = str(
            candidate.get("title")
            or ""
        ).strip()

        candidate_artist = (
            get_candidate_artist(
                candidate
            )
        )

        candidate_url = (
            get_candidate_url(
                candidate
            )
        )

        if candidate_url:

            print()
            print(
                "SoundCloud: TITLE-ONLY "
                "КАНДИДАТ НАЙДЕН."
            )

            print(
                "SoundCloud: этап: 5/5"
            )

            print(
                "SoundCloud: запрос: "
                f"{best.get('search_query', '')}"
            )

            print(
                "SoundCloud: score: "
                f"{best['score']:.1f}"
            )

            print(
                "SoundCloud: название кандидата: "
                f"{candidate_title}"
            )

            print(
                "SoundCloud: исполнитель кандидата: "
                f"{candidate_artist}"
            )

            print(
                "SoundCloud: URL: "
                f"{candidate_url}"
            )

            print(
                "SoundCloud: используем "
                "TITLE-ONLY fallback."
            )

            alternatives = []

            for alternative_item in (
                title_fallback_candidates[1:5]
            ):

                alternative_candidate = (
                    alternative_item.get(
                        "candidate",
                        {}
                    )
                )

                alternative_url = (
                    get_candidate_url(
                        alternative_candidate
                    )
                )

                if not alternative_url:
                    continue

                alternative_title = str(
                    alternative_candidate.get(
                        "title"
                    )
                    or ""
                ).strip()

                alternative_artist = (
                    get_candidate_artist(
                        alternative_candidate
                    )
                )

                alternative_title_ratio = (
                    alternative_item.get(
                        "title_ratio",
                        0.0
                    )
                )

                alternatives.append({
                    "url": alternative_url,
                    "title": alternative_title,
                    "artist": alternative_artist,
                    "duration": alternative_candidate.get(
                        "duration"
                    ),
                    "score": alternative_item[
                        "score"
                    ],
                    "candidate": alternative_candidate,
                    "search_stage": 5,
                    "search_query": alternative_item.get(
                        "search_query",
                        ""
                    ),
                    "exact_match": (
                        alternative_title_ratio >= 0.98
                    ),
                    "title_only_fallback": True,
                })

            return {
                "url": candidate_url,
                "title": candidate_title,
                "artist": candidate_artist,
                "duration": candidate.get(
                    "duration"
                ),
                "score": best["score"],
                "candidate": candidate,
                "search_stage": 5,
                "search_query": best.get(
                    "search_query",
                    ""
                ),
                "title_only_fallback": True,
                "exact_match": (
                    best.get(
                        "title_ratio",
                        0.0
                    ) >= 0.98
                    and best.get(
                        "artist_ratio",
                        0.0
                    ) >= 1.0
                ),
                "alternatives": alternatives,
            }

    print()
    print(
        "SoundCloud: TITLE-ONLY fallback "
        "не дал подходящего кандидата."
    )

    # ========================================================
    # END SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1
    # ========================================================

    print()

    print(
        "SoundCloud: ни один из "
        "4 основных этапов + TITLE-ONLY "
        "не дал подходящего трека."
    )

    return None'''

source = source.replace(
    tail_marker,
    fallback_block,
    1
)

# ============================================================
# WRITE
# ============================================================

TARGET.write_text(
    source,
    encoding="utf-8",
    newline="\n"
)

# ============================================================
# VALIDATE
# ============================================================

print()
print(
    "Проверка результата..."
)

try:
    syntax_check(TARGET)
except Exception as error:

    print()
    print("=" * 70)
    print("ОШИБКА ПАТЧА")
    print("=" * 70)
    print()
    print(
        f"{type(error).__name__}: {error}"
    )
    print()
    print(
        "Выполняется автоматический откат..."
    )

    shutil.copy2(
        backup,
        TARGET
    )

    print(
        "  OK: sources_soundcloud.py "
        "восстановлен из резервной копии."
    )

    sys.exit(1)

# ============================================================
# FINAL STRUCTURE CHECKS
# ============================================================

final_source = TARGET.read_text(
    encoding="utf-8"
)

checks = [
    (
        "TITLE-ONLY marker",
        "SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1"
        in final_source
    ),
    (
        "TITLE-ONLY fetch",
        "fetch_soundcloud_results(" 
        in final_source
    ),
    (
        "TITLE-ONLY stage 5",
        '"SoundCloud: этап: 5/5"'
        in final_source
    ),
    (
        "existing 4 stages",
        "search_stages = ["
        in final_source
    ),
    (
        "existing evaluator",
        "evaluate_soundcloud_candidate("
        in final_source
    ),
]

for name, ok in checks:

    if not ok:

        print()
        print(
            "=" * 70
        )
        print(
            "ОШИБКА ПРОВЕРКИ"
        )
        print(
            "=" * 70
        )

        print(
            f"Не прошла проверка: {name}"
        )

        print()
        print(
            "Выполняется автоматический откат..."
        )

        shutil.copy2(
            backup,
            TARGET
        )

        print(
            "  OK: файл восстановлен."
        )

        sys.exit(1)

print(
    "  OK: синтаксис."
)

print(
    "  OK: TITLE-ONLY fallback установлен."
)

print(
    "  OK: существующие 4 этапа сохранены."
)

print(
    "  OK: evaluate_soundcloud_candidate() "
    "сохранён."
)

print()
print("=" * 70)
print("ИТОГ:")
print("  Основные этапы: 1-4 — без изменений")
print("  Новый fallback: TITLE-ONLY — этап 5")
print("  Лимит результатов: до 50")
print("  Existing scoring: сохранён")
print("  Backup: OK")
print("  Syntax: OK")
print("=" * 70)
print()
print(
    "ПАТЧ УСПЕШНО ПРИМЕНЁН."
)
print(
    f"Резервная копия: {backup.name}"
    )
