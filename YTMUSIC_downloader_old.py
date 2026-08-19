import requests
import re
import html
import base64
import subprocess
from urllib.parse import unquote


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 20


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================

def normalize(text):
    text = html.unescape(str(text))

    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("_", " ")

    text = re.sub(r"\(MP3\.tm\)", "", text, flags=re.I)
    text = re.sub(r"\(audiostart\.net\)", "", text, flags=re.I)

    text = re.sub(r"\.mp3$", "", text, flags=re.I)

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def clean_filename(text):
    text = unquote(text)

    text = re.sub(
        r"\(MP3\.tm\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.replace("_", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_filename(text):
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    return text.strip()


# ============================================================
# РУССКИЙ -> ЛАТИНИЦА
# ============================================================

RU_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sh",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def transliterate(text):
    result = []

    for char in text.lower():

        if char in RU_LATIN:
            result.append(RU_LATIN[char])

        else:
            result.append(char)

    return "".join(result)


# ============================================================
# СПЕЦИАЛЬНЫЕ ВАРИАНТЫ ПРОИЗНОШЕНИЯ
#
# Нужны потому, что реальные названия на сайтах часто
# записаны не по академической транслитерации.
# ============================================================

WORD_ALIASES = {

    # ЭЛЕВЕН
    "элевен": [
        "eleven",
        "elewen",
    ],

    # ЭЙТ
    "эйт": [
        "eit",
        "e yt",
        "ejt",
        "eight",
    ],

    # ПРИОРА
    "приора": [
        "priora",
    ],

    # УБЕР
    "убер": [
        "uber",
    ],

    # БЛЭК
    "блэк": [
        "blek",
        "black",
    ],

    # Частые варианты
    "холла": [
        "holla",
    ],

    "холла": [
        "holla",
    ],

    "ред": [
        "red",
    ],

    "ветер": [
        "weather",
    ],
}


def get_word_variants(word):
    """
    Возвращает варианты одного слова.
    """

    word = normalize(word)

    variants = {word}

    translit = transliterate(word)

    if translit:
        variants.add(translit)

    if word in WORD_ALIASES:

        for alias in WORD_ALIASES[word]:
            variants.add(alias)

    return variants


def text_variants(text):
    """
    Создаёт несколько вариантов всей фразы.
    """

    normalized = normalize(text)

    variants = {
        normalized,
        transliterate(normalized),
    }

    words = normalized.split()

    # --------------------------------------------------------
    # Если каждое слово имеет варианты —
    # строим дополнительные комбинации.
    # --------------------------------------------------------

    variant_lists = []

    for word in words:
        variant_lists.append(
            list(get_word_variants(word))
        )

    # Не создаём бесконечное количество комбинаций.
    # Для наших запросов достаточно первых вариантов.
    if len(words) <= 8:

        combinations = [[]]

        for word_variants in variant_lists:

            new_combinations = []

            for current in combinations:

                for variant in word_variants[:8]:

                    new_combinations.append(
                        current + [variant]
                    )

            combinations = new_combinations[:500]

        for combination in combinations:

            variants.add(
                " ".join(combination)
            )

    return variants


# ============================================================
# СРАВНЕНИЕ ИСПОЛНИТЕЛЯ / НАЗВАНИЯ
# ============================================================

def text_matches(wanted, found):
    """
    Проверяет, может ли найденный текст соответствовать
    пользовательскому запросу.

    Работает и с русским, и с латиницей.
    """

    wanted_variants = text_variants(wanted)

    found_normalized = normalize(found)

    found_translit = transliterate(found_normalized)

    # Полное совпадение
    if found_normalized in wanted_variants:
        return True

    if found_translit in wanted_variants:
        return True

    # --------------------------------------------------------
    # Словесное совпадение
    # --------------------------------------------------------

    wanted_words = normalize(wanted).split()
    found_words = normalize(found).split()

    if not wanted_words or not found_words:
        return False

    matched = 0

    for wanted_word in wanted_words:

        variants = get_word_variants(wanted_word)

        word_found = False

        for found_word in found_words:

            found_variants = get_word_variants(found_word)

            if variants.intersection(found_variants):
                word_found = True
                break

            # Дополнительная проверка через transliteration
            for variant in variants:

                if (
                    len(variant) >= 4
                    and (
                        variant in found_word
                        or found_word in variant
                    )
                ):
                    word_found = True
                    break

            if word_found:
                break

        if word_found:
            matched += 1

    return matched == len(wanted_words)


def phrase_matches(artist, title, filename):
    """
    Проверяет, содержит ли имя файла нужного исполнителя
    и название трека.
    """

    name = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    # --------------------------------------------------------
    # Прямая проверка
    # --------------------------------------------------------

    if (
        wanted_artist in name
        and wanted_title in name
    ):
        return True

    # --------------------------------------------------------
    # Проверяем исполнителя и название отдельно.
    # --------------------------------------------------------

    if text_matches(wanted_artist, name):
        artist_found = True
    else:
        artist_found = False

    if text_matches(wanted_title, name):
        title_found = True
    else:
        title_found = False

    return artist_found and title_found


# ============================================================
# ДЛИТЕЛЬНОСТЬ MP3
# ============================================================

def get_duration(url):

    try:

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            url
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return None

        value = result.stdout.strip()

        if not value:
            return None

        return float(value)

    except Exception:
        return None


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    seconds = int(round(seconds))

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


# ============================================================
# СКАЧИВАНИЕ
# ============================================================

def download_file(url, filename):

    print()
    print("Скачивание...")

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=60,
            stream=True,
            allow_redirects=True
        )

        if r.status_code != 200:

            print(
                "Ошибка скачивания. HTTP:",
                r.status_code
            )

            return False

        content_type = r.headers.get(
            "Content-Type",
            ""
        ).lower()

        if (
            "audio" not in content_type
            and "octet-stream" not in content_type
        ):

            print(
                "Ошибка: сервер не вернул аудиофайл."
            )

            print(
                "Content-Type:",
                content_type
            )

            return False

        total = 0

        with open(filename, "wb") as f:

            for chunk in r.iter_content(
                chunk_size=262144
            ):

                if chunk:

                    f.write(chunk)
                    total += len(chunk)

        print()
        print("ГОТОВО")
        print("Файл:", filename)

        print(
            "Размер:",
            round(total / 1024 / 1024, 2),
            "МБ"
        )

        return True

    except Exception as e:

        print("Ошибка:", e)

        return False


