import requests
import re
import json
import html
import sys
from urllib.parse import urlparse


# ============================================================
# НАСТРОЙКИ
# ============================================================

API_SEARCH = "https://api.music.yandex.net/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


TIMEOUT = 20

DURATION_TOLERANCE = 3.0


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def normalize(text):
    """
    Нормализация текста для сравнения.
    """

    if text is None:
        return ""

    text = html.unescape(str(text))

    text = text.lower()

    text = text.replace("ё", "е")

    text = text.replace("–", "-")
    text = text.replace("—", "-")

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


def normalize_words(text):

    return {
        word
        for word in normalize(text).split()
        if word
    }


def format_duration(seconds):

    if seconds is None:
        return "??:??"

    try:
        seconds = int(round(float(seconds)))

    except Exception:
        return "??:??"

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )


def duration_difference(
    candidate,
    target
):

    if (
        candidate is None
        or target is None
    ):
        return None

    try:

        return abs(
            float(candidate) -
            float(target)
        )

    except Exception:

        return None


def make_cover_url(uri):

    if not uri:
        return None

    uri = str(uri)

    if uri.startswith("http://"):

        uri = uri.replace(
            "http://",
            "https://",
            1
        )

    elif not uri.startswith("https://"):

        uri = (
            "https://" +
            uri
        )

    uri = uri.replace(
        "%%",
        "m1000x1000"
    )

    return uri


def make_track_url(
    track_id,
    album_id=None
):

    if not track_id:
        return None

    if album_id:

        return (
            "https://music.yandex.ru/"
            f"album/{album_id}/"
            f"track/{track_id}"
        )

    return (
        "https://music.yandex.ru/"
        f"track/{track_id}"
    )


# ============================================================
# РАЗБОР ССЫЛКИ
# ============================================================

def parse_yandex_url(url):

    """
    Извлекает album_id и track_id
    из ссылок Яндекс Музыки.
    """

    try:

        parsed = urlparse(
            url
        )

        path = parsed.path

        match = re.search(
            r"/album/(\d+)/track/(\d+)",
            path
        )

        if match:

            return {
                "album_id":
                    int(match.group(1)),

                "track_id":
                    int(match.group(2))
            }

        match = re.search(
            r"/track/(\d+)",
            path
        )

        if match:

            return {
                "album_id":
                    None,

                "track_id":
                    int(match.group(1))
            }

    except Exception:
        pass

    return None


# ============================================================
# ИСПОЛНИТЕЛИ
# ============================================================

def get_artist_names(
    artists
):

    if not artists:
        return []

    result = []

    for artist in artists:

        if not isinstance(
            artist,
            dict
        ):
            continue

        name = artist.get(
            "name"
        )

        if name:
            result.append(
                str(name)
            )

    return result


def format_artists(
    artists
):

    names = get_artist_names(
        artists
    )

    return ", ".join(
        names
    )


# ============================================================
# ОЦЕНКА РЕЗУЛЬТАТА
# ============================================================

