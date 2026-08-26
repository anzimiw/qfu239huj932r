import ast
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# CENSURU.NET
# FIX: SoundCloud TITLE-ONLY fallback
#
# Исправляет:
#     NameError: name 'norm' is not defined
#
# ВАЖНО:
# - четыре основных этапа НЕ изменяются;
# - evaluate_soundcloud_candidate() НЕ изменяется;
# - scoring основных этапов НЕ изменяется;
# - TITLE-ONLY остаётся только fallback;
# ============================================================


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "sources_soundcloud.py"


def fail(message):
    raise RuntimeError(message)


def read_source():
    try:
        return TARGET.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        try:
            return TARGET.read_text(
                encoding="utf-8-sig"
            )
        except Exception as error:
            fail(
                "Не удалось прочитать "
                f"{TARGET}: {error}"
            )


def write_source(text):
    TARGET.write_text(
        text,
        encoding="utf-8"
    )


def compile_source(path):
    try:
        source = path.read_text(
            encoding="utf-8"
        )

        compile(
            source,
            str(path),
            "exec"
        )

    except Exception as error:
        fail(
            "Ошибка синтаксиса после патча:\n"
            f"{type(error).__name__}: {error}"
        )


print("=" * 70)
print("CENSURU.NET — FIX SOUNDCloud TITLE-ONLY")
print("=" * 70)
print()


# ============================================================
# 1. Исходная проверка
# ============================================================

print(
    "Проверка исходного sources_soundcloud.py..."
)

if not TARGET.exists():
    fail(
        f"Файл не найден: {TARGET}"
    )

compile_source(TARGET)

print(
    "  OK: исходный синтаксис."
)


source = read_source()


# ============================================================
# 2. Проверка search_soundcloud()
# ============================================================

print()
print(
    "Проверка текущей структуры..."
)

if "def search_soundcloud(" not in source:
    fail(
        "Не найдена search_soundcloud()."
    )

print(
    "  OK: search_soundcloud() найдена."
)


# ============================================================
# 3. Проверка TITLE-ONLY fallback
# ============================================================

marker_start = (
    "# ========================================================\n"
    "# SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1\n"
    "# ========================================================"
)

marker_end = (
    "# ========================================================\n"
    "# END SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1\n"
    "# ========================================================"
)

start_index = source.find(
    marker_start
)

if start_index == -1:
    fail(
        "Не найдено начало "
        "SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1."
    )

end_index = source.find(
    marker_end,
    start_index
)

if end_index == -1:
    fail(
        "Не найден конец "
        "SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1."
    )

fallback_end = (
    end_index + len(marker_end)
)

fallback_block = source[
    start_index:fallback_end
]

print(
    "  OK: TITLE-ONLY fallback найден."
)


# ============================================================
# 4. Проверяем, что fallback действительно внутри
#    search_soundcloud()
# ============================================================

search_start = source.find(
    "def search_soundcloud("
)

if search_start == -1:
    fail(
        "Не удалось определить начало "
        "search_soundcloud()."
    )

next_function = re.search(
    r"\n(?=def\s+\w+\s*\()",
    source[search_start + 1:]
)

if next_function:
    search_end = (
        search_start
        + 1
        + next_function.start()
    )
else:
    search_end = len(source)

if not (
    search_start
    < start_index
    < fallback_end
    <= search_end
):
    fail(
        "TITLE-ONLY fallback находится "
        "вне search_soundcloud()."
    )

print(
    "  OK: TITLE-ONLY fallback находится "
    "внутри search_soundcloud()."
)


# ============================================================
# 5. Проверяем конкретную проблему
# ============================================================

print()
print(
    "Проверка проблемных вызовов..."
)

title_similarity_calls = re.findall(
    r"\btitle_similarity\s*\(",
    fallback_block
)

print(
    "  Найдено вызовов title_similarity() "
    "в TITLE-ONLY: "
    f"{len(title_similarity_calls)}"
)

if len(title_similarity_calls) != 2:
    fail(
        "Ожидалось ровно 2 вызова "
        "title_similarity() в TITLE-ONLY."
    )


# ============================================================
# 6. Проверяем проблемные обращения norm()
# ============================================================

norm_calls = re.findall(
    r"\bnorm\s*\(",
    fallback_block
)

print(
    "  Найдено вызовов norm() "
    "в TITLE-ONLY: "
    f"{len(norm_calls)}"
)

if norm_calls:
    fail(
        "В TITLE-ONLY уже присутствуют "
        "вызовы norm().\n"
        "Патч остановлен, чтобы не менять "
        "неожиданную структуру."
    )


# ============================================================
# 7. Проверяем, что локальный helper ещё не добавлен
# ============================================================

helper_name = "fallback_title_similarity"

if helper_name in fallback_block:
    fail(
        "fallback_title_similarity() уже присутствует "
        "в TITLE-ONLY fallback.\n"
        "Повторное применение патча запрещено."
    )


# ============================================================
# 8. Создание резервной копии
# ============================================================

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
    "  OK: "
    f"{backup.name}"
)