# ============================================================
# MP3PARTY
# ============================================================

def search_mp3party(artist, title):

    print()
    print("[1/3] MP3Party")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://mp3party.net/search",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print("HTTP:", r.status_code)
            return None

        text = html.unescape(r.text)

        pattern = re.compile(
            r'<div class="track__user-panel"'
            r'[^>]*'
            r'data-js-artist-name="([^"]+)"'
            r'[^>]*'
            r'data-js-id="(\d+)"'
            r'[^>]*'
            r'data-js-song-title="([^"]+)"'
            r'[^>]*'
            r'data-js-url="([^"]+)"',
            re.I
        )

        results = pattern.findall(text)

        print(
            "Найдено результатов:",
            len(results)
        )

        wanted_artist = normalize(artist)
        wanted_title = normalize(title)

        for (
            found_artist,
            song_id,
            found_title,
            mp3_url
        ) in results:

            if (
                text_matches(
                    wanted_artist,
                    found_artist
                )
                and
                text_matches(
                    wanted_title,
                    found_title
                )
            ):

                print()
                print("ТОЧНОЕ СОВПАДЕНИЕ")

                print(
                    "Исполнитель:",
                    found_artist
                )

                print(
                    "Название:   ",
                    found_title
                )

                print(
                    "ID:",
                    song_id
                )

                url = (
                    "https://dl2.mp3party.net/download/"
                    + song_id
                )

                print(
                    "Ссылка:     ",
                    url
                )

                return url

        print(
            "Точное совпадение не найдено."
        )

    except Exception as e:

        print(
            "Ошибка MP3Party:",
            e
        )

    return None


# ============================================================
# ШТРАФ ЗА ЛИШНИЕ ВЕРСИИ
# ============================================================

def version_penalty(filename, artist, title):

    name = normalize(filename)

    requested = normalize(
        artist + " " + title
    )

    penalty = 0

    modifiers = [

        "nightcore",
        "nightcorebot",

        "remix",
        "slowed",
        "slowed reverb",

        "sped up",
        "speed up",

        "bass",
        "bass boosted",

        "edit",
        "extended",

        "instrumental",
        "karaoke",

        "cover",

        "live",
        "acoustic",

        "rework",
        "bootleg",

        "club",
        "hardstyle",

        "phonk",

        "8d",

        "radio edit",
        "original mix",
        "extended mix",

        "prod.",
        "prod",
    ]

    for modifier in modifiers:

        if modifier in name and modifier not in requested:

            penalty += 100

    # --------------------------------------------------------
    # Очень сильный бонус обычному имени.
    # --------------------------------------------------------

    base_variants = text_variants(
        artist + " - " + title
    )

    normalized_name = normalize(filename)

    for variant in base_variants:

        if normalized_name == normalize(variant):

            penalty -= 500

    return penalty


