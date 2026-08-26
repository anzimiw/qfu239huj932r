import ast
import re
import shutil
from datetime import datetime
from pathlib import Path


FILE = Path(__file__).with_name("sources_soundcloud.py")


def fail(message):
    raise RuntimeError(message)


def read_source():
    try:
        return FILE.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return FILE.read_text(
            encoding="utf-8-sig"
        )


def write_source(text):
    FILE.write_text(
        text,
        encoding="utf-8"
    )


def check_syntax(text):
    ast.parse(
        text,
        filename=str(FILE)
    )


print("=" * 70)
print("CENSURU.NET — FIX SOUNDCloud TITLE-ONLY")
print("=" * 70)
print()

if not FILE.exists():
    fail(
        f"Файл не найден: {FILE}"
    )

source = read_source()

print("Проверка исходного sources_soundcloud.py...")

try:
    check_syntax(source)
except SyntaxError as error:
    fail(
        f"Исходный файл содержит SyntaxError: {error}"
    )

print("  OK: исходный синтаксис.")

if "def search_soundcloud(" not in source:
    fail(
        "Не найдена search_soundcloud()."
    )

if "TITLE-ONLY" not in source:
    fail(
        "Не найден существующий TITLE-ONLY fallback."
    )

if "title_similarity" not in source:
    fail(
        "В файле вообще отсутствует title_similarity. "
        "Ожидался существующий вызов внутри TITLE-ONLY."
    )

print(
    "  OK: search_soundcloud() найдена."
)

print(
    "  OK: TITLE-ONLY fallback найден."
)

# ------------------------------------------------------------
# Находим границы search_soundcloud()
# ------------------------------------------------------------

tree = ast.parse(
    source,
    filename=str(FILE)
)

search_node = None

for node in tree.body:

    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "search_soundcloud"
    ):
        search_node = node
        break

if search_node is None:
    fail(
        "Не удалось определить AST-границы search_soundcloud()."
    )

lines = source.splitlines(
    keepends=True
)

function_start = search_node.lineno - 1
function_end = search_node.end_lineno

function_text = "".join(
    lines[
        function_start:function_end
    ]
)

print(
    f"  OK: search_soundcloud() — "
    f"строки {search_node.lineno}-{search_node.end_lineno}."
)

# ------------------------------------------------------------
# Ищем TITLE-ONLY блок
# ------------------------------------------------------------

title_only_pos = function_text.find(
    "TITLE-ONLY"
)

if title_only_pos < 0:
    fail(
        "TITLE-ONLY внутри search_soundcloud() не найден."
    )

print(
    "  OK: найден блок TITLE-ONLY."
)

# ------------------------------------------------------------
# Ищем конкретный участок с title_similarity
# ------------------------------------------------------------

similarity_pos = function_text.find(
    "title_similarity"
)

if similarity_pos < 0:
    fail(
        "Внутри search_soundcloud() "
        "не найден вызов title_similarity."
    )

if similarity_pos < title_only_pos:
    fail(
        "title_similarity находится до TITLE-ONLY. "
        "Структура функции отличается от ожидаемой."
    )

# ------------------------------------------------------------
# Создаём backup
# ------------------------------------------------------------

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = FILE.with_name(
    f"{FILE.name}.backup_{timestamp}"
)

print()
print("Создание резервной копии...")

shutil.copy2(
    FILE,
    backup
)

print(
    f"  OK: {backup.name}"
)

# ------------------------------------------------------------
# Новый TITLE-ONLY блок
# ------------------------------------------------------------