# ============================================================
# 9. Локальный fallback_title_similarity()
# ============================================================
#
# Функция намеренно независима от:
#
#     norm()
#     tokens()
#     normalize_artist_confusables()
#
# из evaluate_soundcloud_candidate().
#
# Она используется только TITLE-ONLY fallback.
# ============================================================

helper = r'''
    # ========================================================
    # SOUNDCLOUD_TITLE_ONLY_SIMILARITY_V1
    # ========================================================
    #
    # Автономное сравнение названий для TITLE-ONLY fallback.
    #
    # ВАЖНО:
    # Эта функция НЕ использует norm() из
    # evaluate_soundcloud_candidate(), потому что norm()
    # является локальной функцией evaluator.
    # ========================================================

    def fallback_title_similarity(
        value_a,
        value_b
    ):
        import difflib
        import unicodedata

        def normalize_title(value):
            value = str(
                value or ""
            ).lower().strip()

            value = re.sub(
                r"https?://\S+",
                " ",
                value,
                flags=re.IGNORECASE
            )

            value = unicodedata.normalize(
                "NFKC",
                value
            )

            value = value.replace(
                "&",
                " and "
            )

            value = re.sub(
                r"[^\w\s]",
                " ",
                value,
                flags=re.UNICODE
            )

            value = re.sub(
                r"\s+",
                " ",
                value
            ).strip()

            return value

        left = normalize_title(
            value_a
        )

        right = normalize_title(
            value_b
        )

        if not left or not right:
            return 0.0

        if left == right:
            return 1.0

        left_tokens = set(
            left.split()
        )

        right_tokens = set(
            right.split()
        )

        if (
            left_tokens
            and right_tokens
        ):
            intersection = (
                left_tokens
                & right_tokens
            )

            union = (
                left_tokens
                | right_tokens
            )

            token_ratio = (
                len(intersection)
                / len(union)
            )
        else:
            token_ratio = 0.0

        sequence_ratio = (
            difflib.SequenceMatcher(
                None,
                left,
                right
            ).ratio()
        )

        return max(
            sequence_ratio,
            token_ratio
        )

    # ========================================================
    # END SOUNDCLOUD_TITLE_ONLY_SIMILARITY_V1
    # ========================================================
'''


# ============================================================
# 10. Точная точка вставки
# ============================================================

insertion_anchor = (
    "    title_fallback_queries = []"
)

anchor_position = fallback_block.find(
    insertion_anchor
)

if anchor_position == -1:
    fail(
        "Не найдена точка вставки "
        "title_fallback_queries."
    )


# Вставляем helper прямо перед title_fallback_queries.
new_fallback_block = (
    fallback_block[
        :anchor_position
    ]
    + helper
    + "\n"
    + fallback_block[
        anchor_position:
    ]
)


# ============================================================
# 11. Замена только двух вызовов
# ============================================================

old_call_1 = """title_similarity(
                    candidate_title,
                    original_query_title
                )"""

new_call_1 = """fallback_title_similarity(
                    candidate_title,
                    original_query_title
                )"""


old_call_2 = """title_similarity(
                    candidate_title,
                    cleaned_base_title
                )"""

new_call_2 = """fallback_title_similarity(
                    candidate_title,
                    cleaned_base_title
                )"""


count_1 = new_fallback_block.count(
    old_call_1
)

count_2 = new_fallback_block.count(
    old_call_2
)

print()
print(
    "Проверка точных замен..."
)

print(
    "  Вызов №1: "
    f"{count_1}"
)

print(
    "  Вызов №2: "
    f"{count_2}"
)

if count_1 != 1:
    fail(
        "Не найден ровно один первый "
        "проблемный вызов."
    )

if count_2 != 1:
    fail(
        "Не найден ровно один второй "
        "проблемный вызов."
    )


new_fallback_block = (
    new_fallback_block.replace(
        old_call_1,
        new_call_1,
        1
    )
)

new_fallback_block = (
    new_fallback_block.replace(
        old_call_2,
        new_call_2,
        1
    )
)


# ============================================================
# 12. Собираем новый исходник
# ============================================================

new_source = (
    source[:start_index]
    + new_fallback_block
    + source[fallback_end:]
)


# ============================================================
# 13. Контроль четырёх основных этапов
# ============================================================

print()
print(
    "Проверка четырёх основных этапов..."
)

required_stage_text = [
    "исполнитель + очищенное название",
    "основной исполнитель + название без feat",
    "исполнитель + исходное название",
    "основной исполнитель + исходное название без feat",
]

for stage in required_stage_text:
    if stage not in new_source:
        fail(
            "После патча пропал основной этап:\n"
            f"{stage}"
        )

print(
    "  OK: все 4 основных этапа сохранены."
)


# ============================================================
# 14. Проверяем границы TITLE-ONLY
# ============================================================

new_start_index = new_source.find(
    marker_start
)

new_end_index = new_source.find(
    marker_end,
    new_start_index
)

if (
    new_start_index == -1
    or new_end_index == -1
):
    fail(
        "После изменения повреждены "
        "границы TITLE-ONLY блока."
    )

