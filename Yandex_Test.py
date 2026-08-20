import requests
import json
import re
import html
import time
from urllib.parse import quote


# ============================================================
# НАСТРОЙКИ
# ============================================================

TIMEOUT = 30

TEST_FILE = "yandex_test.mp3"

BASE_HEADERS = {
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

    "Accept-Language":
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",

    "Connection":
        "keep-alive"
}


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def line():
    print("=" * 60)


def duration_text(seconds):
    try:
        seconds = int(round(float(seconds)))

        return (
            f"{seconds // 60}:"
            f"{seconds % 60:02d}"
        )

    except Exception:
        return "??:??"


def get_artists(track):
    artists = track.get("artists") or []

    names = []

    for artist in artists:

        if isinstance(artist, dict):

            name = artist.get("name")

            if name:
                names.append(
                    str(name)
                )

    return ", ".join(names)


def get_cover(track):

    cover = (
        track.get("ogImage")
        or track.get("coverUri")
    )

    if not cover:
        return None

    if cover.startswith("//"):
        cover = "https:" + cover

    if cover.startswith("avatars."):
        cover = "https://" + cover

    cover = cover.replace(
        "%%",
        "m1000x1000"
    )

    return cover


# ============================================================
# API ПОИСКА
# ============================================================

def search_yandex(
    session,
    artist,
    title
):

    query = (
        f"{artist} {title}"
    )

    print()
    print("=" * 60)
    print("1. ПОИСК ТРЕКА")
    print("=" * 60)

    print()
    print(
        "Запрос:",
        query
    )

    url = (
        "https://api.music.yandex.net/search"
    )

    params = {
        "text": query,
        "page": 0,
        "type": "track",
        "nococrrect": "true"
    }

    print(
        "API:",
        url
    )

    print()
    print(
        "Отправка запроса..."
    )

    try:

        response = session.get(
            url,
            params=params,
            timeout=TIMEOUT
        )

    except Exception as e:

        print(
            "ОШИБКА:",
            e
        )

        return None

    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Размер:",
        len(response.content),
        "байт"
    )

    if response.status_code != 200:

        print(
            response.text[:2000]
        )

        return None

    try:

        data = response.json()

    except Exception:

        print(
            "Ответ не является JSON."
        )

        return None

    result = data.get(
        "result"
    ) or {}

    tracks = (
        result.get("tracks")
        or {}
    )

    results = (
        tracks.get("results")
        or []
    )

    print(
        "Найдено:",
        len(results)
    )

    if not results:
        return None

    # --------------------------------------------------------
    # ОЦЕНКА
    # --------------------------------------------------------

    artist_normalized = artist.lower()
    title_normalized = title.lower()

    candidates = []

    for track in results:

        if not isinstance(
            track,
            dict
        ):
            continue

        track_title = str(
            track.get("title")
            or ""
        )

        track_artists = get_artists(
            track
        )

        candidate_text = (
            track_artists +
            " " +
            track_title
        ).lower()

        score = 0

        if (
            title_normalized
            in track_title.lower()
        ):
            score += 1000

        if (
            artist_normalized
            in track_artists.lower()
        ):
            score += 500

        duration_ms = track.get(
            "durationMs"
        )

        if duration_ms:
            score += 500

        candidates.append(
            (
                score,
                track
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    score, track = candidates[0]

    albums = (
        track.get("albums")
        or []
    )

    album = ""

    album_id = None

    if albums:

        album = (
            albums[0].get("title")
            or ""
        )

        album_id = (
            albums[0].get("id")
        )

    selected = {
        "id":
            track.get("id"),

        "artist":
            get_artists(track),

        "title":
            track.get("title") or "",

        "album":
            album,

        "album_id":
            album_id,

        "duration":
            (
                float(
                    track.get(
                        "durationMs"
                    )
                ) / 1000
                if track.get("durationMs")
                else None
            ),

        "cover_url":
            get_cover(track),

        "available":
            track.get("available"),

        "lyrics_info":
            track.get(
                "lyricsInfo"
            ),

        "score":
            score
    }

    print()
    print(
        "Выбран:"
    )

    print(
        "Исполнитель:",
        selected["artist"]
    )

    print(
        "Название:",
        selected["title"]
    )

    print(
        "Альбом:",
        selected["album"]
    )

    print(
        "Длительность:",
        duration_text(
            selected["duration"]
        )
    )

    print(
        "ID:",
        selected["id"]
    )

    print(
        "Оценка:",
        selected["score"]
    )

    return selected


# ============================================================
# DOWNLOAD-INFO
# ============================================================

def get_download_info(
    session,
    track_id
):

    print()
    print("=" * 60)
    print("2. ПОЛУЧЕНИЕ DOWNLOAD-INFO")
    print("=" * 60)

    url = (
        "https://api.music.yandex.net/"
        f"tracks/{track_id}/download-info"
    )

    print()
    print(
        "URL:"
    )

    print(url)

    print()
    print(
        "Отправка запроса..."
    )

    try:

        response = session.get(
            url,
            timeout=TIMEOUT
        )

    except Exception as e:

        print(
            "ОШИБКА:",
            e
        )

        return None

    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Размер:",
        len(response.content),
        "байт"
    )

    if response.status_code != 200:

        print()
        print(
            response.text[:3000]
        )

        return None

    try:

        data = response.json()

    except Exception:

        print(
            "Ответ не является JSON."
        )

        return None

    result = (
        data.get("result")
        or []
    )

    if not isinstance(
        result,
        list
    ):

        result = [result]

    print()
    print(
        "Вариантов:",
        len(result)
    )

    for index, item in enumerate(
        result,
        1
    ):

        print()
        print(
            f"ВАРИАНТ {index}"
        )

        print(
            "  codec:",
            item.get("codec")
        )

        print(
            "  bitrate:",
            item.get("bitrate"),
            "kbps"
        )

        print(
            "  preview:",
            item.get("preview")
        )

        print(
            "  direct:",
            item.get("direct")
        )

        print(
            "  gain:",
            item.get("gain")
        )

        print(
            "  container:",
            item.get("container")
        )

        print(
            "  downloadInfoUrl:",
            item.get(
                "downloadInfoUrl"
            )
        )

    # Предпочитаем MP3
    mp3 = [
        item
        for item in result
        if item.get("codec") == "mp3"
    ]

    if not mp3:
        return None

    # Предпочитаем самый высокий bitrate
    mp3.sort(
        key=lambda x:
            x.get("bitrate") or 0,
        reverse=True
    )

    selected = mp3[0]

    print()
    print("=" * 60)
    print("ВЫБРАННЫЙ MP3")
    print("=" * 60)

    print()
    print(
        "Bitrate:",
        selected.get("bitrate")
    )

    print(
        "Preview:",
        selected.get("preview")
    )

    print(
        "Direct:",
        selected.get("direct")
    )

    return selected


# ============================================================
# DOWNLOAD-INFO XML
# ============================================================

def get_storage_url(
    session,
    download_info_url
):

    print()
    print("=" * 60)
    print("3. ПОЛУЧЕНИЕ ДАННЫХ ФАЙЛА")
    print("=" * 60)

    print()
    print(
        "Запрос downloadInfoUrl..."
    )

    print(
        "URL:"
    )

    print(
        download_info_url
    )

    try:

        response = session.get(
            download_info_url,
            timeout=TIMEOUT,
            allow_redirects=True
        )

    except Exception as e:

        print(
            "ОШИБКА:",
            e
        )

        return None

    print()
    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Размер:",
        len(response.content),
        "байт"
    )

    print()
    print(
        "Конечный URL:"
    )

    print(
        response.url
    )

    if response.status_code != 200:

        print()
        print(
            response.text[:3000]
        )

        return None

    xml = response.text.strip()

    print()
    print(
        "Ответ XML:"
    )

    print(xml)

    def get_tag(name):

        match = re.search(
            rf"<{name}>(.*?)</{name}>",
            xml,
            re.I
        )

        if match:
            return html.unescape(
                match.group(1)
            )

        return None

    host = get_tag("host")
    path = get_tag("path")
    ts = get_tag("ts")
    signature = get_tag("s")

    print()
    print(
        "Распознанные параметры:"
    )

    print(
        "host:",
        host
    )

    print(
        "path:",
        path
    )

    print(
        "ts:",
        ts
    )

    print(
        "s:",
        "получен"
        if signature
        else "НЕ ПОЛУЧЕН"
    )

    if not host or not path:

        print()
        print(
            "Не удалось собрать storage URL."
        )

        return None

    storage_url = (
        "https://"
        + host
        + path
    )

    params = []

    if ts:
        params.append(
            "ts=" + quote(ts)
        )

    if signature:
        params.append(
            "s=" + quote(signature)
        )

    if params:
        storage_url += (
            "?"
            +
            "&".join(params)
        )

    print()
    print(
        "Сформированный URL:"
    )

    print(
        storage_url
    )

    return storage_url