new_title_only = r'''        # ----------------------------------------------------
        # TITLE-ONLY FALLBACK
        # ----------------------------------------------------
        #
        # Четыре основных этапа выше НЕ изменяются.
        #
        # Этот fallback запускается только после того,
        # как обычный каскад не дал подходящего кандидата.
        #
        # Здесь исполнитель намеренно НЕ учитывается.
        # Это позволяет находить реальные треки, когда:
        #
        #   запрос:       пазнякс, OG Buda + блэкпинк
        #
        #   SoundCloud:
        #       OG Buda - блэкпинк
        #       ogbudapest - blekpink
        #       ogbudek - blekpink feat paznyaks
        #
        # Основной scoring evaluate_soundcloud_candidate()
        # здесь не используется, поскольку он требует
        # совпадения исполнителя.
        # ----------------------------------------------------

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

        title_only_query = (
            cleaned_base_title
            or cleaned_query_title
            or original_base_title
            or original_query_title
        )

        title_only_query = re.sub(
            r"\s+",
            " ",
            str(title_only_query or "")
        ).strip()

        if not title_only_query:

            print(
                "SoundCloud: TITLE-ONLY "
                "запрос пуст."
            )

            return None

        print()
        print(
            "SoundCloud: TITLE-ONLY запрос: "
            f"{title_only_query}"
        )

        print(
            "SoundCloud: максимум результатов: "
            f"{SOUNDCLOUD_SEARCH_RESULTS}"
        )

        try:

            title_collection = (
                fetch_soundcloud_results(
                    title_only_query,
                    client_id
                )
            )

        except Exception as error:

            print(
                "SoundCloud: TITLE-ONLY "
                "ошибка запроса: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return None

        if not isinstance(
            title_collection,
            list
        ):
            title_collection = []

        print(
            "SoundCloud: TITLE-ONLY "
            "получено результатов: "
            f"{len(title_collection)}"
        )

        if not title_collection:

            print(
                "SoundCloud: TITLE-ONLY "
                "результатов нет."
            )

            return None

        # ----------------------------------------------------
        # Локальная функция сравнения названия.
        #
        # ВАЖНО:
        # title_similarity НЕ является внешней функцией.
        # Она создаётся непосредственно здесь, поэтому
        # NameError больше возникнуть не может.
        # ----------------------------------------------------

        def title_similarity(
            requested,
            candidate_value
        ):

            requested = str(
                requested or ""
            ).lower().strip()

            candidate_value = str(
                candidate_value or ""
            ).lower().strip()

            if not requested or not candidate_value:
                return 0.0

            requested = re.sub(
                r"[^\w\s]",
                " ",
                requested,
                flags=re.UNICODE
            )

            candidate_value = re.sub(
                r"[^\w\s]",
                " ",
                candidate_value,
                flags=re.UNICODE
            )

            requested = re.sub(
                r"\s+",
                " ",
                requested
            ).strip()

            candidate_value = re.sub(
                r"\s+",
                " ",
                candidate_value
            ).strip()

            if not requested or not candidate_value:
                return 0.0

            if requested == candidate_value:
                return 1.0

            if (
                requested in candidate_value
                or candidate_value in requested
            ):
                shorter = min(
                    len(requested),
                    len(candidate_value)
                )

                longer = max(
                    len(requested),
                    len(candidate_value)
                )

                if longer:
                    return shorter / longer

            requested_tokens = set(
                requested.split()
            )

            candidate_tokens = set(
                candidate_value.split()
            )

            if not requested_tokens:
                return 0.0

            intersection = (
                requested_tokens
                & candidate_tokens
            )

            token_score = (
                len(intersection)
                / len(requested_tokens)
            )

            # Дополнительное сравнение последовательности
            # символов без сторонних библиотек.
            from difflib import SequenceMatcher

            sequence_score = (
                SequenceMatcher(
                    None,
                    requested,
                    candidate_value
                ).ratio()
            )

            return max(
                token_score,
                sequence_score
            )

        # ----------------------------------------------------
        # Оцениваем TITLE-ONLY кандидатов
        # ----------------------------------------------------

        title_candidates = []

        for candidate in title_collection:

            if not isinstance(
                candidate,
                dict
            ):
                continue

            candidate_title = str(
                candidate.get("title")
                or candidate.get("name")
                or ""
            ).strip()

            if not candidate_title:
                continue

            candidate_title_norm = norm(
                candidate_title
            )

            if not candidate_title_norm:
                continue

            # Убираем типичные конструкции
            # "Artist - Track" перед сравнением.
            candidate_track_title = (
                candidate_title_norm
            )

            separator_match = re.match(
                r"^\s*(.*?)\s+-\s+(.*?)\s*$",
                candidate_title_norm
            )

            if separator_match:

                possible_title = (
                    separator_match.group(
                        2
                    ).strip()
                )

                if possible_title:
                    candidate_track_title = (
                        possible_title
                    )

            candidate_track_title = (
                remove_featured_artists(
                    candidate_track_title
                )
            )

            if not candidate_track_title:
                candidate_track_title = (
                    candidate_title_norm
                )

            score = title_similarity(
                cleaned_base_title,
                candidate_track_title
            )

            # Также проверяем исходное название.
            original_score = title_similarity(
                original_base_title,
                candidate_track_title
            )

            score = max(
                score,
                original_score
            )

            # Полное совпадение названия —
            # максимально сильный результат.
            if (
                candidate_track_title
                == norm(cleaned_base_title)
            ):
                score = 1.0

            if (
                candidate_track_title
                == norm(original_base_title)
            ):
                score = 1.0

            title_candidates.append({
                "candidate": candidate,
                "title": candidate_title,
                "score": score,
            })

        if not title_candidates:

            print(
                "SoundCloud: TITLE-ONLY "
                "кандидатов после оценки нет."
            )

            return None

        title_candidates.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        best_title_item = (
            title_candidates[0]
        )

        best_title_candidate = (
            best_title_item["candidate"]
        )

        best_title = (
            best_title_item["title"]
        )

        best_title_score = (
            best_title_item["score"]
        )

        # ----------------------------------------------------
        # Минимальный порог.
        #
        # Для коротких названий вроде "блэкпинк"
        # требуется очень высокое совпадение.
        # ----------------------------------------------------

        if best_title_score < 0.80:

            print(
                "SoundCloud: TITLE-ONLY "
                "лучший кандидат слишком слабый."
            )

            print(
                "SoundCloud: score: "
                f"{best_title_score:.3f}"
            )

            print(
                "SoundCloud: название: "
                f"{best_title}"
            )

            return None

        user = best_title_candidate.get(
            "user"
        )

        if isinstance(
            user,
            dict
        ):

            candidate_artist = str(
                user.get("username")
                or ""
            ).strip()

        else:

            candidate_artist = ""

        candidate_url = (
            best_title_candidate.get(
                "permalink_url"
            )
            or best_title_candidate.get(
                "uri"
            )
            or ""
        )

        if not candidate_url:

            print(
                "SoundCloud: TITLE-ONLY "
                "у кандидата отсутствует URL."
            )

            return None

        print()
        print(
            "SoundCloud: TITLE-ONLY "
            "КАНДИДАТ НАЙДЕН."
        )

        print(
            "SoundCloud: score: "
            f"{best_title_score:.3f}"
        )

        print(
            "SoundCloud: название кандидата: "
            f"{best_title}"
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
            "TITLE-ONLY результат."
        )

        alternatives = []

        for alternative_item in (
            title_candidates[1:5]
        ):

            alternative_candidate = (
                alternative_item["candidate"]
            )

            alternative_title = str(
                alternative_candidate.get(
                    "title"
                )
                or alternative_candidate.get(
                    "name"
                )
                or ""
            ).strip()

            alternative_user = (
                alternative_candidate.get(
                    "user"
                )
            )

            if isinstance(
                alternative_user,
                dict
            ):

                alternative_artist = str(
                    alternative_user.get(
                        "username"
                    )
                    or ""
                ).strip()

            else:

                alternative_artist = ""

            alternative_url = (
                alternative_candidate.get(
                    "permalink_url"
                )
                or alternative_candidate.get(
                    "uri"
                )
                or ""
            )

            if not alternative_url:
                continue

            alternatives.append({
                "url": alternative_url,
                "title": alternative_title,
                "artist": alternative_artist,
                "duration": alternative_candidate.get(
                    "duration"
                ),
                "score": alternative_item["score"],
                "candidate": alternative_candidate,
                "search_stage": 5,
                "search_query": title_only_query,
                "exact_match": (
                    alternative_item["score"] >= 0.99
                ),
            })

        return {
            "url": candidate_url,
            "title": best_title,
            "artist": candidate_artist,
            "duration": best_title_candidate.get(
                "duration"
            ),
            "score": best_title_score,
            "candidate": best_title_candidate,
            "search_stage": 5,
            "search_query": title_only_query,
            "exact_match": (
                best_title_score >= 0.99
            ),
            "alternatives": alternatives,
        }
'''