new_fallback_block = new_source[
    new_start_index:
    new_end_index + len(marker_end)
]


# ============================================================
# 15. Проверяем результат
# ============================================================

print()
print(
    "Проверка результата..."
)

remaining_title_similarity = len(
    re.findall(
        r"\btitle_similarity\s*\(",
        new_fallback_block
    )
)

if remaining_title_similarity != 0:
    fail(
        "В TITLE-ONLY остались вызовы "
        f"title_similarity(): "
        f"{remaining_title_similarity}"
    )

print(
    "  OK: title_similarity() "
    "в TITLE-ONLY больше не используется."
)


remaining_norm = len(
    re.findall(
        r"\bnorm\s*\(",
        new_fallback_block
    )
)

if remaining_norm != 0:
    fail(
        "В TITLE-ONLY остались вызовы "
        f"norm(): {remaining_norm}"
    )

print(
    "  OK: TITLE-ONLY не зависит от norm()."
)


helper_count = new_fallback_block.count(
    "def fallback_title_similarity("
)

if helper_count != 1:
    fail(
        "Ожидалось ровно одно определение "
        "fallback_title_similarity(). "
        f"Получено: {helper_count}"
    )

print(
    "  OK: локальный "
    "fallback_title_similarity() добавлен."
)


new_similarity_calls = len(
    re.findall(
        r"\bfallback_title_similarity\s*\(",
        new_fallback_block
    )
)

if new_similarity_calls != 3:
    fail(
        "Ожидалось 3 обращения "
        "к fallback_title_similarity(): "
        "1 определение + 2 вызова.\n"
        f"Получено: {new_similarity_calls}"
    )

print(
    "  OK: два TITLE-ONLY вызова "
    "перенаправлены на локальный helper."
)


# ============================================================
# 16. Проверяем отсутствие изменений evaluator
# ============================================================

old_eval_start = source.find(
    "def evaluate_soundcloud_candidate("
)

new_eval_start = new_source.find(
    "def evaluate_soundcloud_candidate("
)

if (
    old_eval_start == -1
    or new_eval_start == -1
):
    fail(
        "Не удалось проверить "
        "evaluate_soundcloud_candidate()."
    )

old_eval_end = source.find(
    "\ndef ",
    old_eval_start + 1
)

new_eval_end = new_source.find(
    "\ndef ",
    new_eval_start + 1
)

if old_eval_end == -1:
    old_eval_end = len(source)

if new_eval_end == -1:
    new_eval_end = len(new_source)

old_evaluator = source[
    old_eval_start:old_eval_end
]

new_evaluator = new_source[
    new_eval_start:new_eval_end
]

if old_evaluator != new_evaluator:
    fail(
        "evaluate_soundcloud_candidate() "
        "был изменён.\n"
        "Патч остановлен."
    )

print(
    "  OK: evaluate_soundcloud_candidate() "
    "не изменён."
)


# ============================================================
# 17. Временный файл для compile-проверки
# ============================================================

temp_path = TARGET.with_name(
    TARGET.name + ".patch_test"
)

try:

    temp_path.write_text(
        new_source,
        encoding="utf-8"
    )

    compile_source(
        temp_path
    )

finally:

    if temp_path.exists():
        temp_path.unlink()


print(
    "  OK: новый файл проходит "
    "проверку Python syntax."
)


# ============================================================
# 18. Запись результата
# ============================================================

write_source(
    new_source
)


# ============================================================
# 19. Финальная проверка уже записанного файла
# ============================================================

compile_source(
    TARGET
)

final_source = read_source()

if (
    "def fallback_title_similarity("
    not in final_source
):
    fail(
        "После записи helper "
        "не найден в файле."
    )

final_start = final_source.find(
    marker_start
)

final_end = final_source.find(
    marker_end,
    final_start
)

if (
    final_start == -1
    or final_end == -1
):
    fail(
        "После записи повреждены "
        "границы TITLE-ONLY."
    )

final_block = final_source[
    final_start:
    final_end + len(marker_end)
]

if re.search(
    r"\btitle_similarity\s*\(",
    final_block
):
    fail(
        "Финальная проверка: "
        "title_similarity() всё ещё присутствует."
    )

if re.search(
    r"\bnorm\s*\(",
    final_block
):
    fail(
        "Финальная проверка: "
        "norm() всё ещё используется "
        "в TITLE-ONLY."
    )


# ============================================================
# ГОТОВО
# ============================================================

print()
print("=" * 70)
print("ПАТЧ ПРИМЕНЁН УСПЕШНО")
print("=" * 70)
print()
print(
    "Изменён только TITLE-ONLY fallback."
)
print(
    "4 основных этапа сохранены."
)
print(
    "evaluate_soundcloud_candidate() не изменён."
)
print(
    "TITLE-ONLY больше не зависит от локального norm()."
)
print()
print(
    "Резервная копия:"
)
print(
    f"  {backup.name}"
)
print()
print(
    "Теперь можно запускать downloader.py."
)
print("=" * 70)
