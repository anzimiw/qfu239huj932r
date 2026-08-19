import requests
import re
import html
import base64
import os
import subprocess
from urllib.parse import unquote
from difflib import SequenceMatcher


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


# ============================================================
# ТРАНСЛИТЕРАЦИЯ
# ============================================================

RU_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
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
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya"
}


def transliterate(text):
    """
    Переводит русскую запись в приблизительную
    латинскую транслитерацию.

    Например:

    ЭЛЕВЕН ЭЙТ
    ->
    eleven eyt

    ПРИОРА УБЕР БЛЭК
    ->
    priora uber blek
    """

    text = normalize(text)

    result = []

    for char in text:

        if char in RU_TO_LAT:
            result.append(RU_TO_LAT[char])
        else:
            result.append(char)

    return "".join(result)


def normalize_for_compare(text):
    """
    Нормализация для сравнения.

    Возвращает сразу несколько вариантов:
    - оригинал
    - транслитерированный вариант
    """

    original = normalize(text)
    translit = transliterate(text)

    return {
        "original": original,
        "translit": translit
    }


# ============================================================
# ДОПОЛНИТЕЛЬНАЯ НОРМАЛИЗАЦИЯ
# ============================================================

def compact(text):
    """
    Убирает пробелы и дефисы.

    Например:

    ELEVEN EJT
    ELEVEN-EJT

    становятся одинаковыми.
    """

    text = normalize(text)

    return re.sub(
        r"[^a-z0-9а-яё]+",
        "",
        text
    )


# ============================================================
# ПОХОЖЕСТЬ СТРОК
# ============================================================

def similarity(a, b):

    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# ============================================================
# СРАВНЕНИЕ РУССКОЙ И ЛАТИНСКОЙ ЗАПИСИ
# ============================================================

def text_matches(found, wanted):
    """
    Проверяет, является ли found подходящим
    вариантом wanted.

    Учитываются:

    1. обычное совпадение;
    2. транслитерация;
    3. компактная запись;
    4. небольшие отличия в написании.
    """

    found = normalize(found)
    wanted = normalize(wanted)

    if not found or not wanted:
        return False

    # Полное совпадение
    if found == wanted:
        return True

    # Одно содержится в другом
    if wanted in found:
        return True

    if found in wanted:
        return True

    # Транслитерация запроса
    wanted_translit = transliterate(wanted)

    if wanted_translit == found:
        return True

    if wanted_translit in found:
        return True

    if found in wanted_translit:
        return True

    # Сравнение без пробелов/дефисов
    if compact(found) == compact(wanted):
        return True

    if compact(found) == compact(wanted_translit):
        return True

    # Небольшая разница в написании
    if similarity(found, wanted) >= 0.88:
        return True

    if similarity(found, wanted_translit) >= 0.82:
        return True

    return False


# ============================================================
# БЕЗОПАСНОЕ ИМЯ ФАЙЛА
# ============================================================

def safe_filename(text):

    text = re.sub(
        r'[<>:"/\\|?*]',
        "",
        text
    )

    text = text.strip()

    return text


