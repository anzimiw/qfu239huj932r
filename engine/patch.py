import os
import re
import json
import shutil
from datetime import datetime


DOWNLOADER = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "downloader.py"
)


def extract_balanced_json_object(
    text,
    start
):
    """
    Извлекает JSON-объект, начиная с позиции
    '{', учитывая вложенность и строки.
    """

    if start < 0 or start >= len(text):
        return None

    if text[start] != "{":
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start,
        len(text)
    ):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False

            elif char == "\\":
                escaped = True

            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[
                    start:index + 1
                ]

    return None


def extract_yandex_state_objects(
    text
):
    """
    Извлекает объекты value из:

    window.__STATE_PATCHES__

    Нас интересуют:
      /playlist/meta
      /playlist/items/N/data
    """

    objects = []

    path_marker = (
        '"path":"\\u002Fplaylist\\u002F'
    )

    position = 0

    while True:
        position = text.find(
            path_marker,
            position
        )

        if position < 0:
            break

        value_position = text.find(
            '"value":',
            position
        )

        if value_position < 0:
            position += len(path_marker)
            continue

        start = text.find(
            "{",
            value_position + len('"value":')
        )

        if start < 0:
            position += len(path_marker)
            continue

        candidate = (
            extract_balanced_json_object(
                text,
                start
            )
        )

        if candidate:
            try:
                data = json.loads(
                    candidate
                )

                objects.append(
                    data
                )

            except Exception:
                pass

        position = (
            start + 1
        )

    return objects


def extract_yandex_playlist_state(
    text
):
    """
    Возвращает:

    {
        "title": "...",
        "tracks": [
            {...},
            {...}
        ]
    }

    где tracks — полноценные объекты
    Яндекс Музыки.
    """

    playlist_title = ""
    tracks = []

    # --------------------------------------------------------
    # PLAYLIST META
    # --------------------------------------------------------

    meta_path = (
        '"path":"\\u002Fplaylist\\u002Fmeta"'
    )

    meta_position = text.find(
        meta_path
    )

    if meta_position >= 0:
        value_position = text.find(
            '"value":',
            meta_position
        )

        if value_position >= 0:
            start = text.find(
                "{",
                value_position + len('"value":')
            )

            if start >= 0:
                candidate = (
                    extract_balanced_json_object(
                        text,
                        start
                    )
                )

                if candidate:
                    try:
                        meta = json.loads(
                            candidate
                        )

                        playlist_title = (
                            meta.get("title")
                            or ""
                        )

                    except Exception:
                        pass

    # --------------------------------------------------------
    # TRACK DATA
    # --------------------------------------------------------

    item_pattern = re.compile(
        r'"path":"\\u002Fplaylist\\u002Fitems\\u002F'
        r'(\d+)\\u002Fdata"'
    )

    for match in item_pattern.finditer(
        text
    ):
        index = int(
            match.group(1)
        )

        value_position = text.find(
            '"value":',
            match.end()
        )

        if value_position < 0:
            continue

        start = text.find(
            "{",
            value_position + len('"value":')
        )

        if start < 0:
            continue

        candidate = (
            extract_balanced_json_object(
                text,
                start
            )
        )

        if not candidate:
            continue

        try:
            data = json.loads(
                candidate
            )
        except Exception:
            continue

        if not isinstance(
            data,
            dict
        ):
            continue

        track_id = (
            data.get("id")
            or data.get("realId")
        )

        if not track_id:
            continue

        tracks.append(
            (
                index,
                data
            )
        )

    # Сохраняем порядок плейлиста.
    tracks.sort(
        key=lambda item: item[0]
    )

    # Убираем возможные дубли.
    unique_tracks = []
    seen = set()

    for _, track in tracks:
        track_id = str(
            track.get("id")
            or track.get("realId")
        )

        if track_id in seen:
            continue

        seen.add(
            track_id
        )

        unique_tracks.append(
            track
        )

    return {
        "title": (
            playlist_title
            or "Яндекс Музыка"
        ),
        "tracks": unique_tracks
    }


def yandex_cover_url(
    cover_uri
):
    if not cover_uri:
        return None

    cover_url = str(
        cover_uri
    ).replace(
        "%%",
        "720x720"
    )

    if cover_url.startswith(
        "//"
    ):
        return (
            "https:"
            + cover_url
        )

    if not cover_url.startswith(
        (
            "http://",
            "https://"
        )
    ):
        return (
            "https://"
            + cover_url
        )

    return cover_url


