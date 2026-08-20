import requests
import re
import html
import subprocess
import os
import json
import time


# ============================================================
# ПУТИ
# ============================================================

ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)

TEST_FILE = os.path.join(
    ENGINE_FOLDER,
    "yandex_test.mp3"
)


# ============================================================
# API
# ============================================================

SEARCH_API = (
    "https://api.music.yandex.net/search"
)

DOWNLOAD_INFO_API = (
    "https://api.music.yandex.net/"
    "tracks/{}/download-info"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),

    "Accept":
        "application/json, text/plain, */*",

    "Accept-Language":
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",

    "Referer":
        "https://music.yandex.ru/"
}


TIMEOUT = 30


# ============================================================
# ФОРМАТИРОВАНИЕ
# ============================================================

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


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize(text):

    if text is None:
        return ""

    text = html.unescape(
        str(text)
    )

    text = text.lower()

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
        r"\b(featuring|feat\.?|ft\.?)\b",
        " ",
        text
    )

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


# ============================================================
# ИСПОЛНИТЕЛИ
# ============================================================

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

    return ", ".join(
        get_artists(track)
    )


# ============================================================
# АЛЬБОМ
# ============================================================

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
# ПОИСК
# ============================================================

def search_track(
    artist,
    title,
    duration
):

    query = (
        f"{artist} {title}"
    )

    print()
    print("=" * 60)
    print(
        "1. ПОИСК ТРЕКА"
    )
    print("=" * 60)

    print()
    print(
        "Запрос:",
        query
    )

    params = {
        "text": query,
        "page": 0,
        "type": "track",
        "nococrrect": "true"
    }

    try:

        response = requests.get(
            SEARCH_API,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        )

    except Exception as e:

        print(
            "Ошибка запроса:",
            e
        )

        return None

    print(
        "HTTP-код:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            response.text[:2000]
        )

        return None

    try:

        data = response.json()

    except Exception as e:

        print(
            "Ошибка JSON:",
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
        return None

    tracks = result.get(
        "tracks"
    )

    if not isinstance(
        tracks,
        dict
    ):
        return None

    results = tracks.get(
        "results"
    )

    if not isinstance(
        results,
        list
    ):
        return None

    print(
        "Найдено:",
        len(results)
    )

    candidates = []

    wanted_artist = normalize(
        artist
    )

    wanted_title = normalize(
        title
    )

    for track in results:

        if not isinstance(
            track,
            dict
        ):
            continue

        found_artist = normalize(
            get_artist_string(track)
        )

        found_title = normalize(
            track.get(
                "title",
                ""
            )
        )

        duration_ms = track.get(
            "durationMs"
        )

        found_duration = None

        if duration_ms:

            try:

                found_duration = (
                    float(duration_ms)
                    / 1000
                )

            except Exception:
                pass

        score = 0

        if found_title == wanted_title:
            score += 1000

        elif wanted_title in found_title:
            score += 500

        if wanted_artist == found_artist:
            score += 1000

        elif wanted_artist in found_artist:
            score += 500

        if (
            found_duration is not None
            and
            duration is not None
        ):

            difference = abs(
                found_duration
                -
                duration
            )

            if difference <= 1:
                score += 500

            elif difference <= 2:
                score += 300

            elif difference <= 3:
                score += 150

            elif difference > 5:
                score -= 500

        candidates.append({
            "track": track,
            "score": score,
            "duration": found_duration
        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    best = candidates[0]

    track = best[
        "track"
    ]

    print()
    print(
        "Выбран:"
    )

    print(
        "Исполнитель:",
        get_artist_string(track)
    )

    print(
        "Название:",
        track.get("title")
    )

    print(
        "Альбом:",
        get_album(track)
    )

    print(
        "Длительность:",
        format_duration(
            best["duration"]
        )
    )

    print(
        "ID:",
        track.get("id")
    )

    print(
        "Оценка:",
        best["score"]
    )

    return track


# ============================================================
# DOWNLOAD INFO
# ============================================================

def get_download_info(
    track_id
):

    print()
    print("=" * 60)
    print(
        "2. ПОЛУЧЕНИЕ DOWNLOAD-INFO"
    )
    print("=" * 60)

    url = DOWNLOAD_INFO_API.format(
        track_id
    )

    print()
    print(
        "URL:"
    )

    print(
        url
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

    except Exception as e:

        print(
            "Ошибка запроса:",
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

    if response.status_code != 200:

        print()
        print(
            "Ответ:"
        )

        print(
            response.text[:5000]
        )

        return None

    try:

        data = response.json()

    except Exception as e:

        print(
            "Ошибка JSON:",
            e
        )

        print(
            response.text[:5000]
        )

        return None

    result = data.get(
        "result"
    )

    if not isinstance(
        result,
        list
    ):

        print()
        print(
            "Поле result имеет "
            "неожиданный формат."
        )

        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )[:5000]
        )

        return None

    print()
    print(
        "Вариантов:",
        len(result)
    )

    print()

    for index, item in enumerate(
        result,
        1
    ):

        print(
            f"ВАРИАНТ {index}"
        )

        print(
            "  codec:",
            item.get("codec")
        )

        print(
            "  bitrate:",
            item.get(
                "bitrateInKbps"
            ),
            "kbps"
        )

        print(
            "  preview:",
            item.get(
                "preview"
            )
        )

        print(
            "  direct:",
            item.get(
                "direct"
            )
        )

        print(
            "  gain:",
            item.get(
                "gain"
            )
        )

        print(
            "  container:",
            item.get(
                "container"
            )
        )

        print(
            "  downloadInfoUrl:",
            item.get(
                "downloadInfoUrl"
            )
        )

        print()

    return result


# ============================================================
# XML DOWNLOAD INFO
# ============================================================

def get_file_info(
    download_info_url
):

    print()
    print("=" * 60)
    print(
        "3. ПОЛУЧЕНИЕ ДАННЫХ ФАЙЛА"
    )
    print("=" * 60)

    print()
    print(
        "Запрос downloadInfoUrl..."
    )

    try:

        response = requests.get(
            download_info_url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

    except Exception as e:

        print(
            "Ошибка:",
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

    text = response.text

    print()
    print(
        "Ответ XML:"
    )

    print(
        text[:3000]
    )

    def get_xml_value(
        name
    ):

        pattern = (
            r"<"
            + re.escape(name)
            + r">"
            r"(.*?)"
            r"</"
            + re.escape(name)
            + r">"
        )

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:
            return (
                html.unescape(
                    match.group(1)
                )
                .strip()
            )

        return None

    host = get_xml_value(
        "host"
    )

    path = get_xml_value(
        "path"
    )

    ts = get_xml_value(
        "ts"
    )

    sign = get_xml_value(
        "s"
    )

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
        if sign
        else "не найден"
    )

    if not host or not path:

        print()
        print(
            "Не удалось получить "
            "host/path."
        )

        return None

    # --------------------------------------------------------
    # Формирование URL
    # --------------------------------------------------------

    file_url = (
        "https://"
        + host
        + path
    )

    separator = (
        "&"
        if "?" in file_url
        else "?"
    )

    if ts:
        file_url += (
            separator
            + "ts="
            + ts
        )

        separator = "&"

    if sign:
        file_url += (
            separator
            + "s="
            + sign
        )

    print()
    print(
        "Сформированный URL:"
    )

    print(
        file_url
    )

    return file_url


# ============================================================
# СКАЧИВАНИЕ
# ============================================================

def download_test_file(
    url
):

    print()
    print("=" * 60)
    print(
        "4. ТЕСТОВОЕ СКАЧИВАНИЕ"
    )
    print("=" * 60)

    if os.path.exists(
        TEST_FILE
    ):

        try:
            os.remove(
                TEST_FILE
            )
        except Exception:
            pass

    print()
    print(
        "Файл:",
        TEST_FILE
    )

    try:

        with requests.get(
            url,
            headers={
                **HEADERS,
                "Accept":
                    "audio/mpeg,audio/*;q=0.9,*/*;q=0.8"
            },
            stream=True,
            timeout=60
        ) as response:

            print(
                "HTTP-код:",
                response.status_code
            )

            if response.status_code != 200:

                print()
                print(
                    "Скачивание не удалось."
                )

                print(
                    response.text[:2000]
                )

                return False

            total = 0

            with open(
                TEST_FILE,
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
            round(
                total /
                1024 /
                1024,
                3
            ),
            "МБ"
        )

    except Exception as e:

        print()
        print(
            "Ошибка скачивания:",
            e
        )

        return False

    if not os.path.exists(
        TEST_FILE
    ):

        return False

    if os.path.getsize(
        TEST_FILE
    ) < 10240:

        print()
        print(
            "Файл слишком маленький."
        )

        return False

    print()
    print(
        "Файл скачан."
    )

    return True


# ============================================================
# FFPROBE
# ============================================================

def check_audio():

    print()
    print("=" * 60)
    print(
        "5. ПРОВЕРКА АУДИО"
    )
    print("=" * 60)

    if not os.path.isfile(
        FFPROBE
    ):

        print()
        print(
            "ffprobe.exe не найден:"
        )

        print(
            FFPROBE
        )

        return None

    command = [
        FFPROBE,

        "-v",
        "error",

        "-show_entries",
        "format=format_name,duration,size",

        "-of",
        "json",

        TEST_FILE
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )

    except Exception as e:

        print(
            "Ошибка ffprobe:",
            e
        )

        return None

    if result.returncode != 0:

        print()
        print(
            "ffprobe не смог "
            "прочитать файл."
        )

        print(
            result.stderr
        )

        return None

    try:

        data = json.loads(
            result.stdout
        )

    except Exception:

        print(
            result.stdout
        )

        return None

    fmt = data.get(
        "format",
        {}
    )

    duration = fmt.get(
        "duration"
    )

    size = fmt.get(
        "size"
    )

    format_name = fmt.get(
        "format_name"
    )

    print()
    print(
        "Формат:",
        format_name
    )

    print(
        "Размер:",
        size,
        "байт"
    )

    if duration:

        print(
            "Длительность:",
            format_duration(
                float(duration)
            )
        )

    return {
        "duration":
            float(duration)
            if duration
            else None,

        "size":
            int(float(size))
            if size
            else None,

        "format":
            format_name
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "YANDEX MUSIC DOWNLOAD TEST"
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

    if not artist or not title:

        print(
            "\nИсполнитель и название обязательны."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    duration = None

    if duration_input:

        try:

            duration = float(
                duration_input
            )

        except ValueError:

            print(
                "\nНекорректная длительность."
            )

            input(
                "\nНажмите Enter для выхода..."
            )

            return

    # --------------------------------------------------------
    # 1. SEARCH
    # --------------------------------------------------------

    track = search_track(
        artist,
        title,
        duration
    )

    if not track:

        print()
        print(
            "ПОИСК НЕ УДАЛСЯ."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    track_id = track.get(
        "id"
    )

    if not track_id:

        print(
            "\nУ трека отсутствует ID."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # 2. DOWNLOAD INFO
    # --------------------------------------------------------

    variants = get_download_info(
        track_id
    )

    if not variants:

        print()
        print(
            "=" * 60
        )

        print(
            "DOWNLOAD-INFO НЕ ПОЛУЧЕН."
        )

        print(
            "=" * 60
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # Выбираем MP3.
    #
    # Сначала предпочитаем НЕ preview.
    # Затем максимальный bitrate.
    # --------------------------------------------------------

    mp3_variants = [
        item
        for item in variants
        if item.get("codec")
        == "mp3"
    ]

    if not mp3_variants:

        print()
        print(
            "MP3-вариантов нет."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    mp3_variants.sort(
        key=lambda item: (
            bool(
                item.get(
                    "preview",
                    False
                )
            ),
            -int(
                item.get(
                    "bitrateInKbps"
                )
                or 0
            )
        )
    )

    selected = mp3_variants[0]

    print()
    print("=" * 60)
    print(
        "ВЫБРАННЫЙ MP3"
    )
    print("=" * 60)

    print()
    print(
        "Bitrate:",
        selected.get(
            "bitrateInKbps"
        ),
        "kbps"
    )

    print(
        "Preview:",
        selected.get(
            "preview"
        )
    )

    print(
        "Direct:",
        selected.get(
            "direct"
        )
    )

    download_info_url = selected.get(
        "downloadInfoUrl"
    )

    if not download_info_url:

        print()
        print(
            "downloadInfoUrl отсутствует."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # 3. XML
    # --------------------------------------------------------

    file_url = get_file_info(
        download_info_url
    )

    if not file_url:

        print()
        print(
            "Не удалось сформировать "
            "URL аудиофайла."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # 4. DOWNLOAD
    # --------------------------------------------------------

    if not download_test_file(
        file_url
    ):

        print()
        print(
            "ТЕСТОВОЕ СКАЧИВАНИЕ НЕ УДАЛОСЬ."
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    # --------------------------------------------------------
    # 5. FFPROBE
    # --------------------------------------------------------

    audio_info = check_audio()

    print()
    print("=" * 60)

    if audio_info:

        print(
            "ТЕСТ ЗАВЕРШЁН"
        )

        print("=" * 60)

        print()
        print(
            "Фактическая длительность:"
        )

        print(
            format_duration(
                audio_info["duration"]
            )
        )

        print()
        print(
            "Файл:"
        )

        print(
            TEST_FILE
        )

    else:

        print(
            "ТЕСТ НЕ ПРОЙДЕН"
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
