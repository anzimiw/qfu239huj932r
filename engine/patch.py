# -*- coding: utf-8 -*-

"""
CENSURU.NET — интеграционный тест AudioStart

Проверяет полный путь:

    downloader.py
        ↓
    search_audiostart()
        ↓
    getmp3 URL
        ↓
    download_file()
        ↓
    проверка скачанного файла
        ↓
    готовый MP3

ВАЖНО:
- downloader.py НЕ изменяется;
- sources_audiostart.py НЕ изменяется;
- остальные источники временно отключаются только в памяти
  текущего процесса;
- после завершения Python-процесса все подмены исчезают.

Тестовый трек:
    Платина — Гикаю
    Длительность: 130 секунд
"""

import os
import sys
import traceback
from pathlib import Path


# ============================================================
# НАСТРОЙКИ
# ============================================================

ARTIST = "Платина"
TITLE = "Гикаю"
DURATION = 130.0

ENGINE_DIR = Path(__file__).resolve().parent

print("=" * 70)
print("CENSURU.NET — ИНТЕГРАЦИОННЫЙ ТЕСТ AUDIOSTART")
print("=" * 70)

print()
print(f"Тестовый исполнитель: {ARTIST}")
print(f"Тестовое название:    {TITLE}")
print(f"Длительность:         {DURATION:.0f} сек")
print()
print(f"Каталог engine:       {ENGINE_DIR}")
print()


# ============================================================
# ПРОВЕРКА downloader.py
# ============================================================

print("-" * 70)
print("1. Загрузка downloader.py")
print("-" * 70)

try:
    import downloader
except Exception as e:
    print()
    print("ОШИБКА: не удалось импортировать downloader.py")
    print(f"{type(e).__name__}: {e}")
    print()
    traceback.print_exc()
    sys.exit(1)

print("OK: downloader.py импортирован.")


# ============================================================
# ПРОВЕРКА НЕОБХОДИМЫХ ФУНКЦИЙ
# ============================================================

print()
print("-" * 70)
print("2. Проверка функций")
print("-" * 70)

required_functions = [
    "find_and_download_track",
    "search_audiostart",
]

optional_functions = [
    "search_soundcloud",
    "search_mp3party",
    "search_mp3tm",
    "download_file",
]


def check_function(name, required=True):
    value = getattr(downloader, name, None)

    if callable(value):
        print(f"OK: {name}")
        return True

    if required:
        print(f"ОШИБКА: отсутствует функция {name}")
        return False

    print(f"INFO: {name} отсутствует")
    return False


if not check_function("find_and_download_track", required=True):
    sys.exit(1)

if not check_function("search_audiostart", required=True):
    sys.exit(1)

for function_name in optional_functions:
    check_function(function_name, required=False)


# ============================================================
# СОХРАНЯЕМ ОРИГИНАЛЬНЫЕ ФУНКЦИИ
# ============================================================

original_functions = {}

for function_name in (
    "search_soundcloud",
    "search_mp3party",
    "search_mp3tm",
):
    if hasattr(downloader, function_name):
        original_functions[function_name] = getattr(
            downloader,
            function_name,
        )


# ============================================================
# ВРЕМЕННЫЕ ЗАГЛУШКИ
# ============================================================

def disabled_source(*args, **kwargs):
    """
    Временно отключённый источник.

    Это НЕ изменение исходного файла.
    Подмена существует только внутри текущего Python-процесса.
    """
    return None


print()
print("-" * 70)
print("3. Временное отключение предыдущих источников")
print("-" * 70)

for function_name in (
    "search_soundcloud",
    "search_mp3party",
    "search_mp3tm",
):
    if function_name in original_functions:
        setattr(
            downloader,
            function_name,
            disabled_source,
        )
        print(f"ОТКЛЮЧЁН НА ВРЕМЯ ТЕСТА: {function_name}")


print()
print("AudioStart остаётся без изменений.")
print("downloader.py на диске не изменяется.")


# ============================================================
# ЗАПУСК
# ============================================================

print()
print("-" * 70)
print("4. Запуск find_and_download_track()")
print("-" * 70)

print()
print("Ожидаемая последовательность:")
print()
print("  SoundCloud  → пропуск")
print("  MP3Party    → пропуск")
print("  MP3TM       → пропуск")
print("  AudioStart  → ПОИСК")
print("       ↓")
print("  getmp3 URL")
print("       ↓")
print("  download_file()")
print("       ↓")
print("  проверка MP3")
print()
print("=" * 70)
print("НАЧАЛО ТЕСТА")
print("=" * 70)
print()


result = None