def clean_filename(text):

    text = unquote(text)

    text = re.sub(
        r"\(MP3\.tm\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\(audiostart\.net\)\.mp3$",
        "",
        text,
        flags=re.I
    )

    text = text.replace("_", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


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

        print(
            "Ошибка:",
            e
        )

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

            print(
                "HTTP:",
                r.status_code
            )

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

        for (
            found_artist,
            song_id,
            found_title,
            mp3_url
        ) in results:

            artist_match = text_matches(
                found_artist,
                artist
            )

            title_match = text_matches(
                found_title,
                title
            )

            if artist_match and title_match:

                print()
                print(
                    "ТОЧНОЕ СОВПАДЕНИЕ"
                )

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
# ОЦЕНКА КАНДИДАТА MP3TM
# ============================================================

def score_mp3tm_candidate(
    filename,
    artist,
    title
):

    name = normalize(filename)

    wanted_artist = normalize(artist)
    wanted_title = normalize(title)

    wanted_artist_translit = transliterate(
        wanted_artist
    )

    wanted_title_translit = transliterate(
        wanted_title
    )

    score = 0

    # --------------------------------------------------------
    # Исполнитель
    # --------------------------------------------------------

    artist_exact = (
        wanted_artist in name
    )

    artist_translit = (
        wanted_artist_translit in name
    )

    if artist_exact:

        score += 300

    elif artist_translit:

        score += 280

    else:

        artist_similarity = max(
            similarity(
                name,
                wanted_artist
            ),
            similarity(
                name,
                wanted_artist_translit
            )
        )

        if artist_similarity < 0.65:

            return -10000

        score += int(
            artist_similarity * 100
        )

    # --------------------------------------------------------
    # Название
    # --------------------------------------------------------

    title_exact = (
        wanted_title in name
    )

    title_translit = (
        wanted_title_translit in name
    )

    if title_exact:

        score += 300

    elif title_translit:

        score += 280

    else:

        title_similarity = max(
            similarity(
                name,
                wanted_title
            ),
            similarity(
                name,
                wanted_title_translit
            )
        )

        if title_similarity < 0.65:

            return -10000

        score += int(
            title_similarity * 100
        )

    # --------------------------------------------------------
    # Идеальная фраза
    # --------------------------------------------------------

    exact_phrase = (
        wanted_artist
        + " - "
        + wanted_title
    )

    translit_phrase = (
        wanted_artist_translit
        + " - "
        + wanted_title_translit
    )

    reverse_phrase = (
        wanted_title
        + " - "
        + wanted_artist
    )

    if exact_phrase in name:

        score += 500

    elif translit_phrase in name:

        score += 500

    elif reverse_phrase in name:

        score += 350

    # --------------------------------------------------------
    # Сколько лишнего текста
    # --------------------------------------------------------

    remaining = name

    # Удаляем запрос в разных вариантах

    remaining = remaining.replace(
        wanted_artist,
        "",
        1
    )

    remaining = remaining.replace(
        wanted_title,
        "",
        1
    )

    remaining = remaining.replace(
        wanted_artist_translit,
        "",
        1
    )

    remaining = remaining.replace(
        wanted_title_translit,
        "",
        1
    )

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

    score -= len(remaining) * 2

    # --------------------------------------------------------
    # Полное совпадение
    # --------------------------------------------------------

    expected_variants = [
        wanted_artist
        + " "
        + wanted_title,

        wanted_artist_translit
        + " "
        + wanted_title_translit
    ]

    for expected in expected_variants:

        if normalize(name) == normalize(expected):

            score += 1000

    # --------------------------------------------------------
    # Дополнительные версии
    # --------------------------------------------------------

    modifiers = [

        "nightcore",
        "nightcorebot",
        "remix",
        "slowed",
        "slowed reverb",
        "sped up",
        "speed up",
        "bass",
        "type beat",
        "edit",
        "extended",
        "instrumental",
        "cover",
        "live",
        "acoustic",
        "rework",
        "version",
        "bootleg",
        "club",
        "hardstyle",
        "phonk",
        "8d",
        "8d audio",
        "ultra slowed",
        "super slowed",
        "speedup",
        "slowed + reverb"
    ]

    requested_text = (
        wanted_artist
        + " "
        + wanted_title
    )

    requested_text_translit = (
        wanted_artist_translit
        + " "
        + wanted_title_translit
    )

    for modifier in modifiers:

        if modifier in name:

            if (
                modifier not in requested_text
                and
                modifier not in requested_text_translit
            ):

                # Очень сильный штраф.
                #
                # Например:
                #
                # ELEVEN EJT - PRIORA UBER BLEK
                #
                # будет выше:
                #
                # ELEVEN EJT - PRIORA UBER BLEK slowed

                score -= 250

    return score


# ============================================================
# MP3TM
# ============================================================

def search_mp3tm(artist, title):

    print()
    print("[2/3] MP3TM")

    query = f"{artist} {title}"

    # --------------------------------------------------------
    # Формируем slug
    # --------------------------------------------------------

    slug = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ]+",
        "-",
        query
    ).strip("-").lower()

    url = (
        f"https://{slug}.mp3tm.net/"
    )

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print(
                "HTTP:",
                r.status_code
            )

            return None

        text = html.unescape(r.text)

        # ----------------------------------------------------
        # Ищем MP3
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

        if not links:

            print(
                "Точное совпадение не найдено."
            )

            return None

        # ----------------------------------------------------
        # Создаём кандидатов
        # ----------------------------------------------------

        candidates = []

        for link in links:

            filename = (
                link.split("/")[-1]
            )

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

        if not candidates:

            print(
                "Точное совпадение не найдено."
            )

            return None

        # ----------------------------------------------------
        # Сортируем
        # ----------------------------------------------------

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # ----------------------------------------------------
        # ВАЖНО:
        # показываем найденные кандидаты
        # ----------------------------------------------------

        print()
        print(
            "ВСЕ ПОДХОДЯЩИЕ КАНДИДАТЫ:"
        )

        for i, candidate in enumerate(
            candidates[:20],
            1
        ):

            print(
                f"{i}. "
                f"{candidate['filename']} "
                f"[совпадение: "
                f"{candidate['score']}]"
            )

        # ----------------------------------------------------
        # Берём лучших
        # ----------------------------------------------------

        best_score = candidates[0]["score"]

        # Кандидаты, которые находятся
        # очень близко к лучшему результату.
        #
        # Это позволяет сравнивать длительность,
        # если у одного трека несколько версий.

        close_candidates = [
            c
            for c in candidates
            if c["score"] >= best_score - 80
        ]

        # Не проверяем слишком много URL через ffprobe.

        close_candidates = (
            close_candidates[:10]
        )

        # ----------------------------------------------------
        # Получаем длительности
        # ----------------------------------------------------

        for candidate in close_candidates:

            candidate["duration"] = (
                get_duration(
                    candidate["url"]
                )
            )

        # ----------------------------------------------------
        # Показываем варианты
        # ----------------------------------------------------

        if len(close_candidates) > 1:

            print()
            print(
                "ВАРИАНТЫ С ВЫСОКИМ "
                "СОВПАДЕНИЕМ:"
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
                    f"] "
                    f"[совпадение: "
                    f"{candidate['score']}]"
                )

        # ----------------------------------------------------
        # Выбираем лучший
        # ----------------------------------------------------

        best = close_candidates[0]

        # ----------------------------------------------------
        # Если есть кандидат с практически
        # идеальным названием, отдаём
        # ему абсолютный приоритет.
        # ----------------------------------------------------

        ideal_candidates = []

        for candidate in close_candidates:

            filename_normalized = normalize(
                candidate["filename"]
            )

            artist_norm = normalize(
                artist
            )

            title_norm = normalize(
                title
            )

            artist_trans = transliterate(
                artist_norm
            )

            title_trans = transliterate(
                title_norm
            )

            ideal_1 = (
                artist_norm
                + " - "
                + title_norm
            )

            ideal_2 = (
                artist_trans
                + " - "
                + title_trans
            )

            if (
                filename_normalized == ideal_1
                or
                filename_normalized == ideal_2
            ):

                ideal_candidates.append(
                    candidate
                )

        if ideal_candidates:

            best = ideal_candidates[0]

        # ----------------------------------------------------
        # Результат
        # ----------------------------------------------------

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
            "Найдено как:",
            best["filename"]
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

            print(
                "HTTP:",
                r.status_code
            )

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

                encoded = (
                    link.split(
                        "/getmp3/",
                        1
                    )[1]
                )

                decoded = base64.b64decode(
                    encoded
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                decoded = unquote(
                    decoded
                )

                decoded_normalized = normalize(
                    decoded
                )

                artist_match = (
                    text_matches(
                        artist,
                        decoded_normalized
                    )
                    or
                    text_matches(
                        transliterate(artist),
                        decoded_normalized
                    )
                )

                title_match = (
                    text_matches(
                        title,
                        decoded_normalized
                    )
                    or
                    text_matches(
                        transliterate(title),
                        decoded_normalized
                    )
                )

                if (
                    artist_match
                    and
                    title_match
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