# ------------------------------------------------------------
# Находим начало существующего TITLE-ONLY блока
# ------------------------------------------------------------

fallback_start = function_text.find(
    "        # ----------------------------------------------------\n"
    "        # TITLE-ONLY"
)

if fallback_start < 0:

    # Второй вариант — если комментарий оформлен иначе.
    marker = (
        '        print(\n'
        '            "SoundCloud: FALLBACK TITLE-ONLY"'
    )

    marker_pos = function_text.find(
        marker
    )

    if marker_pos < 0:
        fail(
            "Не удалось найти начало существующего "
            "TITLE-ONLY блока."
        )

    # Поднимаемся до ближайшего блока комментария.
    fallback_start = function_text.rfind(
        "        #",
        0,
        marker_pos
    )

# ------------------------------------------------------------
# Находим конец старого fallback.
#
# В текущей структуре fallback заканчивается:
#
#     return None
#
# после сообщения "ни один из 4 этапов..."
#
# Нам нужно заменить только TITLE-ONLY часть,
# оставив финальный return None основного каскада.
# ------------------------------------------------------------

fallback_end_marker = (
    "    print()\n\n"
    "    print(\n"
    '        "SoundCloud: ни один из "'
)

fallback_end = function_text.find(
    fallback_end_marker,
    fallback_start
)

