import requests
import re
import json
import html
from urllib.parse import quote, urlparse


# ============================================================
# НАСТРОЙКИ
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}

TIMEOUT = 30


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def print_line():
    print("=" * 60)


def clean_text(value):

    if value is None:
        return ""

    value = html.unescape(
        str(value)
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    try:
        seconds = int(
            round(
                float(seconds)
            )
        )

    except Exception:
        return "??:??"

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )


def extract_duration(value):

    if value is None:
        return None

    value = str(value).strip()

    # --------------------------------------------------------
    # ISO 8601
    # --------------------------------------------------------

    match = re.match(
        r"^PT"
        r"(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+(?:\.\d+)?)S)?"
        r"$",
        value,
        re.I
    )

    if match:

        hours = int(
            match.group(1) or 0
        )

        minutes = int(
            match.group(2) or 0
        )

        seconds = float(
            match.group(3) or 0
        )

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    # --------------------------------------------------------
    # MM:SS / HH:MM:SS
    # --------------------------------------------------------

    if ":" in value:

        try:

            parts = value.split(":")

            if len(parts) == 2:

                return (
                    int(parts[0]) * 60
                    + float(parts[1])
                )

            if len(parts) == 3:

                return (
                    int(parts[0]) * 3600
                    + int(parts[1]) * 60
                    + float(parts[2])
                )

        except Exception:
            pass

    # --------------------------------------------------------
    # Миллисекунды
    # --------------------------------------------------------

    try:

        number = float(value)

        if number > 10000:
            return number / 1000

        return number

    except Exception:

        return None


