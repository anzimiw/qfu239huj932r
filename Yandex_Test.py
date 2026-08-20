import requests
import re
import json
import html
from urllib.parse import urlparse


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

    # ISO 8601: PT3M42S
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

    # MM:SS
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

    # Просто число секунд
    try:
        return float(value)

    except Exception:
        return None


# ============================================================
# ПОЛУЧЕНИЕ HTML
# ============================================================

def get_page(url):

    print()
    print(
        "Запрос страницы Яндекс Музыки..."
    )

    print()

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

    except requests.RequestException as e:

        print()
        print(
            "ОШИБКА HTTP-запроса:"
        )

        print(e)

        return None

    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Конечный URL:",
        response.url
    )

    print(
        "Размер ответа:",
        len(response.content),
        "байт"
    )

    if response.status_code != 200:

        print()
        print(
            "Яндекс вернул HTTP-код, "
            "отличный от 200."
        )

        return None

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text


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

    blocks = pattern.findall(
        text
    )

    for block in blocks:

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

        property_match = re.search(
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

        if not property_match:
            continue

        if not content_match:
            continue

        key = (
            property_match
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
# ПОИСК ТЕКСТОВЫХ ПОЛЕЙ
# ============================================================

def find_first(patterns, text):

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I | re.S
        )

        if match:

            value = clean_text(
                match.group(1)
            )

            if value:
                return value

    return ""


# ============================================================
# ИЗВЛЕЧЕНИЕ ДАННЫХ
# ============================================================

def extract_info(text, url):

    meta = find_meta_tags(
        text
    )

    json_ld = find_json_ld(
        text
    )

    info = {
        "artist": "",
        "title": "",
        "album": "",
        "duration": None,
        "cover": "",
        "url": url,
    }

    # --------------------------------------------------------
    # OpenGraph
    # --------------------------------------------------------

    og_title = meta.get(
        "og:title",
        ""
    )

    og_image = meta.get(
        "og:image",
        ""
    )

    og_url = meta.get(
        "og:url",
        ""
    )

    if og_image:
        info["cover"] = og_image

    if og_url:
        info["url"] = og_url

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    def process_jsonld(obj):

        if isinstance(
            obj,
            list
        ):

            for item in obj:
                process_jsonld(item)

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
        # Название
        # ----------------------------------------------------

        if not info["title"]:

            name = obj.get(
                "name"
            )

            if name:

                info["title"] = (
                    clean_text(name)
                )

        # ----------------------------------------------------
        # Исполнитель
        # ----------------------------------------------------

        if not info["artist"]:

            author = (
                obj.get("byArtist")
                or obj.get("author")
            )

            if isinstance(
                author,
                dict
            ):

                name = author.get(
                    "name"
                )

                if name:

                    info["artist"] = (
                        clean_text(name)
                    )

            elif isinstance(
                author,
                list
            ):

                names = []

                for item in author:

                    if isinstance(
                        item,
                        dict
                    ):

                        name = item.get(
                            "name"
                        )

                        if name:
                            names.append(
                                clean_text(name)
                            )

                if names:

                    info["artist"] = (
                        ", ".join(names)
                    )

            elif author:

                info["artist"] = (
                    clean_text(author)
                )

        # ----------------------------------------------------
        # Альбом
        # ----------------------------------------------------

        if not info["album"]:

            album = (
                obj.get("inAlbum")
                or obj.get("album")
            )

            if isinstance(
                album,
                dict
            ):

                name = album.get(
                    "name"
                )

                if name:

                    info["album"] = (
                        clean_text(name)
                    )

            elif album:

                info["album"] = (
                    clean_text(album)
                )

        # ----------------------------------------------------
        # Длительность
        # ----------------------------------------------------

        if info["duration"] is None:

            duration = (
                obj.get("duration")
            )

            if duration:

                info["duration"] = (
                    extract_duration(
                        duration
                    )
                )

        # ----------------------------------------------------
        # Обложка
        # ----------------------------------------------------

        if not info["cover"]:

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

            elif isinstance(
                image,
                list
            ):

                if image:

                    image = image[0]

                    if isinstance(
                        image,
                        dict
                    ):

                        image = image.get(
                            "url"
                        )

            if image:

                info["cover"] = (
                    clean_text(image)
                )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if not info["url"]:

            obj_url = obj.get(
                "url"
            )

            if obj_url:

                info["url"] = (
                    clean_text(obj_url)
                )

    for item in json_ld:

        process_jsonld(
            item
        )

    # --------------------------------------------------------
    # Meta title как резерв
    # --------------------------------------------------------

    if not info["title"]:

        if og_title:

            info["title"] = (
                clean_text(og_title)
            )

    # --------------------------------------------------------
    # Попытка найти дополнительные
    # данные в HTML
    # --------------------------------------------------------

    if not info["artist"]:

        info["artist"] = find_first(
            [
                r'"artist"\s*:\s*"([^"]+)"',
                r'"artistName"\s*:\s*"([^"]+)"',
                r'"artists"\s*:\s*\[\s*\{\s*"name"\s*:\s*"([^"]+)"',
            ],
            text
        )

    if not info["title"]:

        info["title"] = find_first(
            [
                r'"track"\s*:\s*"([^"]+)"',
                r'"trackTitle"\s*:\s*"([^"]+)"',
                r'"title"\s*:\s*"([^"]+)"',
            ],
            text
        )

    if not info["album"]:

        info["album"] = find_first(
            [
                r'"album"\s*:\s*"([^"]+)"',
                r'"albumTitle"\s*:\s*"([^"]+)"',
            ],
            text
        )

    if info["duration"] is None:

        duration_value = find_first(
            [
                r'"duration"\s*:\s*"([^"]+)"',
                r'"durationMs"\s*:\s*(\d+)',
            ],
            text
        )

        if duration_value:

            if duration_value.isdigit():

                info["duration"] = (
                    float(duration_value)
                    / 1000
                )

            else:

                info["duration"] = (
                    extract_duration(
                        duration_value
                    )
                )

    # --------------------------------------------------------
    # Отчёт о найденном
    # --------------------------------------------------------

    return info, meta, json_ld


# ============================================================
# ВЫВОД РЕЗУЛЬТАТА
# ============================================================

def print_result(
    info,
    meta,
    json_ld,
    html_size
):

    print()
    print_line()

    print(
        "РЕЗУЛЬТАТ АНАЛИЗА"
    )

    print_line()

    print()

    print(
        "Исполнитель:",
        info["artist"]
        or "НЕ НАЙДЕН"
    )

    print(
        "Название:   ",
        info["title"]
        or "НЕ НАЙДЕНО"
    )

    print(
        "Альбом:     ",
        info["album"]
        or "НЕ НАЙДЕН"
    )

    print(
        "Длительность:",
        format_duration(
            info["duration"]
        )
    )

    print(
        "Обложка:    ",
        "НАЙДЕНА"
        if info["cover"]
        else
        "НЕ НАЙДЕНА"
    )

    if info["cover"]:

        print()
        print(
            "URL обложки:"
        )

        print(
            info["cover"]
        )

    print()

    print(
        "URL страницы:"
    )

    print(
        info["url"]
    )

    print()
    print_line()

    print(
        "ДИАГНОСТИКА"
    )

    print_line()

    print()

    print(
        "Размер HTML:",
        html_size,
        "байт"
    )

    print(
        "JSON-LD блоков:",
        len(json_ld)
    )

    print(
        "Meta-тегов:",
        len(meta)
    )

    # --------------------------------------------------------
    # Показываем интересующие meta
    # --------------------------------------------------------

    interesting = [
        "og:title",
        "og:description",
        "og:image",
        "og:url",
        "twitter:title",
        "twitter:image"
    ]

    found_meta = []

    for key in interesting:

        if key in meta:

            found_meta.append(
                key
            )

    print()

    print(
        "Интересующие meta:"
    )

    if found_meta:

        for key in found_meta:

            print(
                " ",
                key,
                "=",
                meta[key]
            )

    else:

        print(
            "  не найдены"
        )

    # --------------------------------------------------------
    # JSON-LD типы
    # --------------------------------------------------------

    print()

    print(
        "Типы JSON-LD:"
    )

    types = []

    def collect_types(obj):

        if isinstance(
            obj,
            list
        ):

            for item in obj:
                collect_types(item)

        elif isinstance(
            obj,
            dict
        ):

            obj_type = obj.get(
                "@type"
            )

            if obj_type:

                if isinstance(
                    obj_type,
                    list
                ):

                    types.extend(
                        obj_type
                    )

                else:

                    types.append(
                        str(obj_type)
                    )

    for item in json_ld:

        collect_types(
            item
        )

    types = list(
        dict.fromkeys(
            types
        )
    )

    if types:

        for item in types:

            print(
                " ",
                item
            )

    else:

        print(
            "  не найдены"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print_line()

    print(
        "YANDEX MUSIC DIRECT TEST"
    )

    print_line()

    print()

    print(
        "Этот тест НЕ использует yt-dlp."
    )

    print(
        "Он напрямую получает HTML "
        "страницы Яндекс Музыки."
    )

    print()

    url = input(
        "Ссылка на Яндекс Музыку: "
    ).strip()

    if not url:

        print()

        print(
            "Ссылка не указана."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # Проверка URL
    # --------------------------------------------------------

    parsed = urlparse(
        url
    )

    hostname = (
        parsed.hostname
        or ""
    ).lower()

    if (
        hostname
        not in (
            "music.yandex.ru",
            "music.yandex.com",
        )
    ):

        print()

        print(
            "ВНИМАНИЕ:"
        )

        print(
            "Домен ссылки не похож "
            "на Яндекс Музыку."
        )

        print()

        choice = input(
            "Продолжить? [y/n]: "
        ).strip().lower()

        if choice not in (
            "y",
            "д",
            "да"
        ):

            return

    # --------------------------------------------------------
    # Получение страницы
    # --------------------------------------------------------

    text = get_page(
        url
    )

    if text is None:

        print()

        print_line()

        print(
            "ТЕСТ НЕ ПРОЙДЕН"
        )

        print_line()

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # Извлечение данных
    # --------------------------------------------------------

    info, meta, json_ld = (
        extract_info(
            text,
            url
        )
    )

    # --------------------------------------------------------
    # Вывод
    # --------------------------------------------------------

    print_result(
        info,
        meta,
        json_ld,
        len(
            text.encode(
                "utf-8",
                errors="replace"
            )
        )
    )

    print()

    print_line()

    if (
        info["artist"]
        or info["title"]
        or info["album"]
        or info["cover"]
    ):

        print(
            "ТЕСТ ЧАСТИЧНО/ПОЛНОСТЬЮ ПРОЙДЕН"
        )

    else:

        print(
            "ДАННЫЕ НЕ НАЙДЕНЫ"
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