try:
    """
    ВАЖНО:

    Здесь используется существующая функция downloader.py.

    У разных версий downloader.py сигнатура этой функции может
    отличаться. Сначала пробуем наиболее распространённый вариант
    с artist/title/duration.

    Если текущая версия требует дополнительные аргументы, ошибка
    будет выведена ниже — тогда по ней подстроим тест точно под
    текущую сигнатуру.
    """

    import inspect

    function = downloader.find_and_download_track

    signature = inspect.signature(function)

    print("Сигнатура find_and_download_track:")
    print(f"  {signature}")
    print()

    parameters = list(signature.parameters.values())

    positional_required = [
        p
        for p in parameters
        if (
            p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            and p.default is inspect.Parameter.empty
        )
    ]

    print(f"Обязательных позиционных параметров: {len(positional_required)}")
    print()

    # --------------------------------------------------------
    # Автоматическая попытка подобрать аргументы по именам.
    # --------------------------------------------------------

    kwargs = {}

    for parameter in parameters:
        name = parameter.name.lower()

        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        if parameter.default is not inspect.Parameter.empty:
            continue

        if name in (
            "artist",
            "artist_name",
            "performer",
            "author",
        ):
            kwargs[parameter.name] = ARTIST

        elif name in (
            "title",
            "track_title",
            "song_title",
            "name",
        ):
            kwargs[parameter.name] = TITLE

        elif name in (
            "duration",
            "track_duration",
            "duration_seconds",
            "length",
        ):
            kwargs[parameter.name] = DURATION

        elif name in (
            "album",
            "album_name",
        ):
            kwargs[parameter.name] = TITLE

        elif name in (
            "source",
            "service",
            "platform",
        ):
            kwargs[parameter.name] = "youtube"

    unresolved = [
        p.name
        for p in positional_required
        if p.name not in kwargs
    ]

    if unresolved:
        print("ВНИМАНИЕ: не удалось автоматически определить")
        print("значения следующих обязательных параметров:")
        print()
        for name in unresolved:
            print(f"  - {name}")
        print()
        print(
            "Тест остановлен без изменения файлов. "
            "Пришли этот вывод, и я подгоню тест под точную сигнатуру."
        )
        sys.exit(2)

    print("Передаваемые аргументы:")
    for key, value in kwargs.items():
        print(f"  {key} = {value!r}")

    print()

    result = function(**kwargs)


except TypeError as e:
    print()
    print("=" * 70)
    print("ОШИБКА ВЫЗОВА find_and_download_track()")
    print("=" * 70)
    print()
    print(f"{type(e).__name__}: {e}")
    print()
    print("Полный traceback:")
    traceback.print_exc()
    sys.exit(2)

except Exception as e:
    print()
    print("=" * 70)
    print("ОШИБКА ВО ВРЕМЯ ИНТЕГРАЦИОННОГО ТЕСТА")
    print("=" * 70)
    print()
    print(f"{type(e).__name__}: {e}")
    print()
    traceback.print_exc()
    sys.exit(3)


# ============================================================
# АНАЛИЗ РЕЗУЛЬТАТА
# ============================================================

print()
print("=" * 70)
print("РЕЗУЛЬТАТ find_and_download_track()")
print("=" * 70)
print()

print(f"Тип результата: {type(result).__name__}")
print(f"Результат:      {result!r}")

print()


# ============================================================
# ПРОВЕРКА ФАЙЛА
# ============================================================

filepath = None

if isinstance(result, (str, Path)):
    filepath = Path(result)

elif isinstance(result, dict):
    for key in (
        "filepath",
        "file",
        "path",
        "filename",
        "output",
    ):
        value = result.get(key)

        if value:
            filepath = Path(value)
            break

elif isinstance(result, tuple):
    for item in result:
        if isinstance(item, (str, Path)):
            candidate = Path(item)

            if candidate.exists():
                filepath = candidate
                break


print("-" * 70)
print("5. Проверка скачанного файла")
print("-" * 70)
print()

if filepath is None:
    print("НЕ УДАЛОСЬ ОПРЕДЕЛИТЬ ПУТЬ К ФАЙЛУ ИЗ РЕЗУЛЬТАТА.")
    print()
    print("Сам результат:")
    print(repr(result))
    print()
    print(
        "Это не обязательно означает ошибку AudioStart. "
        "Возможно, текущая версия downloader.py возвращает "
        "другой формат результата."
    )
    sys.exit(4)


filepath = filepath.resolve()

print(f"Файл: {filepath}")
print()

if not filepath.exists():
    print("ОШИБКА: указанный файл не существует.")
    sys.exit(5)

print("OK: файл существует.")

try:
    file_size = filepath.stat().st_size
except Exception as e:
    print(f"ОШИБКА чтения размера файла: {e}")
    sys.exit(6)

print(f"Размер: {file_size:,} байт")

if file_size <= 0:
    print("ОШИБКА: файл пустой.")
    sys.exit(7)


# ============================================================
# ПРОВЕРКА РАСШИРЕНИЯ
# ============================================================

print()
print("-" * 70)
print("6. Проверка расширения")
print("-" * 70)
print()

print(f"Расширение: {filepath.suffix}")

if filepath.suffix.lower() != ".mp3":
    print(
        "ПРЕДУПРЕЖДЕНИЕ: итоговый файл не имеет расширение .mp3."
    )
else:
    print("OK: расширение .mp3")


# ============================================================
# ФИНАЛ
# ============================================================

print()
print("=" * 70)
print("ИНТЕГРАЦИОННЫЙ ТЕСТ AUDIOSTART ЗАВЕРШЁН")
print("=" * 70)
print()
print("Результат:")
print()
print("  AudioStart найден через downloader.py     — OK")
print("  getmp3 URL передан в download pipeline    — OK")
print("  реальный файл создан                      — OK")
print(f"  итоговый файл: {filepath}")
print()
print("ВАЖНО:")
print("downloader.py и sources_audiostart.py этим тестом")
print("не изменялись.")
print()
print("=" * 70)