def yandex_track_to_info(
    track
):
    """
    Преобразует объект track из
    __STATE_PATCHES__ в формат,
    который уже использует downloader.py.
    """

    if not isinstance(
        track,
        dict
    ):
        return None

    artists = (
        track.get("artists")
        or []
    )

    artist_names = []

    for item in artists:
        if not isinstance(
            item,
            dict
        ):
            continue

        name = item.get(
            "name"
        )

        if name:
            artist_names.append(
                str(name)
            )

    artist = ", ".join(
        artist_names
    )

    title = (
        track.get("title")
        or ""
    )

    album = ""

    albums = (
        track.get("albums")
        or []
    )

    if isinstance(
        albums,
        list
    ):
        for item in albums:
            if not isinstance(
                item,
                dict
            ):
                continue

            album = (
                item.get("title")
                or ""
            )

            if album:
                break

    # В некоторых структурах
    # альбом может отсутствовать.
    if not album:
        album = (
            track.get("albumTitle")
            or ""
        )

    duration = None

    duration_ms = (
        track.get("durationMs")
    )

    if duration_ms is not None:
        try:
            duration = (
                float(duration_ms)
                / 1000.0
            )
        except Exception:
            duration = None

    cover_uri = (
        track.get("coverUri")
        or track.get("ogImage")
    )

    cover_url = yandex_cover_url(
        cover_uri
    )

    track_id = str(
        track.get("id")
        or track.get("realId")
        or ""
    )

    album_id = ""

    if track.get(
        "albumId"
    ) is not None:
        album_id = str(
            track.get("albumId")
        )

    if not album_id:
        if isinstance(
            albums,
            list
        ):
            for item in albums:
                if not isinstance(
                    item,
                    dict
                ):
                    continue

                if item.get("id") is not None:
                    album_id = str(
                        item.get("id")
                    )
                    break

    if (
        not artist
        or not title
        or duration is None
    ):
        return None

    return {
        "source": "yandex",
        "artist": artist,
        "title": title,
        "album": album,
        "duration": duration,
        "cover_url": cover_url,
        "track_id": track_id,
        "album_id": album_id,
        "has_lyrics": bool(
            track.get(
                "hasLyrics",
                False
            )
        ),
        "has_sync_lyrics": bool(
            track.get(
                "hasSyncLyrics",
                False
            )
        )
    }


NEW_GET_YANDEX_MUSIC_INFO = r'''
def get_yandex_music_info(url):
    status(
        "Получение информации из Яндекс Музыки..."
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )
    except requests.RequestException as e:
        print(
            "Не удалось получить страницу "
            "Яндекс Музыки."
        )
        print(
            f"Ошибка: {e}"
        )
        return None

    if response.status_code != 200:
        print(
            "Яндекс Музыка вернула HTTP "
            f"{response.status_code}."
        )
        return None

    text = response.text

    state = extract_yandex_playlist_state(
        text
    )

    tracks = state.get(
        "tracks",
        []
    )

    if not tracks:
        print(
            "В HTML Яндекс Музыки "
            "не найдены данные трека."
        )
        return None

    # Для обычной ссылки на трек
    # определяем ID из URL.
    parsed = parse_yandex_url(
        url
    )

    target_track_id = ""

    if parsed:
        target_track_id = str(
            parsed.get(
                "track_id"
            )
            or ""
        )

    selected_track = None

    if target_track_id:
        for track in tracks:
            current_id = str(
                track.get("id")
                or track.get("realId")
                or ""
            )

            if current_id == target_track_id:
                selected_track = track
                break

    # Если ID из URL не найден,
    # но HTML содержит ровно один трек,
    # используем его.
    if selected_track is None and len(tracks) == 1:
        selected_track = tracks[0]

    if selected_track is None:
        print(
            "Не удалось определить "
            "нужный трек Яндекс Музыки."
        )
        return None

    info = yandex_track_to_info(
        selected_track
    )

    if not info:
        print(
            "Не удалось определить "
            "метаданные трека Яндекс Музыки."
        )
        return None

    print(
        f"Исполнитель: {info['artist']}"
    )

    print(
        f"Название: {info['title']}"
    )

    print(
        f"Альбом: "
        f"{info['album'] or 'не определён'}"
    )

    print(
        f"Длительность: "
        f"{format_duration(info['duration'])}"
    )

    print(
        "Обложка: "
        f"{'НАЙДЕНА' if info['cover_url'] else 'НЕ НАЙДЕНА'}"
    )

    print(
        "Синхронизированный текст Яндекс: "
        f"{'ДА' if info.get('has_sync_lyrics') else 'НЕТ'}"
    )

    return info
'''


NEW_GET_PLAYLIST_TRACKS = r'''
def get_playlist_tracks(url):
    status(
        "Получение списка треков плейлиста..."
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )
    except requests.RequestException as e:
        print(
            "Не удалось получить "
            "страницу плейлиста Яндекс Музыки."
        )
        print(
            f"Ошибка: {e}"
        )
        return None

    if response.status_code != 200:
        print(
            "Яндекс Музыка вернула HTTP "
            f"{response.status_code}."
        )
        return None

    state = extract_yandex_playlist_state(
        response.text
    )

    title = (
        state.get("title")
        or "Яндекс Музыка"
    )

    yandex_tracks = (
        state.get("tracks")
        or []
    )

    if not yandex_tracks:
        print(
            "Треки Яндекс-плейлиста "
            "в HTML не найдены."
        )
        return None

    tracks = []

    for track in yandex_tracks:
        track_id = (
            track.get("id")
            or track.get("realId")
        )

        if not track_id:
            continue

        tracks.append(
            "https://music.yandex.ru/album/"
            + str(
                track.get("albumId")
                or ""
            )
            + "/track/"
            + str(track_id)
        )

    if not tracks:
        print(
            "Не удалось сформировать "
            "ссылки на треки Яндекс-плейлиста."
        )
        return None

    print(
        f"Название плейлиста: {title}"
    )

    print(
        f"Найдено треков: {len(tracks)}"
    )

    return {
        "title": title,
        "tracks": tracks
    }
'''


