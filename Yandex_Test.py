import requests
import re
import sys
import html
from urllib.parse import quote


# ============================================================
# НАСТРОЙКИ
# ============================================================

API_URL = "https://api.music.yandex.net/search"

TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),

    "Accept": "application/json, text/plain, */*",

    "Accept-Language":
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",

    "Referer":
        "https://music.yandex.ru/"
}


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def normalize(text):

    if text is None:
        return ""

    text = html.unescape(
        str(text)
    )

    text = text.lower()

    # Нормализация похожих символов
    text = text.replace("ё", "е")

    text = text.replace("–", "-")
    text = text.replace("—", "-")

    # featuring / feat / ft
    text = re.sub(
        r"\bfeaturing\b",
        "feat",
        text
    )

    text = re.sub(
        r"\bft\.?\b",
        "feat",
        text
    )

    # Убираем feat из сравнения.
    # Самих исполнителей при этом не удаляем.
    text = re.sub(
        r"\bfeat\.?\b",
        " ",
        text
    )

    # Всё лишнее превращаем в пробел
    text = re.sub(
        r"[^a-zа-я0-9]+",
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

    value = normalize(text)

    if not value:
        return set()

    return set(
        value.split()
    )


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


def get_artists(track):

    artists = track.get(
        "artists"
    )

    if not isinstance(
        artists,
        list
    ):

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


def get_artist_string(track):

    artists = get_artists(
        track
    )

    return ", ".join(
        artists
    )


def get_album(track):

    albums = track.get(
        "albums"
    )

    if not isinstance(
        albums,
        list
    ):
        return ""

    if not albums:
        return ""

    album = albums[0]

    if not isinstance(
        album,
        dict
    ):
        return ""

    return (
        album.get("title")
        or ""
    )


def get_cover_url(track):

    cover_uri = (
        track.get(
            "coverUri"
        )
        or
        track.get(
            "ogImage"
        )
    )

    if not cover_uri:
        return None

    cover_uri = str(
        cover_uri
    )

    # API возвращает:
    #
    # avatars.yandex.net/.../%%
    #
    # Для обычной картинки заменяем %%.
    cover_uri = cover_uri.replace(
        "%%",
        "m1000x1000"
    )

    if cover_uri.startswith(
        "//"
    ):

        return (
            "https:"
            + cover_uri
        )

    if cover_uri.startswith(
        "http://"
    ) or cover_uri.startswith(
        "https://"
    ):

        return cover_uri

    return (
        "https://"
        + cover_uri
    )


def get_track_url(track):

    track_id = track.get(
        "id"
    )

    if not track_id:
        return None

    return (
        "https://music.yandex.ru/"
        f"album/"
        f"{get_album_id(track)}/"
        f"track/"
        f"{track_id}"
    )


def get_album_id(track):

    albums = track.get(
        "albums"
    )

    if not isinstance(
        albums,
        list
    ):
        return ""

    if not albums:
        return ""

    album = albums[0]

    if not isinstance(
        album,
        dict
    ):
        return ""

    return str(
        album.get(
            "id",
            ""
        )
    )


# ============================================================
# ОЦЕНКА СОВПАДЕНИЯ
# ============================================================

def text_score(
    found_artist,
    found_title,
    wanted_artist,
    wanted_title
):

    wanted_artist_norm = normalize(
        wanted_artist
    )

    wanted_title_norm = normalize(
        wanted_title
    )

    found_artist_norm = normalize(
        found_artist
    )

    found_title_norm = normalize(
        found_title
    )

    if not wanted_artist_norm:
        return 0

    if not wanted_title_norm:
        return 0

    score = 0

    # --------------------------------------------------------
    # НАЗВАНИЕ
    # --------------------------------------------------------

    if (
        found_title_norm
        ==
        wanted_title_norm
    ):

        score += 600

    elif (
        wanted_title_norm
        in
        found_title_norm
    ):

        score += 400

    else:

        wanted_words = normalize_words(
            wanted_title
        )

        found_words = normalize_words(
            found_title
        )

        if wanted_words:

            ratio = (
                len(
                    wanted_words
                    &
                    found_words
                )
                /
                len(wanted_words)
            )

            if ratio >= 1:
                score += 500

            elif ratio >= 0.75:
                score += 300

            elif ratio >= 0.5:
                score += 150

    # --------------------------------------------------------
    # ИСПОЛНИТЕЛЬ
    # --------------------------------------------------------

    if (
        found_artist_norm
        ==
        wanted_artist_norm
    ):

        score += 600

    elif (
        wanted_artist_norm
        in
        found_artist_norm
    ):

        score += 450

    else:

        wanted_words = normalize_words(
            wanted_artist
        )

        found_words = normalize_words(
            found_artist
        )

        if wanted_words:

            ratio = (
                len(
                    wanted_words
                    &
                    found_words
                )
                /
                len(wanted_words)
            )

            if ratio >= 1:
                score += 500

            elif ratio >= 0.75:
                score += 300

            elif ratio >= 0.5:
                score += 150

    return score


def duration_score(
    found_duration,
    wanted_duration
):

    if (
        found_duration is None
        or
        wanted_duration is None
    ):

        return 0

    difference = abs(
        float(found_duration)
        -
        float(wanted_duration)
    )

    if difference <= 1:
        return 500

    if difference <= 2:
        return 350

    if difference <= 3:
        return 200

    if difference <= 5:
        return 50

    return -500


# ============================================================
# API ЯНДЕКСА
# ============================================================

def search_yandex(
    artist,
    title,
    duration=None
):

    query = (
        f"{artist} {title}"
    )

    print()
    print("=" * 60)
    print(
        "ПОИСК В ЯНДЕКС МУЗЫКЕ"
    )
    print("=" * 60)

    print()
    print(
        "Исполнитель:",
        artist
    )

    print(
        "Название:   ",
        title
    )

    if duration is not None:

        print(
            "Длительность:",
            format_duration(
                duration
            )
        )

    print()
    print(
        "Поисковый запрос:"
    )

    print(
        query
    )

    print()
    print(
        "API:"
    )

    print(
        API_URL
    )

    params = {
        "text": query,
        "page": 0,
        "type": "track",
        "nococrrect": "true"
    }

    try:

        print()
        print(
            "Отправка запроса..."
        )

        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        )

    except requests.RequestException as e:

        print()
        print(
            "ОШИБКА соединения:"
        )

        print(
            e
        )

        return None

    print()
    print(
        "HTTP-код:",
        response.status_code
    )

    print(
        "Размер ответа:",
        len(
            response.content
        ),
        "байт"
    )

    if response.status_code != 200:

        print()
        print(
            "Яндекс Музыка вернула "
            "ошибку HTTP."
        )

        print(
            response.text[:2000]
        )

        return None

    try:

        data = response.json()

    except Exception as e:

        print()
        print(
            "ОШИБКА JSON:"
        )

        print(
            e
        )

        return None

    result = data.get(
        "result"
    )

    if not isinstance(
        result,
        dict
    ):

        print()
        print(
            "В ответе отсутствует "
            "корректный result."
        )

        return None

    tracks = result.get(
        "tracks"
    )

    if not isinstance(
        tracks,
        dict
    ):

        print()
        print(
            "В result отсутствует "
            "блок tracks."
        )

        return None

    results = tracks.get(
        "results"
    )

    if not isinstance(
        results,
        list
    ):

        print()
        print(
            "Поле tracks.results "
            "не найдено."
        )

        return None

    print()
    print(
        "Найдено результатов:",
        len(results)
    )

    if not results:

        print()
        print(
            "Подходящих треков "
            "не найдено."
        )

        return None

    # ========================================================
    # АНАЛИЗ РЕЗУЛЬТАТОВ
    # ========================================================

    candidates = []

    for index, track in enumerate(
        results,
        1
    ):

        if not isinstance(
            track,
            dict
        ):
            continue

        found_title = (
            track.get(
                "title"
            )
            or ""
        )

        found_artist = get_artist_string(
            track
        )

        duration_ms = track.get(
            "durationMs"
        )

        found_duration = None

        if duration_ms is not None:

            try:

                found_duration = (
                    float(
                        duration_ms
                    )
                    /
                    1000
                )

            except Exception:

                found_duration = None

        score = text_score(
            found_artist,
            found_title,
            artist,
            title
        )

        score += duration_score(
            found_duration,
            duration
        )

        candidates.append({
            "track": track,
            "score": score,
            "artist": found_artist,
            "title": found_title,
            "duration": found_duration
        })

    if not candidates:

        print()
        print(
            "Корректных треков "
            "в ответе не найдено."
        )

        return None

    candidates.sort(
        key=lambda item:
            item["score"],
        reverse=True
    )

    # ========================================================
    # ВЫВОД КАНДИДАТОВ
    # ========================================================

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
            f"{candidate['artist']} — "
            f"{candidate['title']}"
        )

        print(
            "   Длительность:",
            format_duration(
                candidate["duration"]
            )
        )

        print(
            "   Оценка:",
            candidate["score"]
        )

        track = candidate[
            "track"
        ]

        print(
            "   ID:",
            track.get(
                "id"
            )
        )

    best = candidates[0]

    track = best[
        "track"
    ]

    # ========================================================
    # ПРОВЕРКА КАЧЕСТВА СОВПАДЕНИЯ
    # ========================================================

    if best["score"] < 500:

        print()
        print(
            "Лучший результат имеет "
            "слишком низкую степень "
            "совпадения."
        )

        return None

    found_artist = best[
        "artist"
    ]

    found_title = best[
        "title"
    ]

    found_duration = best[
        "duration"
    ]

    album = get_album(
        track
    )

    cover_url = get_cover_url(
        track
    )

    track_id = track.get(
        "id"
    )

    album_id = get_album_id(
        track
    )

    track_url = get_track_url(
        track
    )

    print()
    print("=" * 60)
    print(
        "ЛУЧШЕЕ СОВПАДЕНИЕ"
    )
    print("=" * 60)

    print()
    print(
        "Исполнитель:",
        found_artist
    )

    print(
        "Название:   ",
        found_title
    )

    print(
        "Альбом:     ",
        album or "не определён"
    )

    print(
        "Длительность:",
        format_duration(
            found_duration
        )
    )

    print(
        "ID трека:   ",
        track_id
    )

    print(
        "ID альбома: ",
        album_id or "не определён"
    )

    print(
        "Обложка:    ",
        "НАЙДЕНА"
        if cover_url
        else "НЕ НАЙДЕНА"
    )

    if cover_url:

        print()
        print(
            "URL обложки:"
        )

        print(
            cover_url
        )

    if track_url:

        print()
        print(
            "URL трека:"
        )

        print(
            track_url
        )

    print()
    print(
        "Оценка совпадения:",
        best["score"]
    )

    return {
        "id":
            track_id,

        "real_id":
            track.get(
                "realId"
            ),

        "artist":
            found_artist,

        "title":
            found_title,

        "album":
            album,

        "duration":
            found_duration,

        "duration_ms":
            track.get(
                "durationMs"
            ),

        "album_id":
            album_id,

        "cover_url":
            cover_url,

        "track_url":
            track_url,

        "available":
            track.get(
                "available",
                False
            ),

        "available_for_premium":
            track.get(
                "availableForPremiumUsers",
                False
            ),

        "available_full_without_permission":
            track.get(
                "availableFullWithoutPermission",
                False
            ),

        "lyrics_info":
            track.get(
                "lyricsInfo"
            ),

        "raw":
            track
    }