# ============================================================
# ТЕСТ ОДНОГО ЗАПРОСА
# ============================================================

def test_request(
    session,
    name,
    url,
    headers,
    output_file
):

    print()
    print("-" * 60)
    print(
        name
    )
    print("-" * 60)

    print()
    print(
        "Заголовки:"
    )

    for key, value in headers.items():

        print(
            f"  {key}: {value}"
        )

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=60,
            stream=True,
            allow_redirects=True
        )

    except Exception as e:

        print()
        print(
            "ОШИБКА:",
            repr(e)
        )

        return False

    print()
    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Конечный URL:",
        response.url
    )

    print(
        "Content-Type:",
        response.headers.get(
            "Content-Type"
        )
    )

    print(
        "Content-Length:",
        response.headers.get(
            "Content-Length"
        )
    )

    print(
        "Server:",
        response.headers.get(
            "Server"
        )
    )

    print(
        "Location:",
        response.headers.get(
            "Location"
        )
    )

    print()
    print(
        "Ответные cookies:"
    )

    if response.cookies:

        for key, value in response.cookies.items():

            print(
                f"  {key}={value}"
            )

    else:

        print(
            "  отсутствуют"
        )

    # --------------------------------------------------------
    # УСПЕХ
    # --------------------------------------------------------

    if response.status_code in (
        200,
        206
    ):

        total = 0

        try:

            with open(
                output_file,
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=262144
                ):

                    if chunk:

                        file.write(
                            chunk
                        )

                        total += len(
                            chunk
                        )

            print()
            print(
                "Получено:",
                total,
                "байт"
            )

            if total > 10000:

                print()
                print(
                    "УСПЕХ: storage отдал "
                    "аудиоданные."
                )

                return True

        except Exception as e:

            print(
                "Ошибка записи:",
                e
            )

            return False

    # --------------------------------------------------------
    # ОШИБКА
    # --------------------------------------------------------

    print()

    try:

        body = response.text

        print(
            "Тело ответа:"
        )

        print(
            body[:3000]
        )

    except Exception:
        pass

    return False