NEW_IS_PLAYLIST_URL = r'''
def is_playlist_url(url):
    if not url:
        return False

    lowered = url.lower()

    if (
        "music.yandex.ru/playlists/"
        in lowered
        or
        "music.yandex.com/playlists/"
        in lowered
        or
        "music.yandex.kz/playlists/"
        in lowered
        or
        "music.yandex.by/playlists/"
        in lowered
        or
        "music.yandex.uz/playlists/"
        in lowered
    ):
        return True

    return (
        "list=" in lowered
        and (
            "youtube.com" in lowered
            or "music.youtube.com" in lowered
        )
    )
'''


def replace_function(
    source,
    function_name,
    new_function
):
    pattern = re.compile(
        r"(?ms)^def "
        + re.escape(function_name)
        + r"\(.*?(?=^def |\Z)"
    )

    match = pattern.search(
        source
    )

    if not match:
        raise RuntimeError(
            f"Функция {function_name} "
            "не найдена."
        )

    return (
        source[:match.start()]
        + new_function.strip()
        + "\n\n"
        + source[match.end():]
    )


def main():
    print(
        "=" * 70
    )
    print(
        "CENSURU.NET — ПАТЧ ЯНДЕКС МУЗЫКИ"
    )
    print(
        "=" * 70
    )

    if not os.path.isfile(
        DOWNLOADER
    ):
        print()
        print(
            "ОШИБКА: downloader.py "
            "не найден:"
        )
        print(
            DOWNLOADER
        )
        return

    with open(
        DOWNLOADER,
        "r",
        encoding="utf-8"
    ) as f:
        source = f.read()

    print()
    print(
        "Проверка функций..."
    )

    required = (
        "get_yandex_music_info",
        "get_playlist_tracks",
        "is_playlist_url"
    )

    for name in required:
        if not re.search(
            r"(?m)^def "
            + re.escape(name)
            + r"\(",
            source
        ):
            print(
                f"  ОШИБКА: {name} "
                "не найдена."
            )
            return

        print(
            f"  OK: {name}"
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = (
        DOWNLOADER
        + ".backup_yandex_"
        + timestamp
    )

    shutil.copy2(
        DOWNLOADER,
        backup
    )

    print()
    print(
        "Резервная копия создана:"
    )
    print(
        backup
    )

    try:
        print()
        print(
            "Замена get_yandex_music_info()..."
        )

        source = replace_function(
            source,
            "get_yandex_music_info",
            NEW_GET_YANDEX_MUSIC_INFO
        )

        print(
            "OK"
        )

        print()
        print(
            "Замена get_playlist_tracks()..."
        )

        source = replace_function(
            source,
            "get_playlist_tracks",
            NEW_GET_PLAYLIST_TRACKS
        )

        print(
            "OK"
        )

        print()
        print(
            "Замена is_playlist_url()..."
        )

        source = replace_function(
            source,
            "is_playlist_url",
            NEW_IS_PLAYLIST_URL
        )

        print(
            "OK"
        )

    except Exception as e:
        print()
        print(
            "ОШИБКА ПАТЧА:"
        )
        print(
            e
        )

        shutil.copy2(
            backup,
            DOWNLOADER
        )

        print()
        print(
            "Исходный downloader.py "
            "восстановлен из резервной копии."
        )

        return

    # Проверка синтаксиса до записи.
    print()
    print(
        "Проверка синтаксиса..."
    )

    try:
        compile(
            source,
            DOWNLOADER,
            "exec"
        )
    except SyntaxError as e:
        print(
            "ОШИБКА СИНТАКСИСА:"
        )
        print(
            e
        )

        shutil.copy2(
            backup,
            DOWNLOADER
        )

        print()
        print(
            "Исходный downloader.py "
            "восстановлен."
        )

        return

    with open(
        DOWNLOADER,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:
        f.write(
            source
        )

    print()
    print(
        "=" * 70
    )
    print(
        "ПАТЧ УСПЕШНО ПРИМЕНЁН"
    )
    print(
        "=" * 70
    )

    print()
    print(
        "Изменено:"
    )
    print(
        "  - get_yandex_music_info()"
    )
    print(
        "  - get_playlist_tracks()"
    )
    print(
        "  - is_playlist_url()"
    )

    print()
    print(
        "SoundCloud / MP3Party / MP3TM / "
        "AudioStart не изменялись."
    )

    print()
    print(
        "Резервная копия:"
    )
    print(
        backup
    )


if __name__ == "__main__":
    main()