# ============================================================
# ТЕСТ
# ============================================================

def main():

    print("=" * 60)
    print(
        "YANDEX MUSIC API TEST"
    )
    print("=" * 60)

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

        except ValueError:

            print()
            print(
                "Некорректная длительность."
            )

            input(
                "\nНажмите Enter для выхода..."
            )

            return

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

    result = search_yandex(
        artist,
        title,
        duration
    )

    print()
    print("=" * 60)

    if result:

        print(
            "ТЕСТ ПОИСКА ПРОЙДЕН"
        )

        print("=" * 60)

        print()
        print(
            "Яндекс Музыка вернула "
            "подходящий трек."
        )

        print()
        print(
            "ID:",
            result["id"]
        )

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
            "Длительность:",
            format_duration(
                result["duration"]
            )
        )

        print()
        print(
            "Доступен:",
            "ДА"
            if result["available"]
            else "НЕТ"
        )

        lyrics_info = result.get(
            "lyrics_info"
        )

        if isinstance(
            lyrics_info,
            dict
        ):

            print()
            print(
                "Синхронизированный текст:",
                "ДА"
                if lyrics_info.get(
                    "hasAvailableSyncLyrics"
                )
                else "НЕТ"
            )

            print(
                "Обычный текст:",
                "ДА"
                if lyrics_info.get(
                    "hasAvailableTextLyrics"
                )
                else "НЕТ"
            )

    else:

        print(
            "ТЕСТ ПОИСКА НЕ ПРОЙДЕН"
        )

        print("=" * 60)

    print()

    input(
        "Нажмите Enter для выхода..."
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()