if fallback_end < 0:
    fail(
        "Не найден конец существующего TITLE-ONLY блока. "
        "Основной каскад будет оставлен без изменений."
    )

# ------------------------------------------------------------
# Собираем новую функцию
# ------------------------------------------------------------

new_function_text = (
    function_text[:fallback_start]
    + new_title_only
    + "\n"
    + function_text[fallback_end:]
)

# ------------------------------------------------------------
# Защитная проверка:
# первые четыре этапа должны остаться
# ------------------------------------------------------------

for stage in (
    '"SoundCloud: ЭТАП "',
    '"исполнитель + очищенное название"',
    '"основной исполнитель + название без feat"',
    '"исполнитель + исходное название"',
    '"основной исполнитель + исходное название без feat"',
):

    if stage not in new_function_text:
        fail(
            "Защитная проверка не пройдена: "
            f"исчез элемент основного каскада: {stage}"
        )

# ------------------------------------------------------------
# Вставляем функцию обратно
# ------------------------------------------------------------

new_lines = lines[:function_start]

new_lines.extend(
    new_function_text.splitlines(
        keepends=True
    )
)

new_lines.extend(
    lines[function_end:]
)

new_source = "".join(
    new_lines
)

# ------------------------------------------------------------
# Проверка синтаксиса ДО записи
# ------------------------------------------------------------

print()
print(
    "Проверка нового кода перед записью..."
)

try:
    check_syntax(
        new_source
    )
except SyntaxError as error:

    print()
    print(
        "ОШИБКА ПАТЧА"
    )

    print()
    print(
        f"SyntaxError: {error}"
    )

    print()
    print(
        "Исходный файл не изменён."
    )

    print(
        f"Резервная копия: {backup.name}"
    )

    raise SystemExit(1)

print(
    "  OK: новый синтаксис."
)

# ------------------------------------------------------------
# Проверка отсутствия проблемного
# глобального вызова
# ------------------------------------------------------------

new_function_tree = ast.parse(
    new_source,
    filename=str(FILE)
)

new_search_node = None

for node in new_function_tree.body:

    if (
        isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        )
        and node.name == "search_soundcloud"
    ):
        new_search_node = node
        break

if new_search_node is None:
    fail(
        "После патча search_soundcloud() исчезла."
    )

new_function_source = "".join(
    new_source.splitlines(
        keepends=True
    )[
        new_search_node.lineno - 1:
        new_search_node.end_lineno
    ]
)

if "def title_similarity(" not in new_function_source:
    fail(
        "Защитная проверка: локальная "
        "title_similarity() не найдена."
    )

print(
    "  OK: title_similarity() определена "
    "внутри TITLE-ONLY."
)

# ------------------------------------------------------------
# Запись
# ------------------------------------------------------------

print()
print(
    "Запись исправленного sources_soundcloud.py..."
)

write_source(
    new_source
)

# ------------------------------------------------------------
# Финальная проверка файла
# ------------------------------------------------------------

final_source = read_source()

try:
    check_syntax(
        final_source
    )
except SyntaxError as error:

    print()
    print(
        "ОШИБКА ПОСЛЕ ЗАПИСИ"
    )

    print(
        f"SyntaxError: {error}"
    )

    print()
    print(
        "Автоматический откат..."
    )

    shutil.copy2(
        backup,
        FILE
    )

    print(
        "  OK: файл восстановлен."
    )

    raise SystemExit(1)

print()
print("=" * 70)
print(
    "ПАТЧ ПРИМЕНЁН УСПЕШНО"
)
print("=" * 70)

print()
print(
    "Изменено:"
)

print(
    "  - 4 основных этапа SoundCloud НЕ изменены."
)

print(
    "  - TITLE-ONLY остаётся пятым fallback."
)

print(
    "  - добавлено локальное сравнение названий."
)

print(
    "  - NameError: title_similarity устранён."
)

print(
    "  - alternatives сохранены."
)

print()
print(
    f"Резервная копия: {backup.name}"
        )