def normalize(text):

    text = clean_text(
        text
    ).lower()

    text = text.replace(
        "ё",
        "е"
    )

    text = text.replace(
        "–",
        "-"
    )

    text = text.replace(
        "—",
        "-"
    )

    text = re.sub(
        r"[()[\]{}]",
        " ",
        text
    )

    text = re.sub(
        r"[,;|/\\]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def words(text):

    return {
        word
        for word in normalize(text).split()
        if word
    }


# ============================================================
# ПОЛУЧЕНИЕ СТРАНИЦЫ
# ============================================================

def get_page(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

    except requests.RequestException as e:

        print(
            "Ошибка HTTP:",
            e
        )

        return None, None

    if response.status_code != 200:

        print(
            "HTTP-код:",
            response.status_code
        )

        return None, response

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text, response


# ============================================================
# JSON-LD
# ============================================================

def find_json_ld(text):

    results = []

    pattern = re.compile(
        r'<script[^>]+type=["\']'
        r'application/ld\+json'
        r'["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        re.I | re.S
    )

    for block in pattern.findall(
        text
    ):

        block = html.unescape(
            block.strip()
        )

        try:

            data = json.loads(
                block
            )

            results.append(
                data
            )

        except Exception:
            continue

    return results


# ============================================================
# META-ТЕГИ
# ============================================================

def find_meta_tags(text):

    result = {}

    pattern = re.compile(
        r'<meta\s+'
        r'([^>]+?)'
        r'/?>',
        re.I | re.S
    )

    for attributes in pattern.findall(
        text
    ):

        name_match = re.search(
            r'(?:property|name|itemprop)'
            r'\s*=\s*["\']([^"\']+)["\']',
            attributes,
            re.I
        )

        content_match = re.search(
            r'content\s*=\s*["\']'
            r'([^"\']*)["\']',
            attributes,
            re.I | re.S
        )

        if not name_match:
            continue

        if not content_match:
            continue

        key = (
            name_match
            .group(1)
            .strip()
            .lower()
        )

        value = clean_text(
            content_match.group(1)
        )

        result[key] = value

    return result


# ============================================================
# ИЗВЛЕЧЕНИЕ ТРЕКА ИЗ СТРАНИЦЫ
# ============================================================

def extract_track_from_page(
    text,
    url
):

    meta = find_meta_tags(
        text
    )

    json_ld = find_json_ld(
        text
    )

    track = {
        "artist": "",
        "title": "",
        "album": "",
        "duration": None,
        "cover_url": "",
        "url": url,
    }

    # --------------------------------------------------------
    # OpenGraph
    # --------------------------------------------------------

    if meta.get("og:title"):

        track["title"] = clean_text(
            meta["og:title"]
        )

    if meta.get("og:image"):

        track["cover_url"] = (
            meta["og:image"]
        )

    if meta.get("og:url"):

        track["url"] = (
            meta["og:url"]
        )

    # --------------------------------------------------------
    # og:description
    #
    # Например:
    # Scally Milano, 163ONMYNECK • Трек • 2022
    # --------------------------------------------------------

    description = meta.get(
        "og:description",
        ""
    )

    if description:

        description = clean_text(
            description
        )

        parts = [
            part.strip()
            for part in description.split("•")
        ]

        if parts:

            artists = parts[0]

            if artists:

                track["artist"] = (
                    artists
                )

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    def process(obj):

        if isinstance(
            obj,
            list
        ):

            for item in obj:
                process(item)

            return

        if not isinstance(
            obj,
            dict
        ):

            return

        obj_type = obj.get(
            "@type"
        )

        # ----------------------------------------------------
        # MusicRecording
        # ----------------------------------------------------

        if (
            obj_type == "MusicRecording"
            or
            (
                isinstance(
                    obj_type,
                    list
                )
                and
                "MusicRecording"
                in obj_type
            )
        ):

            name = obj.get(
                "name"
            )

            if name:

                track["title"] = (
                    clean_text(name)
                )

            artist = (
                obj.get("byArtist")
                or obj.get("artist")
                or obj.get("author")
            )

            if isinstance(
                artist,
                dict
            ):

                name = artist.get(
                    "name"
                )

                if name:

                    track["artist"] = (
                        clean_text(name)
                    )

            elif isinstance(
                artist,
                list
            ):

                names = []

                for item in artist:

                    if isinstance(
                        item,
                        dict
                    ):

                        name = item.get(
                            "name"
                        )

                        if name:

                            names.append(
                                clean_text(
                                    name
                                )
                            )

                if names:

                    track["artist"] = (
                        ", ".join(names)
                    )

            elif artist:

                track["artist"] = (
                    clean_text(artist)
                )

            duration = obj.get(
                "duration"
            )

            if duration:

                track["duration"] = (
                    extract_duration(
                        duration
                    )
                )

            album = obj.get(
                "inAlbum"
            )

            if isinstance(
                album,
                dict
            ):

                name = album.get(
                    "name"
                )

                if name:

                    track["album"] = (
                        clean_text(name)
                    )

            elif album:

                track["album"] = (
                    clean_text(album)
                )

            image = obj.get(
                "image"
            )

            if isinstance(
                image,
                dict
            ):

                image = image.get(
                    "url"
                )

            if image:

                track["cover_url"] = (
                    clean_text(image)
                )

            obj_url = obj.get(
                "url"
            )

            if obj_url:

                track["url"] = (
                    clean_text(obj_url)
                )

    for item in json_ld:

        process(item)

    # --------------------------------------------------------
    # Дополнительный поиск
    # --------------------------------------------------------

    if not track["artist"]:

        match = re.search(
            r'"artistName"\s*:\s*"([^"]+)"',
            text,
            re.I
        )

        if match:

            track["artist"] = clean_text(
                match.group(1)
            )

    if not track["album"]:

        match = re.search(
            r'"albumTitle"\s*:\s*"([^"]+)"',
            text,
            re.I
        )

        if match:

            track["album"] = clean_text(
                match.group(1)
            )

    if track["duration"] is None:

        match = re.search(
            r'"durationMs"\s*:\s*(\d+)',
            text,
            re.I
        )

        if match:

            track["duration"] = (
                int(
                    match.group(1)
                )
                / 1000
            )

    return track


# ============================================================
# ПОИСК КАНДИДАТОВ
# ============================================================

def find_candidate_urls(
    text
):

    candidates = []

    # --------------------------------------------------------
    # Прямые URL треков
    # --------------------------------------------------------

    patterns = [

        r'https?://music\.yandex\.(?:ru|com)'
        r'/album/\d+/track/\d+[^"\']*',

        r'//music\.yandex\.(?:ru|com)'
        r'/album/\d+/track/\d+[^"\']*',

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.I
        )

        for url in matches:

            url = html.unescape(
                url
            )

            url = url.replace(
                "\\/",
                "/"
            )

            if url.startswith("//"):

                url = (
                    "https:"
                    + url
                )

            if url not in candidates:

                candidates.append(
                    url
                )

    return candidates


# ============================================================
# ОЦЕНКА КАНДИДАТА
# ============================================================

def score_candidate(
    track,
    wanted_artist,
    wanted_title
):

    candidate_artist = normalize(
        track.get("artist", "")
    )

    candidate_title = normalize(
        track.get("title", "")
    )

    wanted_artist = normalize(
        wanted_artist
    )

    wanted_title = normalize(
        wanted_title
    )

    if not candidate_artist:
        return -100000

    if not candidate_title:
        return -100000

    score = 0

    artist_words = words(
        wanted_artist
    )

    title_words = words(
        wanted_title
    )

    candidate_artist_words = words(
        candidate_artist
    )

    candidate_title_words = words(
        candidate_title
    )

    # --------------------------------------------------------
    # Исполнитель
    # --------------------------------------------------------

    if wanted_artist == candidate_artist:

        score += 1000

    elif (
        wanted_artist in candidate_artist
        or
        candidate_artist in wanted_artist
    ):

        score += 700

    else:

        common = (
            artist_words
            &
            candidate_artist_words
        )

        if artist_words:

            ratio = (
                len(common)
                /
                len(artist_words)
            )

            if ratio >= 0.75:

                score += 500

            elif ratio >= 0.5:

                score += 250

    # --------------------------------------------------------
    # Название
    # --------------------------------------------------------

    if wanted_title == candidate_title:

        score += 1000

    elif (
        wanted_title in candidate_title
        or
        candidate_title in wanted_title
    ):

        score += 700

    else:

        common = (
            title_words
            &
            candidate_title_words
        )

        if title_words:

            ratio = (
                len(common)
                /
                len(title_words)
            )

            if ratio >= 0.75:

                score += 500

            elif ratio >= 0.5:

                score += 250

    # --------------------------------------------------------
    # Точный составной запрос
    # --------------------------------------------------------

    combined_1 = (
        wanted_artist
        + " "
        + wanted_title
    )

    combined_2 = (
        wanted_title
        + " "
        + wanted_artist
    )

    combined_candidate = (
        candidate_artist
        + " "
        + candidate_title
    )

    if (
        combined_1
        in combined_candidate
    ):

        score += 500

    if (
        combined_2
        in combined_candidate
    ):

        score += 500

    return score


# ============================================================
# ПОИСК ЧЕРЕЗ ЯНДЕКС
# ============================================================

def search_yandex(
    artist,
    title
):

    query = (
        f"{artist} {title}"
    ).strip()

    print()
    print(
        "Поисковый запрос:"
    )

    print(
        query
    )

    # --------------------------------------------------------
    # Используем страницу поиска Яндекс Музыки
    # --------------------------------------------------------

    search_url = (
        "https://music.yandex.ru/search?"
        "text="
        + quote(query)
    )

    print()
    print(
        "URL поиска:"
    )

    print(
        search_url
    )

    text, response = get_page(
        search_url
    )

    if text is None:

        return []

    print()
    print(
        "Страница поиска получена."
    )

    print(
        "Размер:",
        len(
            response.content
        ),
        "байт"
    )

    # --------------------------------------------------------
    # Находим URL треков
    # --------------------------------------------------------

    urls = find_candidate_urls(
        text
    )

    print(
        "Найдено URL треков:",
        len(urls)
    )

    if not urls:

        return []

    results = []

    # --------------------------------------------------------
    # Обрабатываем найденные страницы
    # --------------------------------------------------------

    max_candidates = 10

    for index, url in enumerate(
        urls[:max_candidates],
        1
    ):

        print()
        print(
            f"Проверка кандидата "
            f"{index}/{min(len(urls), max_candidates)}..."
        )

        candidate_text, candidate_response = (
            get_page(url)
        )

        if candidate_text is None:

            continue

        track = extract_track_from_page(
            candidate_text,
            candidate_response.url
        )

        track["score"] = score_candidate(
            track,
            artist,
            title
        )

        if track["score"] <= 0:

            continue

        results.append(
            track
        )

    # --------------------------------------------------------
    # Сортировка
    # --------------------------------------------------------

    results.sort(
        key=lambda item:
            item["score"],
        reverse=True
    )

    return results


# ============================================================
# ВЫВОД РЕЗУЛЬТАТОВ
# ============================================================

def print_results(
    results
):

    print()
    print_line()

    print(
        "РЕЗУЛЬТАТЫ ПОИСКА"
    )

    print_line()

    if not results:

        print()

        print(
            "Подходящих треков не найдено."
        )

        return

    for index, track in enumerate(
        results,
        1
    ):

        print()

        print(
            f"[{index}] "
            f"{track['artist']} — "
            f"{track['title']}"
        )

        print(
            "    Альбом:",
            track["album"]
            or
            "не определён"
        )

        print(
            "    Длительность:",
            format_duration(
                track["duration"]
            )
        )

        print(
            "    Оценка:",
            track["score"]
        )

        print(
            "    URL:",
            track["url"]
        )

        print(
            "    Обложка:",
            "есть"
            if track["cover_url"]
            else
            "нет"
        )

        if track["cover_url"]:

            print(
                "    Cover URL:",
                track["cover_url"]
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print_line()

    print(
        "YANDEX MUSIC SEARCH TEST"
    )

    print_line()

    print()

    print(
        "Этот тест ищет трек напрямую "
        "через веб-страницу Яндекс Музыки."
    )

    print(
        "yt-dlp здесь НЕ используется."
    )

    print()

    artist = input(
        "Исполнитель: "
    ).strip()

    title = input(
        "Название:    "
    ).strip()

    if not artist or not title:

        print()

        print(
            "Исполнитель и название "
            "должны быть указаны."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    results = search_yandex(
        artist,
        title
    )

    print_results(
        results
    )

    print()

    print_line()

    if results:

        print(
            "ТЕСТ ПОИСКА ПРОЙДЕН"
        )

    else:

        print(
            "ТЕСТ ПОИСКА НЕ ПРОЙДЕН"
        )

    print_line()

    print()

    input(
        "Нажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