# ============================================================
# ДИАГНОСТИКА STORAGE
# ============================================================

def diagnose_storage(
    storage_url
):

    print()
    print("=" * 60)
    print("4. ДИАГНОСТИКА STORAGE")
    print("=" * 60)

    print()
    print(
        "Будет выполнено несколько запросов "
        "к одному storage URL."
    )

    print(
        "Основной проект при этом не изменяется."
    )

    session = requests.Session()

    # --------------------------------------------------------
    # Базовая сессия
    # --------------------------------------------------------

    session.headers.update(
        BASE_HEADERS
    )

    tests = []

    tests.append(
        (
            "ТЕСТ 1 — Обычный GET",
            {}
        )
    )

    tests.append(
        (
            "ТЕСТ 2 — Referer Яндекс Музыки",
            {
                "Referer":
                    "https://music.yandex.ru/"
            }
        )
    )

    tests.append(
        (
            "ТЕСТ 3 — Referer + Origin",
            {
                "Referer":
                    "https://music.yandex.ru/",
                "Origin":
                    "https://music.yandex.ru"
            }
        )
    )

    tests.append(
        (
            "ТЕСТ 4 — AJAX-запрос",
            {
                "Referer":
                    "https://music.yandex.ru/",
                "Origin":
                    "https://music.yandex.ru",
                "Accept":
                    "*/*",
                "Sec-Fetch-Dest":
                    "empty",
                "Sec-Fetch-Mode":
                    "cors",
                "Sec-Fetch-Site":
                    "same-site"
            }
        )
    )

    tests.append(
        (
            "ТЕСТ 5 — Audio Accept",
            {
                "Referer":
                    "https://music.yandex.ru/",
                "Accept":
                    "audio/mpeg,audio/*;q=0.9,*/*;q=0.8"
            }
        )
    )

    # --------------------------------------------------------
    # Запускаем
    # --------------------------------------------------------

    for index, (
        name,
        headers
    ) in enumerate(
        tests,
        1
    ):

        output = (
            f"yandex_test_{index}.mp3"
        )

        success = test_request(
            session,
            name,
            storage_url,
            headers,
            output
        )

        if success:

            print()
            print("=" * 60)
            print(
                "СТОП — РАБОЧИЙ ВАРИАНТ НАЙДЕН"
            )
            print("=" * 60)

            print()
            print(
                "Рабочий тест:",
                name
            )

            print(
                "Файл:",
                output
            )

            return True

        time.sleep(
            0.5
        )

    # --------------------------------------------------------
    # Попытка через новую сессию с Referer
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "ТЕСТ 6 — НОВАЯ SESSION"
    )
    print("=" * 60)

    new_session = requests.Session()

    new_session.headers.update({
        "User-Agent":
            BASE_HEADERS["User-Agent"],

        "Accept":
            "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",

        "Accept-Language":
            BASE_HEADERS["Accept-Language"],

        "Referer":
            "https://music.yandex.ru/",

        "Origin":
            "https://music.yandex.ru",

        "Connection":
            "keep-alive"
    })

    success = test_request(
        new_session,
        "ТЕСТ 6 — Новая Session",
        storage_url,
        {},
        "yandex_test_6.mp3"
    )

    if success:

        print()
        print(
            "Найден рабочий вариант."
        )

        return True

    print()
    print("=" * 60)
    print(
        "ВСЕ ТЕСТЫ STORAGE ЗАВЕРШИЛИСЬ 401"
    )
    print("=" * 60)

    print()
    print(
        "Это означает, что одного "
        "сформированного storage URL "
        "недостаточно."
    )

    print()
    print(
        "Следующий этап — определить, "
        "требуется ли Яндексом дополнительная "
        "авторизация/подпись/сессионные данные."
    )

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "YANDEX MUSIC STORAGE DIAGNOSTIC"
    )
    print("=" * 60)

    print()
    print(
        "Этот тест НЕ изменяет downloader.py."
    )

    print(
        "Он НЕ использует браузер."
    )

    print(
        "Он НЕ использует cookies "
        "из установленного браузера."
    )

    print(
        "Он только проверяет HTTP-доступ "
        "к Яндекс Музыке и storage."
    )

    print()

    artist = input(
        "Исполнитель: "
    ).strip()

    title = input(
        "Название:    "
    ).strip()

    duration_input = input(
        "Длительность в секундах "
        "(Enter — пропустить): "
    ).strip()

    duration = None

    if duration_input:

        try:

            duration = float(
                duration_input
            )

        except Exception:

            print(
                "Некорректная длительность."
            )

            duration = None

    if not artist or not title:

        print()
        print(
            "Исполнитель и название "
            "обязательны."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    session = requests.Session()

    session.headers.update(
        BASE_HEADERS
    )

    track = search_yandex(
        session,
        artist,
        title
    )

    if not track:

        print()
        line()
        print(
            "ПОИСК НЕ ПРОЙДЕН"
        )
        line()

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # Проверка длительности
    if duration is not None:

        difference = abs(
            track["duration"]
            - duration
        )

        print()
        print(
            "Разница длительности:",
            round(difference, 2),
            "сек."
        )

    download_info = get_download_info(
        session,
        track["id"]
    )

    if not download_info:

        print()
        line()
        print(
            "DOWNLOAD-INFO НЕ ПОЛУЧЕН"
        )
        line()

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    download_info_url = (
        download_info.get(
            "downloadInfoUrl"
        )
    )

    if not download_info_url:

        print()
        line()
        print(
            "DOWNLOAD INFO URL ОТСУТСТВУЕТ"
        )
        line()

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    storage_url = get_storage_url(
        session,
        download_info_url
    )

    if not storage_url:

        print()
        line()
        print(
            "STORAGE URL НЕ ПОЛУЧЕН"
        )
        line()

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    diagnose_storage(
        storage_url
    )

    print()
    line()
    print(
        "ДИАГНОСТИКА ЗАВЕРШЕНА"
    )
    line()

    print()
    input(
        "Нажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