# ============================================================
# ОЦЕНКА MP3TM
# ============================================================

def score_mp3tm_candidate(
    filename,
    artist,
    title
):

    name = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    # --------------------------------------------------------
    # Проверяем, действительно ли это нужный трек.
    # --------------------------------------------------------

    if not phrase_matches(
        artist,
        title,
        filename
    ):
        return -100000

    score = 0

    # --------------------------------------------------------
    # Базовое совпадение
    # --------------------------------------------------------

    score += 500

    # --------------------------------------------------------
    # Варианты всей фразы
    # --------------------------------------------------------

    phrase_variants = text_variants(
        artist + " " + title
    )

    for variant in phrase_variants:

        if normalize(variant) in name:

            score += 300
            break

    # --------------------------------------------------------
    # Исполнитель + название через дефис
    # --------------------------------------------------------

    phrase_variants = text_variants(
        artist + " - " + title
    )

    for variant in phrase_variants:

        if normalize(variant) in name:

            score += 500
            break

    # --------------------------------------------------------
    # Обратный порядок
    # --------------------------------------------------------

    reverse_variants = text_variants(
        title + " - " + artist
    )

    for variant in reverse_variants:

        if normalize(variant) in name:

            score += 300
            break

    # --------------------------------------------------------
    # Убираем известные части из имени.
    # Чем меньше осталось — тем лучше.
    # --------------------------------------------------------

    remaining = name

    for variant in text_variants(artist):

        if variant in remaining:

            remaining = remaining.replace(
                variant,
                "",
                1
            )

            break

    for variant in text_variants(title):

        if variant in remaining:

            remaining = remaining.replace(
                variant,
                "",
                1
            )

            break

    remaining = re.sub(
        r"\s*-\s*",
        " ",
        remaining
    )

    remaining = re.sub(
        r"\s+",
        " ",
        remaining
    ).strip()

    score -= len(remaining) * 3

    # --------------------------------------------------------
    # Штраф за версии
    # --------------------------------------------------------

    score -= version_penalty(
        filename,
        artist,
        title
    )

    return score


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(artist, title):

    print()
    print("[2/3] MP3TM")

    query = f"{artist} {title}"

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip("-").lower()

    url = f"https://{slug}.mp3tm.net/"

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print("HTTP:", r.status_code)

            return None

        text = html.unescape(r.text)

        # ----------------------------------------------------
        # Ищем прямые MP3-ссылки
        # ----------------------------------------------------

        links = re.findall(
            r'https?://[^"\']+\.mp3(?:\?[^"\']*)?',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(links)
        )

        print(
            "Найдено MP3-ссылок:",
            len(links)
        )

        # ----------------------------------------------------
        # Кандидаты
        # ----------------------------------------------------

        candidates = []

        for link in links:

            filename = link.split("/")[-1]

            filename = clean_filename(
                filename
            )

            score = score_mp3tm_candidate(
                filename,
                artist,
                title
            )

            if score <= -1000:
                continue

            candidates.append({
                "url": link,
                "filename": filename,
                "score": score,
                "duration": None
            })

        # ----------------------------------------------------
        # Ничего не найдено
        # ----------------------------------------------------

        if not candidates:

            print(
                "Точное совпадение не найдено."
            )

            return None

        # ----------------------------------------------------
        # Сортировка
        # ----------------------------------------------------

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # ----------------------------------------------------
        # Показываем найденные варианты
        # ----------------------------------------------------

        print()
        print(
            "НАЙДЕНО ВАРИАНТОВ С ОДИНАКОВЫМ "
            "СОВПАДЕНИЕМ:",
            len(candidates)
        )

        for i, candidate in enumerate(
            candidates[:15],
            1
        ):

            print(
                f"{i}. "
                f"{candidate['filename']} "
                f"[совпадение: "
                f"{candidate['score']}]"
            )

        # ----------------------------------------------------
        # Проверяем длительность лучших кандидатов.
        #
        # Если несколько файлов имеют близкое качество
        # совпадения, смотрим их длительность.
        # --------------------------------------------------------

        best_score = candidates[0]["score"]

        close_candidates = [
            c
            for c in candidates
            if c["score"] >= best_score - 20
        ]

        # Ограничиваем число запросов к ffprobe
        close_candidates = close_candidates[:10]

        for candidate in close_candidates:

            candidate["duration"] = get_duration(
                candidate["url"]
            )

        # ----------------------------------------------------
        # Выводим варианты с длительностью
        # --------------------------------------------------------

        if len(close_candidates) > 1:

            print()
            print(
                "ВАРИАНТЫ С БЛИЗКИМ СОВПАДЕНИЕМ:"
            )

            for i, candidate in enumerate(
                close_candidates,
                1
            ):

                print(
                    f"{i}. "
                    f"{candidate['filename']} "
                    f"["
                    f"{format_duration(candidate['duration'])}"
                    f"]"
                )

        # ----------------------------------------------------
        # Выбираем лучший
        # --------------------------------------------------------

        best = close_candidates[0]

        print()
        print(
            "НАЙДЕН НАИЛУЧШИЙ КАНДИДАТ"
        )

        print(
            "Исполнитель:",
            artist
        )

        print(
            "Название:   ",
            title
        )

        print(
            "Длительность:",
            format_duration(
                best["duration"]
            )
        )

        print(
            "URL:",
            best["url"]
        )

        return best["url"]

    except Exception as e:

        print(
            "Ошибка MP3TM:",
            e
        )

    return None