def score_candidate(
    candidate,
    wanted_artist,
    wanted_title,
    wanted_duration=None,
    wanted_track_id=None
):

    score = 0

    candidate_title = (
        candidate.get("title")
        or ""
    )

    candidate_artists = (
        candidate.get("artists")
        or []
    )

    candidate_artist = format_artists(
        candidate_artists
    )

    # --------------------------------------------------------
    # ID
    # --------------------------------------------------------

    candidate_id = candidate.get(
        "id"
    )

    if (
        wanted_track_id
        and candidate_id
        and str(candidate_id)
        == str(wanted_track_id)
    ):

        score += 1000

    # --------------------------------------------------------
    # НАЗВАНИЕ
    # --------------------------------------------------------

    wanted_title_norm = normalize(
        wanted_title
    )

    candidate_title_norm = normalize(
        candidate_title
    )

    if (
        wanted_title_norm
        and candidate_title_norm
    ):

        if (
            candidate_title_norm
            == wanted_title_norm
        ):

            score += 600

        elif (
            wanted_title_norm
            in candidate_title_norm
        ):

            score += 350

        else:

            wanted_words = (
                normalize_words(
                    wanted_title
                )
            )

            candidate_words = (
                normalize_words(
                    candidate_title
                )
            )

            if wanted_words:

                matches = (
                    wanted_words &
                    candidate_words
                )

                ratio = (
                    len(matches) /
                    len(wanted_words)
                )

                if ratio == 1:
                    score += 500

                elif ratio >= 0.75:
                    score += 300

                elif ratio >= 0.5:
                    score += 100

    # --------------------------------------------------------
    # ИСПОЛНИТЕЛЬ
    # --------------------------------------------------------

    wanted_artist_norm = normalize(
        wanted_artist
    )

    candidate_artist_norm = normalize(
        candidate_artist
    )

    if (
        wanted_artist_norm
        and candidate_artist_norm
    ):

        if (
            candidate_artist_norm
            == wanted_artist_norm
        ):

            score += 600

        elif (
            wanted_artist_norm
            in candidate_artist_norm
        ):

            score += 400

        else:

            wanted_words = (
                normalize_words(
                    wanted_artist
                )
            )

            candidate_words = (
                normalize_words(
                    candidate_artist
                )
            )

            if wanted_words:

                matches = (
                    wanted_words &
                    candidate_words
                )

                ratio = (
                    len(matches) /
                    len(wanted_words)
                )

                if ratio == 1:
                    score += 500

                elif ratio >= 0.75:
                    score += 300

                elif ratio >= 0.5:
                    score += 100

    # --------------------------------------------------------
    # ДЛИТЕЛЬНОСТЬ
    # --------------------------------------------------------

    candidate_duration = (
        candidate.get(
            "duration"
        )
    )

    difference = duration_difference(
        candidate_duration,
        wanted_duration
    )

    if difference is not None:

        if difference <= 1:
            score += 500

        elif difference <= 2:
            score += 350

        elif difference <= 3:
            score += 200

        elif difference <= 5:
            score += 50

        else:
            score -= 500

    return score


# ============================================================
# ПРЕОБРАЗОВАНИЕ ТРЕКА
# ============================================================

def parse_track(
    track
):

    if not isinstance(
        track,
        dict
    ):
        return None

    track_id = track.get(
        "id"
    )

    if not track_id:
        return None

    artists = track.get(
        "artists"
    ) or []

    albums = track.get(
        "albums"
    ) or []

    album = (
        albums[0]
        if albums
        and isinstance(
            albums[0],
            dict
        )
        else {}
    )

    album_id = album.get(
        "id"
    )

    album_title = album.get(
        "title"
    )

    duration_ms = track.get(
        "durationMs"
    )

    duration = None

    if duration_ms is not None:

        try:

            duration = (
                float(duration_ms) /
                1000
            )

        except Exception:
            pass

    cover_uri = (
        track.get(
            "coverUri"
        )
        or
        track.get(
            "ogImage"
        )
        or
        album.get(
            "coverUri"
        )
        or
        album.get(
            "ogImage"
        )
    )

    lyrics_info = (
        track.get(
            "lyricsInfo"
        )
        or {}
    )

    result = {

        "id":
            track_id,

        "real_id":
            track.get(
                "realId"
            ),

        "artist":
            format_artists(
                artists
            ),

        "artists":
            get_artist_names(
                artists
            ),

        "title":
            track.get(
                "title"
            ),

        "album":
            album_title or "",

        "album_id":
            album_id,

        "duration":
            duration,

        "duration_ms":
            duration_ms,

        "duration_formatted":
            format_duration(
                duration
            ),

        "cover_url":
            make_cover_url(
                cover_uri
            ),

        "genre":
            album.get(
                "genre"
            ),

        "year":
            album.get(
                "year"
            ),

        "release_date":
            album.get(
                "releaseDate"
            ),

        "available":
            track.get(
                "available"
            ),

        "available_for_premium":
            track.get(
                "availableForPremiumUsers"
            ),

        "available_full_without_permission":
            track.get(
                "availableFullWithoutPermission"
            ),

        "lyrics_available":
            track.get(
                "lyricsAvailable"
            ),

        "has_sync_lyrics":
            lyrics_info.get(
                "hasAvailableSyncLyrics"
            ),

        "has_text_lyrics":
            lyrics_info.get(
                "hasAvailableTextLyrics"
            ),

        "explicit":
            track.get(
                "explicit"
            ),

        "track_source":
            track.get(
                "trackSource"
            ),

        "track_url":
            make_track_url(
                track_id,
                album_id
            ),

        "cover_uri":
            cover_uri,

        "raw":
            track
    }

    return result