# ============================================================
# AUDIOSTART
# ============================================================

def search_audiostart(artist, title):

    print()
    print("[3/3] AudioStart")

    query = f"{artist} {title}"

    try:

        r = requests.get(
            "https://audiostart.net/",
            params={"song": query},
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print("HTTP:", r.status_code)

            return None

        text = html.unescape(r.text)

        links = re.findall(
            r'href=["\']([^"\']*?/getmp3/[^"\']+)["\']',
            text,
            re.I
        )

        links = list(
            dict.fromkeys(links)
        )

        print(
            "Найдено ссылок:",
            len(links)
        )

        for link in links:

            try:

                encoded = link.split(
                    "/getmp3/",
                    1
                )[1]

                decoded = base64.b64decode(
                    encoded
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                decoded = unquote(
                    decoded
                )

                if phrase_matches(
                    artist,
                    title,
                    decoded
                ):

                    if link.startswith("//"):

                        link = (
                            "https:"
                            + link
                        )

                    print()
                    print(
                        "ТОЧНОЕ СОВПАДЕНИЕ"
                    )

                    print(
                        "Исполнитель:",
                        artist
                    )

                    print(
                        "Название:   ",
                        title
                    )

                    print(
                        "URL:",
                        link
                    )

                    return link

            except Exception:
                continue

        print(
            "Точное совпадение не найдено."
        )

    except Exception as e:

        print(
            "Ошибка AudioStart:",
            e
        )

    return None


# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

def main():

    print("=" * 50)
    print("YTMUSIC DOWNLOADER")
    print("=" * 50)
    print()

    artist = input(
        "Исполнитель: "
    ).strip()

    title = input(
        "Название:    "
    ).strip()

    if not artist or not title:

        print(
            "Исполнитель и название "
            "должны быть указаны."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    filename = (
        f"{safe_filename(artist)} - "
        f"{safe_filename(title)}.mp3"
    )

    print()
    print("=" * 50)

    print(
        "Ищем:",
        artist,
        "—",
        title
    )

    print("=" * 50)

    # ========================================================
    # 1. MP3PARTY
    # ========================================================

    url = search_mp3party(
        artist,
        title
    )

    if url:

        print()
        print("=" * 50)

        print(
            "ВЫБРАН ИСТОЧНИК: MP3PARTY"
        )

        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filename
        ):

            input(
                "\nНажмите Enter для выхода..."
            )

            return

    # ========================================================
    # 2. MP3TM
    # ========================================================

    url = search_mp3tm(
        artist,
        title
    )

    if url:

        print()
        print("=" * 50)

        print(
            "ВЫБРАН ИСТОЧНИК: MP3TM"
        )

        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filename
        ):

            input(
                "\nНажмите Enter для выхода..."
            )

            return

    # ========================================================
    # 3. AUDIOSTART
    # ========================================================

    url = search_audiostart(
        artist,
        title
    )

    if url:

        print()
        print("=" * 50)

        print(
            "ВЫБРАН ИСТОЧНИК: AUDIOSTART"
        )

        print("=" * 50)

        print(
            "URL:",
            url
        )

        if download_file(
            url,
            filename
        ):

            input(
                "\nНажмите Enter для выхода..."
            )

            return

    # ========================================================
    # НЕ НАЙДЕНО
    # ========================================================

    print()
    print("=" * 50)

    print(
        "ТРЕК НЕ НАЙДЕН"
    )

    print("=" * 50)

    input(
        "\nНажмите Enter для выхода..."
    )


if __name__ == "__main__":
    main()