# ============================================================
# ПОИСК В ЯНДЕКС МУЗЫКЕ
# ============================================================

def search_yandex(
    artist,
    title,
    duration=None,
    track_id=None
):

    query = (
        f"{artist} {title}"
    ).strip()

    print()
    print("=" * 60)
    print(
        "ПОИСК В ЯНДЕКС МУЗЫКЕ"
    )
    print("=" * 60)

    print()
    print(
        "Запрос:",
        query
    )

    print()
    print(
        "API:",
        API_SEARCH
    )

    params = {
        "text":
            query,

        "page":
            0,

        "type":
            "track",

        "nococrrect":
            "true"
    }

    try:

        print()
        print(
            "Отправка запроса..."
        )

        response = requests.get(
            API_SEARCH,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        print(
            "HTTP-код:",
            response.status_code
        )

        print(
            "Размер ответа:",
            len(response.content),
            "байт"
        )

        if response.status_code != 200:

            print()
            print(
                "Яндекс Музыка "
                "вернула ошибку."
            )

            print(
                response.text[:1000]
            )

            return None

        data = response.json()

        result = data.get(
            "result"
        ) or {}

        tracks_container = (
            result.get(
                "tracks"
            )
            or {}
        )

        raw_tracks = (
            tracks_container.get(
                "results"
            )
            or []
        )

        print(
            "Найдено:",
            len(raw_tracks)
        )

        if not raw_tracks:

            print()
            print(
                "Подходящих результатов "
                "не найдено."
            )

            return None

        candidates = []

        for raw_track in raw_tracks:

            parsed = parse_track(
                raw_track
            )

            if not parsed:
                continue

            parsed["score"] = (
                score_candidate(
                    parsed,
                    artist,
                    title,
                    duration,
                    track_id
                )
            )

            candidates.append(
                parsed
            )

        if not candidates:

            return None

        candidates.sort(
            key=lambda x:
                x["score"],
            reverse=True
        )

        print()
        print("=" * 60)
        print(
            "КАНДИДАТЫ"
        )
        print("=" * 60)

        for index, candidate in enumerate(
            candidates[:10],
            1
        ):

            print()
            print(
                f"{index}. "
                f"{candidate['artist']} "
                f"— "
                f"{candidate['title']}"
            )

            print(
                "   Длительность:",
                candidate[
                    "duration_formatted"
                ]
            )

            print(
                "   Оценка:",
                candidate[
                    "score"
                ]
            )

            print(
                "   ID:",
                candidate[
                    "id"
                ]
            )

        best = candidates[0]

        print()
        print("=" * 60)
        print(
            "ЛУЧШЕЕ СОВПАДЕНИЕ"
        )
        print("=" * 60)

        print()
        print(
            "Исполнитель:",
            best["artist"]
        )

        print(
            "Название:   ",
            best["title"]
        )

        print(
            "Альбом:     ",
            best["album"]
        )

        print(
            "Длительность:",
            best[
                "duration_formatted"
            ]
        )

        print(
            "ID трека:   ",
            best["id"]
        )

        print(
            "ID альбома: ",
            best["album_id"]
        )

        print(
            "Оценка:     ",
            best["score"]
        )

        if duration is not None:

            difference = (
                duration_difference(
                    best["duration"],
                    duration
                )
            )

            if difference is not None:

                print(
                    "Разница длительности:",
                    f"{difference:.1f} сек."
                )

        print(
            "Обложка:    ",
            "НАЙДЕНА"
            if best["cover_url"]
            else "НЕТ"
        )

        if best["cover_url"]:

            print()
            print(
                "URL обложки:"
            )

            print(
                best["cover_url"]
            )

        print()
        print(
            "URL трека:"
        )

        print(
            best["track_url"]
        )

        return best

    except requests.RequestException as e:

        print()
        print(
            "Ошибка HTTP:"
        )

        print(
            e
        )

        return None

    except json.JSONDecodeError:

        print()
        print(
            "Ошибка: Яндекс вернул "
            "невалидный JSON."
        )

        return None

    except Exception as e:

        print()
        print(
            "Ошибка:"
        )

        print(
            e
        )

        return None


# ============================================================
# ПОЛУЧЕНИЕ ТРЕКА ПО ID
# ============================================================

def get_track_by_id(
    track_id
):

    """
    Отдельная функция для будущего использования
    из downloader.py.

    Сейчас поиск использует API /search.
    Эта функция оставлена как дополнительный
    интерфейс для дальнейшей интеграции.
    """

    url = (
        "https://api.music.yandex.net/"
        f"tracks/{track_id}"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return None

        data = response.json()

        result = data.get(
            "result"
        )

        if isinstance(
            result,
            list
        ):

            if not result:
                return None

            return parse_track(
                result[0]
            )

        if isinstance(
            result,
            dict
        ):

            return parse_track(
                result
            )

    except Exception:
        pass

    return None


# ============================================================
# АНАЛИЗ ССЫЛКИ
# ============================================================

def process_yandex_url(
    url
):

    print()
    print("=" * 60)
    print(
        "АНАЛИЗ ССЫЛКИ ЯНДЕКС МУЗЫКИ"
    )
    print("=" * 60)

    parsed = parse_yandex_url(
        url
    )

    if not parsed:

        print()
        print(
            "Не удалось определить "
            "ID трека из ссылки."
        )

        print()
        print(
            "Поддерживаемый формат:"
        )

        print(
            "https://music.yandex.ru/"
            "album/АЛЬБОМ/track/ТРЕК"
        )

        return None

    album_id = parsed.get(
        "album_id"
    )

    track_id = parsed.get(
        "track_id"
    )

    print()
    print(
        "ID трека:",
        track_id
    )

    print(
        "ID альбома:",
        album_id
    )

    print()

    # --------------------------------------------------------
    # Сначала пробуем получить данные страницы.
    #
    # Для текущей версии это диагностический этап.
    # Основной поиск будет через API.
    # --------------------------------------------------------

    print(
        "Получение данных через API поиска..."
    )

    # --------------------------------------------------------
    # Нам неизвестны artist/title только из URL.
    #
    # Поэтому используем API track endpoint.
    # --------------------------------------------------------

    direct_track = get_track_by_id(
        track_id
    )

    if direct_track:

        print()
        print(
            "Данные трека получены напрямую."
        )

        artist = direct_track.get(
            "artist"
        ) or ""

        title = direct_track.get(
            "title"
        ) or ""

        duration = direct_track.get(
            "duration"
        )

        # Повторно прогоняем через поиск.
        #
        # Это позволяет получить одинаковую
        # структуру и проверить качество совпадения.
        return search_yandex(
            artist,
            title,
            duration,
            track_id
        )

    # --------------------------------------------------------
    # Если прямой endpoint не сработал,
    # пытаемся использовать HTML страницы.
    # --------------------------------------------------------

    print()
    print(
        "Прямое получение данных не удалось."
    )

    print(
        "Пытаемся получить страницу..."
    )

    try:

        response = requests.get(
            url,
            headers={
                **HEADERS,
                "Accept":
                    "text/html,"
                    "application/xhtml+xml"
            },
            timeout=TIMEOUT
        )

        if response.status_code != 200:

            print(
                "HTTP-код:",
                response.status_code
            )

            return None

        text = response.text

        print(
            "HTTP-код:",
            response.status_code
        )

        print(
            "Размер HTML:",
            len(response.content),
            "байт"
        )

        # ----------------------------------------------------
        # OG TITLE
        # ----------------------------------------------------

        title_match = re.search(
            r'<meta[^>]+'
            r'property=["\']og:title["\']'
            r'[^>]+content=["\']'
            r'([^"\']+)'
            r'["\']',
            text,
            re.I
        )

        title = (
            html.unescape(
                title_match.group(1)
            )
            if title_match
            else ""
        )

        # ----------------------------------------------------
        # OG DESCRIPTION
        # ----------------------------------------------------

        description_match = re.search(
            r'<meta[^>]+'
            r'property=["\']og:description["\']'
            r'[^>]+content=["\']'
            r'([^"\']+)'
            r'["\']',
            text,
            re.I
        )

        description = (
            html.unescape(
                description_match.group(1)
            )
            if description_match
            else ""
        )

        # ----------------------------------------------------
        # Пытаемся определить исполнителя
        # из og:description.
        #
        # Формат обычно:
        # Artist • Трек • 2022
        # ----------------------------------------------------

        artist = ""

        if description:

            parts = [
                part.strip()
                for part
                in description.split("•")
            ]

            if parts:

                artist = parts[0]

        if not title:

            print(
                "Не удалось определить "
                "название трека."
            )

            return None

        print()
        print(
            "Найдено:"
        )

        print(
            "Исполнитель:",
            artist
        )

        print(
            "Название:",
            title
        )

        print()

        return search_yandex(
            artist,
            title,
            None,
            track_id
        )

    except Exception as e:

        print(
            "Ошибка получения страницы:",
            e
        )

        return None


# ============================================================
# ФОРМАТ ДЛЯ БУДУЩЕЙ ИНТЕГРАЦИИ
# ============================================================

def get_yandex_info(
    url
):

    """
    Основная функция, которую позже будет
    вызывать downloader.py.

    Возвращает словарь:

    {
        artist,
        artists,
        title,
        album,
        album_id,
        duration,
        duration_ms,
        duration_formatted,
        cover_url,
        genre,
        year,
        release_date,
        available,
        lyrics_available,
        has_sync_lyrics,
        has_text_lyrics,
        track_url,
        id
    }

    либо None.
    """

    return process_yandex_url(
        url
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "YANDEX MUSIC INFO TEST"
    )
    print("=" * 60)

    print()
    print(
        "Этот тест НЕ скачивает аудио."
    )

    print(
        "Он только получает информацию "
        "из Яндекс Музыки."
    )

    print()

    if len(sys.argv) > 1:

        url = sys.argv[1]

    else:

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

    result = get_yandex_info(
        url
    )

    print()

    if not result:

        print("=" * 60)
        print(
            "ТЕСТ НЕ ПРОЙДЕН"
        )
        print("=" * 60)

        print()
        print(
            "Не удалось получить "
            "информацию о треке."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    print()
    print("=" * 60)
    print(
        "ПОЛНАЯ ИНФОРМАЦИЯ"
    )
    print("=" * 60)

    print()

    print(
        "Исполнитель:",
        result["artist"]
    )

    print(
        "Название:",
        result["title"]
    )

    print(
        "Альбом:",
        result["album"]
    )

    print(
        "ID трека:",
        result["id"]
    )

    print(
        "ID альбома:",
        result["album_id"]
    )

    print(
        "Длительность:",
        result["duration_formatted"]
    )

    print(
        "Жанр:",
        result["genre"]
    )

    print(
        "Год:",
        result["year"]
    )

    print(
        "Доступен:",
        "ДА"
        if result["available"]
        else "НЕТ"
    )

    print(
        "Обложка:",
        "НАЙДЕНА"
        if result["cover_url"]
        else "НЕТ"
    )

    print(
        "Синхронизированный текст:",
        "ДА"
        if result["has_sync_lyrics"]
        else "НЕТ"
    )

    print(
        "Обычный текст:",
        "ДА"
        if result["has_text_lyrics"]
        else "НЕТ"
    )

    print(
        "Explicit:",
        "ДА"
        if result["explicit"]
        else "НЕТ"
    )

    print()

    if result["cover_url"]:

        print(
            "URL обложки:"
        )

        print(
            result["cover_url"]
        )

        print()

    print(
        "URL трека:"
    )

    print(
        result["track_url"]
    )

    print()

    print("=" * 60)
    print(
        "ТЕСТ ПРОЙДЕН"
    )
    print("=" * 60)

    print()
    print(
        "Яндекс Музыка успешно определена "
        "как источник метаданных."
    )

    print()
    print(
        "Аудиофайл НЕ скачивался."
    )

    input(
        "\nНажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
