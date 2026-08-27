# Censuru.net — SoundCloud source
# Реальная рабочая логика перенесена из downloader.py.

import os
import re
import html
import shutil
import subprocess
import requests
from urllib.parse import unquote

from sources_utils import normalize, normalize_words
ENGINE_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive"
}

SOUNDCLOUD_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": HEADERS["Accept-Language"],
    "Referer": "https://soundcloud.com/"
}


SOUNDCLOUD_SEARCH_URL = (
    "https://api-v2.soundcloud.com/search/tracks"
)


SOUNDCLOUD_DURATION_TOLERANCE = 20.0

SOUNDCLOUD_SEARCH_TIMEOUT = 15

SOUNDCLOUD_DOWNLOAD_TIMEOUT = 90

SOUNDCLOUD_SEARCH_RESULTS = 50

SOUNDCLOUD_CLIENT_ID_TIMEOUT = 15

SOUNDCLOUD_CLIENT_ID_CACHE = None

YTDLP = os.path.join(
    ENGINE_FOLDER,
    "yt-dlp.exe"
)

FFMPEG = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffmpeg.exe"
)

FFPROBE = os.path.join(
    ENGINE_FOLDER,
    "ffmpeg",
    "bin",
    "ffprobe.exe"
)

MIN_FILE_SIZE = 10 * 1024

EXACT_MATCH_TOLERANCE = 30.0

SOUNDCLOUD_SERVICE_MODIFIERS = (
    "remix", "remixed", "remaster", "remastered", "rework", "bootleg",
    "nightcore", "slowed", "sped up", "speed up", "edit", "live",
    "acoustic", "instrumental", "mashup", "flip", "extended", "radio edit",
    "version", "mix", "clean", "censored", "explicit", "uncensored",
    "ремикс", "ремастер", "ремикш", "переработка", "бутлег", "найткор",
    "ночкор", "замедление", "замедленный", "ускорение", "ускоренный",
    "эдит", "лайв", "акустика", "инструментал", "мэшап", "мешап", "флип",
    "кавер", "караоке", "расширенная версия", "клубная версия", "реверб",
)

def get_soundcloud_client_id():
    global SOUNDCLOUD_CLIENT_ID_CACHE

    if SOUNDCLOUD_CLIENT_ID_CACHE:
        return SOUNDCLOUD_CLIENT_ID_CACHE

    try:
        response = requests.get(
            "https://soundcloud.com/",
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_CLIENT_ID_TIMEOUT
        )

        if response.status_code != 200:
            return None

        text = response.text

        patterns = [
            r'client_id["\']?\s*[:=]\s*["\']'
            r'([A-Za-z0-9_-]{32,})["\']',

            r'clientId["\']?\s*[:=]\s*["\']'
            r'([A-Za-z0-9_-]{32,})["\']'
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.I
            )

            if match:
                SOUNDCLOUD_CLIENT_ID_CACHE = (
                    match.group(1)
                )

                return SOUNDCLOUD_CLIENT_ID_CACHE

        scripts = re.findall(
            r'<script[^>]+src=["\']'
            r'([^"\']+)["\']',
            text,
            re.I
        )

        for script in scripts:
            if script.startswith("//"):
                script = (
                    "https:"
                    + script
                )

            elif script.startswith("/"):
                script = (
                    "https://soundcloud.com"
                    + script
                )

            elif not script.startswith(
                "http"
            ):
                continue

            try:
                r = requests.get(
                    script,
                    headers=SOUNDCLOUD_HEADERS,
                    timeout=SOUNDCLOUD_CLIENT_ID_TIMEOUT
                )

                if r.status_code != 200:
                    continue

                for pattern in patterns:
                    match = re.search(
                        pattern,
                        r.text,
                        re.I
                    )

                    if match:
                        SOUNDCLOUD_CLIENT_ID_CACHE = (
                            match.group(1)
                        )

                        return (
                            SOUNDCLOUD_CLIENT_ID_CACHE
                        )

            except Exception:
                continue

    except Exception:
        pass

    return None

def normalize_soundcloud_metadata(
    artist,
    title
):
    import re

    raw_artist = str(
        artist or ""
    ).strip()

    raw_title = str(
        title or ""
    ).strip()

    soundcloud_artist = ""
    soundcloud_original_title = raw_title
    soundcloud_clean_title = raw_title

    # --------------------------------------------------------
    # 1. Проверяем, является ли artist служебным описанием.
    # --------------------------------------------------------

    technical_artist = bool(
        re.search(
            r"(?i)"
            r"(?:"
            r"video\s+prod\.?\s+by|"
            r"music\s+by|"
            r"produced\s+by|"
            r"production\s+by|"
            r"prod\.?\s+by|"
            r"beat\s+by"
            r")",
            raw_artist
        )
    )

    # --------------------------------------------------------
    # 2. Разбираем:
    #
    # KIZARU - Если бы я был тобой (Prod.Realitybeats)
    #
    # --------------------------------------------------------

    title_match = re.match(
        r"^\s*(.+?)\s*[-–—:]\s*(.+?)\s*$",
        raw_title
    )

    if title_match:

        possible_artist = (
            title_match.group(1).strip()
        )

        possible_title = (
            title_match.group(2).strip()
        )

        if (
            possible_artist
            and possible_title
        ):

            soundcloud_artist = (
                possible_artist
            )

            soundcloud_clean_title = (
                possible_title
            )

    # --------------------------------------------------------
    # 3. Если title не имеет Artist - Title,
    #    используем нормальный artist.
    # --------------------------------------------------------

    if not soundcloud_artist:

        if not technical_artist:

            soundcloud_artist = (
                raw_artist
            )

    # --------------------------------------------------------
    # 4. Удаляем служебные Prod./Produced/... из названия.
    # --------------------------------------------------------

    soundcloud_clean_title = re.sub(
        r"\s*"
        r"[\(\[]"
        r"\s*"
        r"(?:"
        r"prod\.?|"
        r"produced\s+by|"
        r"production\s+by|"
        r"music\s+by|"
        r"beat\s+by"
        r")"
        r"[^)\]]*"
        r"[\)\]]"
        r"\s*$",
        "",
        soundcloud_clean_title,
        flags=re.I
    ).strip()

    # Дополнительный вариант:
    # Prod.Realitybeats без скобок.
    soundcloud_clean_title = re.sub(
        r"\s+"
        r"prod(?:uced)?\.?"
        r"\s*"
        r"(?:by)?"
        r"\s*"
        r"[\w.@:/-]+"
        r"\s*$",
        "",
        soundcloud_clean_title,
        flags=re.I
    ).strip()

    # --------------------------------------------------------
    # 5. Если artist всё ещё пустой,
    #    пробуем извлечь его из очищенного title.
    # --------------------------------------------------------

    if not soundcloud_artist:

        fallback_match = re.match(
            r"^\s*(.+?)\s*[-–—:]\s*(.+?)\s*$",
            soundcloud_clean_title
        )

        if fallback_match:

            soundcloud_artist = (
                fallback_match.group(1).strip()
            )

            soundcloud_clean_title = (
                fallback_match.group(2).strip()
            )

    # --------------------------------------------------------
    # 6. Финальная очистка пробелов.
    # --------------------------------------------------------

    soundcloud_artist = re.sub(
        r"\s+",
        " ",
        soundcloud_artist
    ).strip()

    soundcloud_original_title = re.sub(
        r"\s+",
        " ",
        soundcloud_original_title
    ).strip()

    soundcloud_clean_title = re.sub(
        r"\s+",
        " ",
        soundcloud_clean_title
    ).strip()

    return (
        soundcloud_artist,
        soundcloud_original_title,
        soundcloud_clean_title
    )

def evaluate_soundcloud_candidate(
    candidate,
    artist,
    title,
    duration
):
    """
    Оценивает SoundCloud-кандидата.

    Главный принцип:

    1. Исполнитель является обязательным условием.
    2. Точное название + точный исполнитель имеют
       абсолютный приоритет.
    3. Кандидат с другим исполнителем не может
       победить правильного исполнителя только
       из-за совпадения названия.
    4. Remix / Ремикс / Slowed / Nightcore /
       Reverb / Edit и другие альтернативные
       версии получают сильный штраф.
    5. Регистр не имеет значения.
    6. feat / ft / featuring НЕ являются
       модификаторами версии.
    """

    if not isinstance(
        candidate,
        dict
    ):
        return None

    candidate_title = str(
        candidate.get("title")
        or candidate.get("name")
        or ""
    ).strip()

    if not candidate_title:
        return None

    candidate_user = candidate.get(
        "user"
    )

    candidate_username = ""

    if isinstance(
        candidate_user,
        dict
    ):
        candidate_username = str(
            candidate_user.get("username")
            or candidate_user.get("permalink")
            or ""
        ).strip()

    candidate_artist = str(
        candidate.get("artist")
        or candidate.get("publisher")
        or candidate.get("metadata_artist")
        or ""
    ).strip()


    # ========================================================
    # НОРМАЛИЗАЦИЯ
    # ========================================================

    def norm(value):

        value = str(
            value or ""
        ).lower()

        value = re.sub(
            r"https?://\S+",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = value.replace(
            "&",
            " and "
        )

        value = re.sub(
            r"[^\w\sа-яё]",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value


    def tokens(value):

        return set(
            norm(value).split()
        )


    def normalize_artist_confusables(value):
        value = norm(value)

        replacements = str.maketrans({
            "a": "а",
            "c": "с",
            "e": "е",
            "o": "о",
            "p": "р",
            "x": "х",
            "y": "у",
            "k": "к",
            "m": "м",
            "t": "т",
            "b": "в",
            "h": "н",
        })

        return value.translate(replacements)

    requested_artist = normalize_artist_confusables(
        artist
    )

    requested_title = norm(
        title
    )

    candidate_title_norm = norm(
        candidate_title
    )

    candidate_artist_norm = normalize_artist_confusables(
        candidate_artist
    )

    candidate_username_norm = normalize_artist_confusables(
        candidate_username
    )

    if not requested_title:
        return None


    requested_title_tokens = tokens(
        requested_title
    )

    requested_artist_tokens = tokens(
        requested_artist
    )


    # ========================================================
    # ОБРАБОТКА "Artist - Track"
    # ========================================================

    candidate_track_title = (
        candidate_title_norm
    )

    title_artist_part = ""

    separator_match = re.match(
        r"^\s*(.*?)\s+-\s+(.*?)\s*$",
        candidate_title_norm
    )

    if separator_match:

        possible_artist = (
            separator_match.group(
                1
            ).strip()
        )

        possible_title = (
            separator_match.group(
                2
            ).strip()
        )

        if (
            possible_artist
            and possible_title
        ):

            title_artist_part = (
                possible_artist
            )

            candidate_track_title = (
                possible_title
            )


    # ========================================================
    # МОДИФИКАТОРЫ ВЕРСИЙ
    #
    # IGNORECASE означает, что:
    #
    # REMIX
    # Remix
    # remix
    # РЕМИКС
    # Ремикс
    #
    # обрабатываются одинаково.
    # ========================================================

    version_patterns = (

        # English

        r"\bclean\b",
        r"\bcensored\b",
        r"\bexplicit\b",
        r"\buncensored\b",

        r"\bremix\w*\b",
        r"\bremaster\w*\b",
        r"\brework\w*\b",
        r"\bbootleg\w*\b",

        r"\bnightcore\w*\b",
        r"\bslowed\w*\b",

        r"\bsped\s*up\b",
        r"\bspeed\s*up\b",

        r"\bedit\w*\b",
        r"\blive\w*\b",
        r"\bacoustic\w*\b",

        r"\binstrumental\w*\b",
        r"\bmashup\w*\b",
        r"\bflip\w*\b",

        r"\bextended\w*\b",

        r"\bradio\s+edit\b",

        r"\bversion\s*\d+\b",
        r"\bver\.?\s*\d+\b",

        r"\bpart\s*\d+\b",
        r"\bpt\.?\s*\d+\b",

        r"\b\d+\s*(?:mix|edit|version)\b",


        # Russian

        r"\bцензур\w*\b",
        r"\bнецензур\w*\b",

        r"\bремикс\w*\b",
        r"\bремикш\w*\b",

        r"\bремастер\w*\b",
        r"\bремастирован\w*\b",
        r"\bремастирова\w*\b",

        r"\bпереработк\w*\b",
        r"\bбутлег\w*\b",

        r"\bночкор\w*\b",
        r"\bнайткор\w*\b",

        r"\bзамедлен\w*\b",
        r"\bзамедл\w*\b",

        r"\bускорен\w*\b",
        r"\bускор\w*\b",

        r"\bспид\s*ап\b",
        r"\bспид-ап\b",

        r"\bреверб\w*\b",

        r"\bэдит\w*\b",
        r"\bлайв\w*\b",

        r"\bакустическ\w*\b",
        r"\bинструментал\w*\b",

        r"\bмэшап\w*\b",
        r"\bмешап\w*\b",

        r"\bфлип\w*\b",

        r"\bкавер\w*\b",
        r"\bкараоке\w*\b",

        r"\bрасширен\w*\b",

        r"\bрадио\s+верси\w*\b",

        r"\bклубн\w*\b",
    )


    has_version_modifier = any(
        re.search(
            pattern,
            candidate_title,
            flags=re.IGNORECASE
        )
        for pattern
        in version_patterns
    )


    # ========================================================
    # ПРОВЕРКА ИСПОЛНИТЕЛЯ
    #
    # Это КРИТИЧЕСКИ ВАЖНО.
    #
    # Если запрос:
    #
    #     Платина Abu Dhabi Ba6y
    #
    # кандидат:
    #
    #     Dummo - Abu Dhabi Ba6y
    #
    # НЕ проходит.
    #
    # Совпадение названия само по себе
    # недостаточно.
    # ========================================================

    artist_match = False

    exact_artist = False

    if requested_artist:

        # ----------------------------------------------------
        # Точное совпадение username
        # ----------------------------------------------------

        if (
            candidate_username_norm
            == requested_artist
        ):
            artist_match = True
            exact_artist = True


        # ----------------------------------------------------
        # Точное совпадение artist metadata
        # ----------------------------------------------------

        if (
            candidate_artist_norm
            == requested_artist
        ):
            artist_match = True
            exact_artist = True


        # ----------------------------------------------------
        # Несколько исполнителей.
        #
        # Например:
        #
        # requested:
        # Платина OG Buda MAYOT
        #
        # candidate:
        # Платина OG Buda MAYOT Official
        #
        # Такое совпадение разрешаем.
        # ----------------------------------------------------

        if not artist_match:

            sources = []

            if candidate_username_norm:
                sources.append(
                    candidate_username_norm
                )

            if candidate_artist_norm:
                sources.append(
                    candidate_artist_norm
                )

            requested_artist_set = set(
                requested_artist.split()
            )

            for source in sources:

                source_set = set(
                    source.split()
                )

                if (
                    requested_artist_set
                    <= source_set
                ):

                    artist_match = True

                    break


        # ----------------------------------------------------
        # SoundCloud может хранить:
        #
        # Artist - Track
        #
        # непосредственно в title.
        # ----------------------------------------------------

        if (
            not artist_match
            and title_artist_part
        ):

            if (
                title_artist_part
                == requested_artist
            ):

                artist_match = True
                exact_artist = True

            elif (
                requested_artist_tokens
                and requested_artist_tokens
                <= set(
                    title_artist_part.split()
                )
            ):

                artist_match = True


        # ----------------------------------------------------
        # Если исполнитель НЕ совпадает —
        # кандидат полностью отбрасывается.
        # ----------------------------------------------------

        if not artist_match:
            return None


    # ========================================================
    # СОВПАДЕНИЕ НАЗВАНИЯ
    # ========================================================

    exact_title = (
        candidate_track_title
        == requested_title
    )


    candidate_title_tokens = tokens(
        candidate_track_title
    )


    title_intersection = (
        requested_title_tokens
        & candidate_title_tokens
    )


    title_ratio = (
        len(title_intersection)
        / max(
            1,
            len(
                requested_title_tokens
            )
        )
    )


    if (
        title_ratio < 0.50
        and not exact_title
    ):
        return None


    # ========================================================
    # ТОЧНАЯ ИДЕНТИЧНОСТЬ
    #
    # Точный исполнитель
    # +
    # точное название
    # +
    # НЕ remix/version
    #
    # получает абсолютный приоритет.
    # ========================================================

    exact_identity = (
        exact_title
        and (
            exact_artist
            or not requested_artist
        )
        and not has_version_modifier
    )


    # ========================================================
    # ДЛИТЕЛЬНОСТЬ
    # ========================================================

    candidate_duration = candidate.get(
        "duration"
    )

    try:

        if candidate_duration is not None:

            candidate_duration = float(
                candidate_duration
            )

            if candidate_duration > 1000:

                candidate_duration /= 1000.0

    except (
        TypeError,
        ValueError
    ):

        candidate_duration = None


    try:

        requested_duration = (
            float(duration)
            if duration is not None
            else None
        )

    except (
        TypeError,
        ValueError
    ):

        requested_duration = None


    duration_difference = None


    if (
        candidate_duration is not None
        and requested_duration is not None
    ):

        duration_difference = abs(
            candidate_duration
            - requested_duration
        )

        # Длительность из SoundCloud API НЕ является
        # причиной удаления кандидата.
        #
        # SoundCloud может отдавать неправильную duration.
        # Поэтому кандидат остаётся в рейтинге и может
        # быть реально скачан.
        #
        # Окончательная проверка выполняется после загрузки
        # через ffprobe внутри download_from_soundcloud().
        #
        # Это позволяет сделать:
        #
        #   TOP 1 -> скачать -> duration не совпала -> reject
        #   TOP 2 -> скачать -> проверить
        #   TOP 3 -> скачать -> проверить
        #   ...
        #
        # При этом сама оценка кандидата и остальные
        # ограничения поиска не изменяются.


    # ========================================================
    # ШТРАФЫ
    # ========================================================

    version_penalty = 0


    if has_version_modifier:

        version_penalty += 80


    # Дополнительные слова в названии.
    #
    # feat / ft / featuring НЕ штрафуем.
    # Это важно, поскольку дополнительные
    # исполнители могут быть частью оригинального
    # трека.

    extra_tokens = (
        candidate_title_tokens
        - requested_title_tokens
    )


    meaningful_extra_tokens = set(
        extra_tokens
    )


    meaningful_extra_tokens -= {
        "feat",
        "ft",
        "featuring"
    }


    if meaningful_extra_tokens:

        version_penalty += (
            len(
                meaningful_extra_tokens
            )
            * 20
        )


    # ========================================================
    # SCORE
    # ========================================================

    score = 0.0


    score += (
        title_ratio
        * 60
    )


    if exact_title:

        score += 100


    if artist_match:

        score += 60


    if exact_artist:

        score += 100


    if (
        title_artist_part
        == requested_artist
    ):

        score += 50


    if duration_difference is not None:

        if duration_difference <= 1:

            score += 40

        elif duration_difference <= 2:

            score += 32

        elif duration_difference <= 4:

            score += 22

        elif duration_difference <= 6:

            score += 12

        else:

            score += 4


    score -= version_penalty


    # ========================================================
    # АБСОЛЮТНЫЙ ПРИОРИТЕТ
    #
    # Если внутри первых 15 результатов есть:
    #
    #     правильный исполнитель
    #     +
    #     точное название
    #
    # он получает score >= 1000.
    #
    # Поэтому случайный трек с другим исполнителем
    # никогда не сможет его обойти.
    # ========================================================

    if exact_identity:

        score = max(
            score,
            1000.0
        )


    # ========================================================
    # MINIMUM SCORE
    # ========================================================

    if exact_identity:

        minimum_score = 900

    elif (
        exact_title
        and artist_match
    ):

        minimum_score = 100

    elif (
        title_ratio >= 0.80
        and artist_match
    ):

        minimum_score = 65

    elif (
        artist_match
        and title_ratio >= 0.60
    ):

        minimum_score = 65

    else:

        minimum_score = 75


    if score < minimum_score:
        return None


    return {
        "score": score,
        "candidate": candidate,
        "title_ratio": title_ratio,
        "artist_ratio": (
            1.0
            if artist_match
            else 0.0
        ),
        "duration_difference": (
            duration_difference
        ),
        "exact_title": exact_title,
        "exact_artist": exact_artist,
        "exact_identity": exact_identity,
    }

def fetch_soundcloud_results(
    query_str,
    client_id
):
    try:

        response = requests.get(
            "https://api-v2.soundcloud.com/"
            "search/tracks",
            params={
                "q": query_str,
                "client_id": client_id,
                "limit": SOUNDCLOUD_SEARCH_RESULTS
            },
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_SEARCH_TIMEOUT
        )

        print(
            "SoundCloud API: HTTP-код: "
            f"{response.status_code}"
        )

        print(
            "SoundCloud API: размер ответа: "
            f"{len(response.text)} байт"
        )

        if response.status_code != 200:

            print(
                "SoundCloud API: ответ "
                "не 200."
            )

            if response.text:

                print(
                    "SoundCloud API: ответ:"
                )

                print(
                    response.text[:500]
                )

            return []

        try:

            data = response.json()

        except Exception as error:

            print(
                "SoundCloud API: ошибка "
                "JSON: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            print(
                "SoundCloud API: "
                "начало ответа:"
            )

            print(
                response.text[:500]
            )

            return []

        collection = (
            data.get("collection")
            if isinstance(data, dict)
            else None
        )

        if not isinstance(
            collection,
            list
        ):

            print(
                "SoundCloud API: "
                "collection отсутствует "
                "или имеет неверный формат."
            )

            return []

        print(
            "SoundCloud API: "
            f"collection = {len(collection)}"
        )

        return collection

    except Exception as error:

        print(
            "SoundCloud API: исключение: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return []

def search_soundcloud(
    artist,
    title,
    duration=None
):
    """
    Каскадный поиск SoundCloud.

    Этап 1:
        полный исполнитель + очищенное название.

    Этап 2:
        основной исполнитель + название без feat.

    Этап 3:
        полный исполнитель + исходное название.

    Этап 4:
        основной исполнитель + исходное название без feat.

    Каждый этап независим.

    Следующий этап запускается только если
    предыдущий не дал подходящего кандидата.
    """

    if not artist:
        artist = ""

    if not title:
        title = ""

    original_artist = str(
        artist
    ).strip()

    original_title = str(
        title
    ).strip()

    print(
        "SoundCloud: запуск поиска..."
    )

    print(
        "SoundCloud: исполнитель: "
        f"{original_artist}"
    )

    print(
        "SoundCloud: название: "
        f"{original_title}"
    )

    print(
        "SoundCloud: длительность: "
        f"{duration}"
    )

    (
        soundcloud_artist,
        soundcloud_original_title,
        soundcloud_clean_title
    ) = normalize_soundcloud_metadata(
        original_artist,
        original_title
    )

    print(
        "SoundCloud: нормализованный исполнитель: "
        f"{soundcloud_artist}"
    )

    print(
        "SoundCloud: исходное название: "
        f"{soundcloud_original_title}"
    )

    print(
        "SoundCloud: очищенное название: "
        f"{soundcloud_clean_title}"
    )

    if not soundcloud_artist:

        soundcloud_artist = (
            original_artist
        )

    if not soundcloud_clean_title:

        soundcloud_clean_title = (
            original_title
        )

    # --------------------------------------------------------
    # Очистка служебных конструкций
    # --------------------------------------------------------

    def clean_query(value):

        value = str(
            value or ""
        )

        value = re.sub(
            r"https?://\S+",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\b(?:video\s+)?prod(?:uced)?\.?\s+by\b.*",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\bmusic\s+by\b.*",
            " ",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value

    # --------------------------------------------------------
    # Основной исполнитель
    # --------------------------------------------------------

    def get_primary_artist(value):

        value = str(
            value or ""
        ).strip()

        if not value:

            return ""

        parts = re.split(
            r"\s*,\s*",
            value
        )

        if parts:

            primary = (
                parts[0].strip()
            )

            if primary:

                return primary

        return value

    # --------------------------------------------------------
    # Удаление feat только для fallback
    # --------------------------------------------------------

    def remove_featured_artists(value):

        value = str(
            value or ""
        ).strip()

        if not value:

            return ""

        value = re.sub(
            r"\s*[\(\[]\s*"
            r"(?:feat\.?|ft\.?|featuring)\b"
            r".*?"
            r"[\)\]]\s*$",
            "",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+"
            r"(?:feat\.?|ft\.?|featuring)\b"
            r".*$",
            "",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        return value

    # --------------------------------------------------------
    # Подготавливаем основные запросы
    # --------------------------------------------------------

    cleaned_query_artist = clean_query(
        soundcloud_artist
    )

    cleaned_query_title = clean_query(
        soundcloud_clean_title
    )

    original_query_artist = clean_query(
        original_artist
    )

    original_query_title = clean_query(
        original_title
    )

    if not cleaned_query_artist:

        cleaned_query_artist = (
            original_query_artist
        )

    if not cleaned_query_title:

        cleaned_query_title = (
            original_query_title
        )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    primary_artist = get_primary_artist(
        cleaned_query_artist
    )

    primary_artist = clean_query(
        primary_artist
    )

    if not primary_artist:

        primary_artist = (
            cleaned_query_artist
        )

    cleaned_base_title = (
        remove_featured_artists(
            cleaned_query_title
        )
    )

    original_base_title = (
        remove_featured_artists(
            original_query_title
        )
    )

    if not cleaned_base_title:

        cleaned_base_title = (
            cleaned_query_title
        )

    if not original_base_title:

        original_base_title = (
            original_query_title
        )

    print(
        "SoundCloud: основной исполнитель "
        "для fallback-поиска: "
        f"{primary_artist}"
    )

    print(
        "SoundCloud: базовое очищенное название "
        "для fallback-поиска: "
        f"{cleaned_base_title}"
    )

    # --------------------------------------------------------
    # КАСКАД
    # --------------------------------------------------------

    search_stages = [

        (
            1,
            "исполнитель + очищенное название",
            (
                f"{cleaned_query_artist} "
                f"{cleaned_query_title}"
            ).strip(),
            cleaned_query_artist,
            cleaned_query_title
        ),

        (
            2,
            "основной исполнитель + название без feat",
            (
                f"{primary_artist} "
                f"{cleaned_base_title}"
            ).strip(),
            primary_artist,
            cleaned_base_title
        ),

        (
            3,
            "исполнитель + исходное название",
            (
                f"{original_query_artist} "
                f"{original_query_title}"
            ).strip(),
            original_query_artist,
            original_query_title
        ),

        (
            4,
            "основной исполнитель + исходное название без feat",
            (
                f"{primary_artist} "
                f"{original_base_title}"
            ).strip(),
            primary_artist,
            original_base_title
        ),
    ]

    # --------------------------------------------------------
    # НЕ удаляем дубли.
    #
    # Одинаковый запрос может использовать разные
    # requested_artist / requested_title.
    # --------------------------------------------------------

    unique_stages = []

    for (
        stage_number,
        stage_name,
        query,
        requested_artist,
        requested_title
    ) in search_stages:

        query = re.sub(
            r"\s+",
            " ",
            str(query or "")
        ).strip()

        requested_artist = re.sub(
            r"\s+",
            " ",
            str(requested_artist or "")
        ).strip()

        requested_title = re.sub(
            r"\s+",
            " ",
            str(requested_title or "")
        ).strip()

        if not query:

            continue

        unique_stages.append(
            (
                stage_number,
                stage_name,
                query,
                requested_artist,
                requested_title
            )
        )

    # --------------------------------------------------------
    # client_id
    # --------------------------------------------------------

    client_id = (
        get_soundcloud_client_id()
    )

    if not client_id:

        print(
            "SoundCloud: "
            "client_id не получен."
        )

        return None

    print(
        "SoundCloud: client_id получен."
    )

    # --------------------------------------------------------
    # ПОЭТАПНЫЙ ПОИСК
    # --------------------------------------------------------

    for (
        stage_number,
        stage_name,
        query,
        requested_artist,
        requested_title
    ) in unique_stages:

        print()
        print(
            "-" * 60
        )

        print(
            "SoundCloud: ЭТАП "
            f"{stage_number}/4"
        )

        print(
            "SoundCloud: режим: "
            f"{stage_name}"
        )

        print(
            "SoundCloud: поисковый запрос: "
            f"{query}"
        )

        print(
            "SoundCloud: максимум результатов: "
            f"{SOUNDCLOUD_SEARCH_RESULTS}"
        )

        print(
            "-" * 60
        )

        try:

            collection = (
                fetch_soundcloud_results(
                    query,
                    client_id
                )
            )

        except Exception as error:

            print(
                "SoundCloud: ошибка запроса: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            continue

        if not isinstance(
            collection,
            list
        ):

            collection = []

        print(
            "SoundCloud: получено результатов: "
            f"{len(collection)}"
        )

        if not collection:

            print(
                "SoundCloud: на этом этапе "
                "результатов нет."
            )

            continue

        # ----------------------------------------------------
        # Оценка только текущего этапа
        # ----------------------------------------------------

        stage_candidates = []

        for candidate in collection:

            result = (
                evaluate_soundcloud_candidate(
                    candidate,
                    requested_artist,
                    requested_title,
                    duration
                )
            )

            if not result:

                continue

            result[
                "search_stage"
            ] = stage_number

            result[
                "search_query"
            ] = query

            stage_candidates.append(
                result
            )

        print(
            "SoundCloud: подходящих кандидатов "
            "на этом этапе: "
            f"{len(stage_candidates)}"
        )

        if not stage_candidates:

            print(
                "SoundCloud: подходящий кандидат "
                "не найден. Переход к следующему этапу."
            )

            continue

        # ----------------------------------------------------
        # Дубликаты внутри текущего этапа
        # ----------------------------------------------------

        unique = {}

        for item in stage_candidates:

            candidate = item[
                "candidate"
            ]

            candidate_id = (
                candidate.get("id")
            )

            if candidate_id is None:

                candidate_id = (
                    candidate.get(
                        "permalink_url"
                    )
                    or candidate.get(
                        "uri"
                    )
                    or candidate.get(
                        "title"
                    )
                )

            previous = unique.get(
                candidate_id
            )

            if (
                previous is None
                or item["score"]
                > previous["score"]
            ):

                unique[
                    candidate_id
                ] = item

        candidates = list(
            unique.values()
        )

        if not candidates:

            print(
                "SoundCloud: после удаления "
                "дубликатов кандидатов не осталось."
            )

            continue

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        best = candidates[0]

        candidate = best[
            "candidate"
        ]

        candidate_title = str(
            candidate.get("title")
            or ""
        ).strip()

        user = candidate.get(
            "user"
        )

        if isinstance(
            user,
            dict
        ):

            candidate_artist = str(
                user.get("username")
                or ""
            ).strip()

        else:

            candidate_artist = ""

        candidate_url = (
            candidate.get(
                "permalink_url"
            )
            or candidate.get(
                "uri"
            )
            or ""
        )

        if not candidate_url:

            print(
                "SoundCloud: у кандидата "
                "отсутствует URL."
            )

            continue

        print()
        print(
            "SoundCloud: КАНДИДАТ НАЙДЕН."
        )

        print(
            "SoundCloud: этап: "
            f"{stage_number}/4"
        )

        print(
            "SoundCloud: запрос: "
            f"{query}"
        )

        print(
            "SoundCloud: score: "
            f"{best['score']:.1f}"
        )

        print(
            "SoundCloud: название кандидата: "
            f"{candidate_title}"
        )

        print(
            "SoundCloud: исполнитель кандидата: "
            f"{candidate_artist}"
        )

        print(
            "SoundCloud: URL: "
            f"{candidate_url}"
        )

        print(
            "SoundCloud: используем результат "
            f"этапа {stage_number}."
        )

        # SOUNDCLOUD_NEXT_CANDIDATES_V4
        # Существующий scoring НЕ изменяется.
        # TOP 1 остаётся основным результатом.
        # Остальные кандидаты передаются downloader'у
        # в уже существующем порядке score.
        alternatives = []
        
        for alternative_item in candidates[1:5]:
            alternative_candidate = alternative_item["candidate"]
        
            alternative_title = str(
                alternative_candidate.get("title")
                or ""
            ).strip()
        
            alternative_user = alternative_candidate.get("user")
        
            if isinstance(alternative_user, dict):
                alternative_artist = str(
                    alternative_user.get("username")
                    or ""
                ).strip()
            else:
                alternative_artist = ""
        
            alternative_url = (
                alternative_candidate.get("permalink_url")
                or alternative_candidate.get("uri")
                or ""
            )
        
            if not alternative_url:
                continue
        
            alternatives.append({
                "url": alternative_url,
                "title": alternative_title,
                "artist": alternative_artist,
                "duration": alternative_candidate.get("duration"),
                "score": alternative_item["score"],
                "candidate": alternative_candidate,
                "search_stage": stage_number,
                "search_query": query,
                "exact_match": (
                    alternative_item["score"] >= 900
                    and (
                        alternative_item.get(
                            "title_ratio",
                            0
                        ) >= 1.0
                    )
                    and (
                        alternative_item.get(
                            "artist_ratio",
                            0
                        ) >= 1.0
                    )
                ),
            })
        
        return {
            "url": candidate_url,
            "title": candidate_title,
            "artist": candidate_artist,
            "duration": candidate.get(
                "duration"
            ),
            "score": best["score"],
            "candidate": candidate,
            "search_stage": stage_number,
            "search_query": query,

            # Признак очень точного совпадения.
            #
            # Для exact_match НЕ используются конкретные
            # имена исполнителей или названия треков.
            #
            # Проверяем:
            #   1. высокий score;
            #   2. точное совпадение названия;
            #   3. совпадение исполнителя.
            "exact_match": (
                best["score"] >= 900
                and (
                    best.get("title_ratio", 0)
                    >= 1.0
                )
                and (
                    best.get("artist_ratio", 0)
                    >= 1.0
                )
            ),
        "alternatives": alternatives,
        }

    # ========================================================
    # SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1
    # ========================================================
    #
    # Четыре основных этапа выше НЕ изменяются.
    #
    # Этот этап запускается только если обычный каскад
    # не дал подходящего кандидата.
    #
    # Причина:
    # SoundCloud Search API иногда не возвращает нужный
    # трек по запросу "исполнитель + название", даже когда
    # сам трек существует.
    #
    # Пример:
    #     пазнякс, OG Buda + блэкпинк
    #
    # При title-only поиске:
    #     блэкпинк
    #
    # SoundCloud может вернуть нужные загрузки.
    # ========================================================

    print()
    print(
        "-" * 60
    )

    print(
        "SoundCloud: FALLBACK TITLE-ONLY"
    )

    print(
        "SoundCloud: обычные 4 этапа "
        "не дали подходящего кандидата."
    )


    # ========================================================
    # TITLE-ONLY LOCAL HELPERS
    # ========================================================
    #
    # TITLE-ONLY fallback является самостоятельным последним
    # этапом поиска. Он не должен зависеть от helper-функций,
    # которых может не быть в текущем sources_soundcloud.py.
    # ========================================================

    def fallback_duration_is_reasonable(
        candidate_duration,
        requested_duration
    ):
        """
        Безопасная проверка длительности для TITLE-ONLY.

        Допускаются:
        - секунды;
        - миллисекунды;
        - None.

        Если одна из длительностей неизвестна, кандидат
        не отбрасывается только из-за отсутствия duration.
        """

        if (
            candidate_duration is None
            or requested_duration is None
        ):
            return True

        try:
            candidate_value = float(
                candidate_duration
            )

            requested_value = float(
                requested_duration
            )

        except (
            TypeError,
            ValueError
        ):
            return True

        if candidate_value > 1000:
            candidate_value /= 1000.0

        if requested_value > 1000:
            requested_value /= 1000.0

        if (
            candidate_value <= 0
            or requested_value <= 0
        ):
            return True

        difference = abs(
            candidate_value
            - requested_value
        )

        # Для TITLE-ONLY используем тот же разумный
        # диапазон, который применяется в основном
        # SoundCloud scoring: до 6 секунд.
        return difference <= 6.0


    def fallback_get_candidate_artist(
        candidate
    ):
        """
        Безопасно получает исполнителя SoundCloud-кандидата.
        """

        if not isinstance(
            candidate,
            dict
        ):
            return ""

        direct_artist = str(
            candidate.get("artist")
            or candidate.get("publisher")
            or candidate.get("metadata_artist")
            or ""
        ).strip()

        if direct_artist:
            return direct_artist

        user = candidate.get(
            "user"
        )

        if isinstance(
            user,
            dict
        ):
            return str(
                user.get("username")
                or user.get("permalink")
                or ""
            ).strip()

        return ""


    def fallback_get_candidate_url(
        candidate
    ):
        """
        Безопасно получает URL SoundCloud-кандидата.
        """

        if not isinstance(
            candidate,
            dict
        ):
            return ""

        return str(
            candidate.get("permalink_url")
            or candidate.get("uri")
            or candidate.get("url")
            or ""
        ).strip()


    # ========================================================
    # END TITLE-ONLY LOCAL HELPERS
    # ========================================================

    title_fallback_queries = []

    # Основной вариант: очищенное название без feat.
    if cleaned_base_title:
        title_fallback_queries.append(
            cleaned_base_title
        )

    # Второй вариант: исходное название без feat.
    if (
        original_base_title
        and original_base_title
        not in title_fallback_queries
    ):
        title_fallback_queries.append(
            original_base_title
        )

    # На случай слишком агрессивной очистки.
    if (
        cleaned_query_title
        and cleaned_query_title
        not in title_fallback_queries
    ):
        title_fallback_queries.append(
            cleaned_query_title
        )

    title_fallback_candidates = []

    for title_query in title_fallback_queries:

        print()
        print(
            "SoundCloud: TITLE-ONLY запрос: "
            f"{title_query}"
        )

        print(
            "SoundCloud: максимум результатов: "
            f"{SOUNDCLOUD_SEARCH_RESULTS}"
        )

        try:

            title_collection = (
                fetch_soundcloud_results(
                    title_query,
                    client_id
                )
            )

        except Exception as error:

            print(
                "SoundCloud: TITLE-ONLY ошибка запроса: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            continue

        if not isinstance(
            title_collection,
            list
        ):
            title_collection = []

        print(
            "SoundCloud: TITLE-ONLY получено "
            f"результатов: {len(title_collection)}"
        )

        for title_candidate in title_collection:

            candidate_title = str(
                title_candidate.get("title")
                or ""
            ).strip()

            candidate_url = (
                title_candidate.get(
                    "permalink_url"
                )
                or title_candidate.get(
                    "uri"
                )
                or ""
            )

            if not candidate_title or not candidate_url:
                continue

            # ------------------------------------------------
            # TITLE-ONLY similarity
            #
            # Отдельная глобальная title_similarity()
            # в sources_soundcloud.py отсутствует.
            #
            # Поэтому TITLE-ONLY использует локальный
            # безопасный расчёт similarity.
            # ------------------------------------------------

            def fallback_norm(value):
                value = str(
                    value or ""
                ).lower()

                value = re.sub(
                    r"https?://\\S+",
                    " ",
                    value,
                    flags=re.IGNORECASE
                )

                value = value.replace(
                    "&",
                    " and "
                )

                value = re.sub(
                    r"[^\\w\\sа-яА-ЯёЁ]",
                    " ",
                    value,
                    flags=re.IGNORECASE
                )

                value = re.sub(
                    r"\\s+",
                    " ",
                    value
                ).strip()

                return value


            def fallback_title_similarity(
                left,
                right
            ):
                left_norm = re.sub(
                    r"\s+",
                    " ",
                    fallback_norm(left)
                ).strip()

                right_norm = re.sub(
                    r"\s+",
                    " ",
                    fallback_norm(right)
                ).strip()

                if not left_norm or not right_norm:
                    return 0.0

                if left_norm == right_norm:
                    return 1.0

                left_tokens = set(
                    left_norm.split()
                )

                right_tokens = set(
                    right_norm.split()
                )

                if not left_tokens or not right_tokens:
                    return 0.0

                intersection = (
                    left_tokens & right_tokens
                )

                if not intersection:
                    return 0.0

                precision = (
                    len(intersection)
                    / len(left_tokens)
                )

                recall = (
                    len(intersection)
                    / len(right_tokens)
                )

                if (
                    precision + recall
                    == 0
                ):
                    return 0.0

                return (
                    2.0
                    * precision
                    * recall
                    / (
                        precision
                        + recall
                    )
                )

            candidate_title_ratio = (
                fallback_title_similarity(
                    candidate_title,
                    original_query_title
                )
            )

            candidate_base_title_ratio = (
                fallback_title_similarity(
                    candidate_title,
                    cleaned_base_title
                )
                if cleaned_base_title
                else 0.0
            )

            title_ratio = max(
                candidate_title_ratio,
                candidate_base_title_ratio
            )

            # ------------------------------------------------
            # Сначала пробуем существующий scoring.
            # ------------------------------------------------

            evaluated = None

            try:

                evaluated = (
                    evaluate_soundcloud_candidate(
                        title_candidate,
                        requested_artist,
                        requested_title,
                        duration
                    )
                )

            except Exception as error:

                print(
                    "SoundCloud: TITLE-ONLY evaluator "
                    "ошибка: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            if evaluated:

                evaluated["search_stage"] = 5
                evaluated["search_query"] = title_query
                evaluated["title_only_fallback"] = True

                title_fallback_candidates.append(
                    evaluated
                )

                continue

            # ------------------------------------------------
            # Если штатный evaluator отклонил результат,
            # используем осторожный title-only критерий.
            #
            # Важное условие:
            # название должно быть действительно похоже.
            # ------------------------------------------------

            if title_ratio < 0.82:
                continue

            if not fallback_duration_is_reasonable(
                title_candidate.get("duration"),
                duration
            ):
                continue

            candidate_artist = (
                fallback_get_candidate_artist(
                    title_candidate
                )
            )

            # Score специально ниже exact/high-confidence
            # совпадений обычного evaluator.
            #
            # Это fallback, а не замена штатному scoring.
            fallback_score = (
                500.0
                + title_ratio * 100.0
            )

            title_fallback_candidates.append({
                "candidate": title_candidate,
                "score": fallback_score,
                "title_ratio": title_ratio,
                "artist_ratio": 0.0,
                "search_stage": 5,
                "search_query": title_query,
                "title_only_fallback": True,
            })

    # --------------------------------------------------------
    # Удаляем дубликаты.
    # --------------------------------------------------------

    fallback_unique = {}

    for item in title_fallback_candidates:

        candidate = item.get(
            "candidate",
            {}
        )

        candidate_id = (
            candidate.get("id")
            or candidate.get("permalink_url")
            or candidate.get("uri")
            or candidate.get("title")
        )

        previous = fallback_unique.get(
            candidate_id
        )

        if (
            previous is None
            or item["score"]
            > previous["score"]
        ):
            fallback_unique[
                candidate_id
            ] = item

    title_fallback_candidates = list(
        fallback_unique.values()
    )

    title_fallback_candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print()
    print(
        "SoundCloud: TITLE-ONLY подходящих "
        "кандидатов: "
        f"{len(title_fallback_candidates)}"
    )

    if title_fallback_candidates:

        best = title_fallback_candidates[0]

        candidate = best.get(
            "candidate",
            {}
        )

        candidate_title = str(
            candidate.get("title")
            or ""
        ).strip()

        candidate_artist = (
            fallback_get_candidate_artist(
                candidate
            )
        )

        candidate_url = (
            fallback_get_candidate_url(
                candidate
            )
        )

        if candidate_url:

            print()
            print(
                "SoundCloud: TITLE-ONLY "
                "КАНДИДАТ НАЙДЕН."
            )

            print(
                "SoundCloud: этап: 5/5"
            )

            print(
                "SoundCloud: запрос: "
                f"{best.get('search_query', '')}"
            )

            print(
                "SoundCloud: score: "
                f"{best['score']:.1f}"
            )

            print(
                "SoundCloud: название кандидата: "
                f"{candidate_title}"
            )

            print(
                "SoundCloud: исполнитель кандидата: "
                f"{candidate_artist}"
            )

            print(
                "SoundCloud: URL: "
                f"{candidate_url}"
            )

            print(
                "SoundCloud: используем "
                "TITLE-ONLY fallback."
            )

            alternatives = []

            for alternative_item in (
                title_fallback_candidates[1:5]
            ):

                alternative_candidate = (
                    alternative_item.get(
                        "candidate",
                        {}
                    )
                )

                alternative_url = (
                    fallback_get_candidate_url(
                        alternative_candidate
                    )
                )

                if not alternative_url:
                    continue

                alternative_title = str(
                    alternative_candidate.get(
                        "title"
                    )
                    or ""
                ).strip()

                alternative_artist = (
                    fallback_get_candidate_artist(
                        alternative_candidate
                    )
                )

                alternative_title_ratio = (
                    alternative_item.get(
                        "title_ratio",
                        0.0
                    )
                )

                alternatives.append({
                    "url": alternative_url,
                    "title": alternative_title,
                    "artist": alternative_artist,
                    "duration": alternative_candidate.get(
                        "duration"
                    ),
                    "score": alternative_item[
                        "score"
                    ],
                    "candidate": alternative_candidate,
                    "search_stage": 5,
                    "search_query": alternative_item.get(
                        "search_query",
                        ""
                    ),
                    "exact_match": (
                        alternative_title_ratio >= 0.98
                    ),
                    "title_only_fallback": True,
                })

            return {
                "url": candidate_url,
                "title": candidate_title,
                "artist": candidate_artist,
                "duration": candidate.get(
                    "duration"
                ),
                "score": best["score"],
                "candidate": candidate,
                "search_stage": 5,
                "search_query": best.get(
                    "search_query",
                    ""
                ),
                "title_only_fallback": True,
                "exact_match": (
                    best.get(
                        "title_ratio",
                        0.0
                    ) >= 0.98
                    and best.get(
                        "artist_ratio",
                        0.0
                    ) >= 1.0
                ),
                "alternatives": alternatives,
            }

    print()
    print(
        "SoundCloud: TITLE-ONLY fallback "
        "не дал подходящего кандидата."
    )

    # ========================================================
    # END SOUNDCLOUD_TITLE_ONLY_FALLBACK_V1
    # ========================================================

    print()

    print(
        "SoundCloud: ни один из "
        "4 основных этапов + TITLE-ONLY "
        "не дал подходящего трека."
    )

    return None

def soundcloud_is_preview_only(
    track_data
):
    """
    Проверяет, предоставляет ли SoundCloud
    только preview вместо полного трека.

    Возвращает:

        True
            если доступен только preview;

        False
            если обнаружен полноценный поток;

        None
            если определить состояние невозможно.

    Важно:

    Эта функция НЕ определяет, подходит ли трек
    по названию или исполнителю.

    Она отвечает только за доступность полного
    аудиопотока.
    """

    if not isinstance(
        track_data,
        dict
    ):
        return None

    policy = str(
        track_data.get(
            "policy"
        )
        or ""
    ).strip().upper()

    access = str(
        track_data.get(
            "access"
        )
        or ""
    ).strip().lower()

    duration = track_data.get(
        "duration"
    )

    full_duration = track_data.get(
        "full_duration"
    )

    media = track_data.get(
        "media"
    )

    if not isinstance(
        media,
        dict
    ):
        media = {}

    transcodings = media.get(
        "transcodings"
    )

    if not isinstance(
        transcodings,
        list
    ):
        transcodings = []

    valid_transcodings = []

    for transcoding in transcodings:

        if not isinstance(
            transcoding,
            dict
        ):
            continue

        url = str(
            transcoding.get(
                "url"
            )
            or ""
        )

        if not url:
            continue

        valid_transcodings.append(
            transcoding
        )

    # --------------------------------------------------------
    # Самый надёжный признак:
    #
    # SoundCloud сообщает SNIP и все transcoding
    # помечены snipped=True.
    # --------------------------------------------------------

    if (
        policy == "SNIP"
        and valid_transcodings
    ):

        all_snipped = all(
            item.get(
                "snipped"
            ) is True
            for item in valid_transcodings
        )

        if all_snipped:

            print(
                "SoundCloud: полный трек "
                "недоступен."
            )

            print(
                "SoundCloud: SoundCloud "
                "предоставил только preview."
            )

            if (
                duration is not None
                and full_duration is not None
            ):
                try:

                    preview_seconds = (
                        float(duration)
                        / 1000.0
                    )

                    full_seconds = (
                        float(full_duration)
                        / 1000.0
                    )

                    print(
                        "SoundCloud: длительность "
                        "preview: "
                        f"{preview_seconds:.3f} сек."
                    )

                    print(
                        "SoundCloud: полная "
                        "длительность: "
                        f"{full_seconds:.3f} сек."
                    )

                except Exception:
                    pass

            return True

    # --------------------------------------------------------
    # access=preview
    #
    # Используем только если одновременно нет
    # полноценного transcoding.
    # --------------------------------------------------------

    if access == "preview":

        has_full = False

        for transcoding in valid_transcodings:

            if transcoding.get(
                "snipped"
            ) is not True:

                has_full = True
                break

        if not has_full:

            print(
                "SoundCloud: полный трек "
                "недоступен."
            )

            print(
                "SoundCloud: доступен только "
                "preview."
            )

            return True

    # --------------------------------------------------------
    # Проверяем transcoding непосредственно.
    #
    # Это позволяет обнаруживать preview даже если
    # поле policy отсутствует.
    # --------------------------------------------------------

    if valid_transcodings:

        has_full = False

        for transcoding in valid_transcodings:

            if transcoding.get(
                "snipped"
            ) is True:

                continue

            url = str(
                transcoding.get(
                    "url"
                )
                or ""
            ).lower()

            if (
                "/preview/" not in url
                and "/preview" not in url
            ):

                has_full = True
                break

        if not has_full:

            all_preview = True

            for transcoding in valid_transcodings:

                url = str(
                    transcoding.get(
                        "url"
                    )
                    or ""
                ).lower()

                if (
                    transcoding.get(
                        "snipped"
                    ) is not True
                    and "/preview/" not in url
                    and "/preview" not in url
                ):
                    all_preview = False
                    break

            if all_preview:

                print(
                    "SoundCloud: все доступные "
                    "transcoding являются preview."
                )

                return True

    # --------------------------------------------------------
    # Явного признака preview-only нет.
    # --------------------------------------------------------

    return False




def get_soundcloud_track_info(
    soundcloud_url
):
    """
    Получает полный JSON трека SoundCloud
    через API resolve.

    Используется только для определения
    доступности полной версии / preview.
    """

    client_id = (
        get_soundcloud_client_id()
    )

    if not client_id:
        return None

    try:

        response = requests.get(
            "https://api-v2.soundcloud.com/resolve",
            params={
                "url": soundcloud_url,
                "client_id": client_id
            },
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_SEARCH_TIMEOUT
        )

    except Exception:

        return None

    if response.status_code != 200:
        return None

    try:

        data = response.json()

    except Exception:

        return None

    if not isinstance(
        data,
        dict
    ):

        return None

    return data




def is_soundcloud_confirmed_preview(
    track_info
):
    """
    Возвращает True только если SoundCloud
    явно сообщает, что доступно только
    укороченное preview.

    Условия:

    policy == SNIP

    duration < full_duration

    существуют transcodings

    ВСЕ transcoding имеют:
        snipped == True
    """

    if not isinstance(
        track_info,
        dict
    ):
        return False

    policy = str(
        track_info.get("policy")
        or ""
    ).upper()

    if policy != "SNIP":
        return False

    duration = track_info.get(
        "duration"
    )

    full_duration = track_info.get(
        "full_duration"
    )

    try:

        duration = float(
            duration
        )

        full_duration = float(
            full_duration
        )

    except (
        TypeError,
        ValueError
    ):

        return False

    if duration <= 0:
        return False

    if full_duration <= duration:
        return False

    transcodings = []

    media = track_info.get(
        "media"
    )

    if isinstance(
        media,
        dict
    ):

        transcodings = media.get(
            "transcodings",
            []
        )

    if not isinstance(
        transcodings,
        list
    ):
        return False

    if not transcodings:
        return False

    all_snipped = all(
        isinstance(
            transcoding,
            dict
        )
        and transcoding.get(
            "snipped"
        ) is True
        for transcoding
        in transcodings
    )

    if not all_snipped:
        return False

    return True


def get_soundcloud_full_stream_url(
    soundcloud_url
):
    """
    Пытается получить полноценный SoundCloud
    stream URL напрямую через API.

    ВАЖНО:
    - preview URL специально отбрасываются;
    - существующая yt-dlp загрузка остаётся
      резервным способом;
    - функция ничего не пытается
      "растягивать" или подменять;
    - если SoundCloud действительно отдаёт
      только preview, возвращается None.
    """

    if not soundcloud_url:
        return None

    client_id = (
        get_soundcloud_client_id()
    )

    if not client_id:
        print(
            "SoundCloud: client_id "
            "не получен для прямого stream API."
        )

        return None

    try:
        # ----------------------------------------------------
        # 1. Resolve URL -> полная информация о треке
        # ----------------------------------------------------

        resolve_response = requests.get(
            "https://api-v2.soundcloud.com/resolve",
            params={
                "url": soundcloud_url,
                "client_id": client_id,
            },
            headers=SOUNDCLOUD_HEADERS,
            timeout=SOUNDCLOUD_SEARCH_TIMEOUT
        )

        print(
            "SoundCloud API: resolve HTTP-код: "
            f"{resolve_response.status_code}"
        )

        if resolve_response.status_code != 200:
            return None

        track_info = (
            resolve_response.json()
        )

        if not isinstance(
            track_info,
            dict
        ):
            return None

        track_id = (
            track_info.get("id")
        )

        if not track_id:
            print(
                "SoundCloud API: "
                "track_id не найден."
            )

            return None

        print(
            "SoundCloud API: "
            f"track_id: {track_id}"
        )

        # ----------------------------------------------------
        # 2. Сначала пытаемся получить
        #    streams endpoint.
        # ----------------------------------------------------

        streams_urls = [
            (
                "https://api-v2.soundcloud.com/"
                f"tracks/{track_id}/streams"
            ),
            (
                "https://api.soundcloud.com/"
                f"tracks/{track_id}/streams"
            ),
        ]

        for streams_url in streams_urls:

            try:

                response = requests.get(
                    streams_url,
                    params={
                        "client_id": client_id,
                    },
                    headers=SOUNDCLOUD_HEADERS,
                    timeout=SOUNDCLOUD_SEARCH_TIMEOUT
                )

            except Exception:
                continue

            print(
                "SoundCloud API: streams HTTP-код: "
                f"{response.status_code}"
            )

            if response.status_code != 200:
                continue

            try:
                streams_data = response.json()
            except Exception:
                continue

            if not isinstance(
                streams_data,
                dict
            ):
                continue

            # ------------------------------------------------
            # Возможные ключи:
            #
            # http_mp3
            # hls_mp3
            # http_aac
            # hls_aac
            # ------------------------------------------------

            preferred_keys = (
                "http_mp3",
                "hls_mp3",
                "http_aac",
                "hls_aac",
                "http_opus",
                "hls_opus",
            )

            for key in preferred_keys:

                stream_url = (
                    streams_data.get(key)
                )

                if not isinstance(
                    stream_url,
                    str
                ):
                    continue

                if not stream_url:
                    continue

                lowered = (
                    stream_url.lower()
                )

                if "/preview/" in lowered:
                    print(
                        "SoundCloud API: "
                        f"{key} является preview, "
                        "пропускаем."
                    )

                    continue

                print(
                    "SoundCloud API: "
                    f"найден полноценный stream: "
                    f"{key}"
                )

                return stream_url

        # ----------------------------------------------------
        # 3. Новый API: media.transcodings
        #
        # Это тот же механизм, который использует
        # современный yt-dlp extractor SoundCloud.
        # ----------------------------------------------------

        transcodings = (
            track_info
            .get("media", {})
            .get("transcodings", [])
        )

        if not isinstance(
            transcodings,
            list
        ):
            transcodings = []

        print(
            "SoundCloud API: "
            "transcodings: "
            f"{len(transcodings)}"
        )

        # Сначала ищем MP3, затем AAC.
        preferred_protocols = (
            "progressive",
            "http",
            "hls",
        )

        ordered = []

        for transcoding in transcodings:

            if not isinstance(
                transcoding,
                dict
            ):
                continue

            transcoding_url = (
                transcoding.get("url")
            )

            if not transcoding_url:
                continue

            preset = str(
                transcoding.get("preset")
                or ""
            ).lower()

            format_data = (
                transcoding.get("format")
            )

            if not isinstance(
                format_data,
                dict
            ):
                format_data = {}

            protocol = str(
                format_data.get(
                    "protocol"
                )
                or ""
            ).lower()

            # ------------------------------------------------
            # ЖЁСТКО исключаем preview.
            # ------------------------------------------------

            if transcoding.get(
                "snipped"
            ):
                print(
                    "SoundCloud API: "
                    f"preview transcoding: "
                    f"{preset}"
                )

                continue

            if "/preview/" in str(
                transcoding_url
            ).lower():
                print(
                    "SoundCloud API: "
                    f"URL preview: "
                    f"{preset}"
                )

                continue

            if "preview" in preset:
                print(
                    "SoundCloud API: "
                    f"preset preview: "
                    f"{preset}"
                )

                continue

            # Приоритет:
            # mp3 > aac > opus
            if "mp3" in preset:
                quality = 0
            elif "aac" in preset:
                quality = 1
            elif "opus" in preset:
                quality = 2
            else:
                quality = 3

            # progressive/http предпочтительнее HLS.
            protocol_quality = (
                0
                if protocol in (
                    "progressive",
                    "http"
                )
                else 1
            )

            ordered.append(
                (
                    quality,
                    protocol_quality,
                    transcoding
                )
            )

        ordered.sort(
            key=lambda item: (
                item[0],
                item[1]
            )
        )

        for (
            _quality,
            _protocol_quality,
            transcoding
        ) in ordered:

            transcoding_url = (
                transcoding.get("url")
            )

            preset = str(
                transcoding.get("preset")
                or ""
            )

            print(
                "SoundCloud API: "
                "попытка получить stream "
                f"из transcoding: {preset}"
            )

            try:

                stream_response = (
                    requests.get(
                        transcoding_url,
                        params={
                            "client_id":
                                client_id
                        },
                        headers=(
                            SOUNDCLOUD_HEADERS
                        ),
                        timeout=(
                            SOUNDCLOUD_SEARCH_TIMEOUT
                        )
                    )
                )

            except Exception as error:

                print(
                    "SoundCloud API: "
                    "ошибка transcoding: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                continue

            print(
                "SoundCloud API: "
                "transcoding HTTP-код: "
                f"{stream_response.status_code}"
            )

            if (
                stream_response.status_code
                != 200
            ):
                continue

            try:
                stream_data = (
                    stream_response.json()
                )
            except Exception:
                continue

            if not isinstance(
                stream_data,
                dict
            ):
                continue

            stream_url = (
                stream_data.get("url")
            )

            if not isinstance(
                stream_url,
                str
            ):
                continue

            if not stream_url:
                continue

            lowered = (
                stream_url.lower()
            )

            if "/preview/" in lowered:
                print(
                    "SoundCloud API: "
                    "полученный stream "
                    "всё ещё preview."
                )

                continue

            print(
                "SoundCloud API: "
                "ПОЛНОЦЕННЫЙ STREAM ПОЛУЧЕН."
            )

            print(
                "SoundCloud API: "
                f"preset: {preset}"
            )

            return stream_url

    except Exception as error:

        print(
            "SoundCloud API: "
            "ошибка получения полного "
            "stream: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    print(
        "SoundCloud API: "
        "полноценный stream не найден."
    )

    return None

def download_from_soundcloud(
    soundcloud_url,
    filepath,
    target_duration=None,
    exact_match=False
):
    """
    Скачивает трек с SoundCloud.

    Сначала пытается получить полноценный
    stream напрямую через SoundCloud API.

    Если API не дал полноценный stream,
    используется обычный yt-dlp.

    Preview stream никогда не принимается
    как успешный результат: существующая
    проверка ffprobe остаётся обязательной.
    """

    if not soundcloud_url:
        return False

    if not filepath:
        return False

    print(
        "Скачивание с SoundCloud..."
    )

    original_filepath = filepath

    filepath_directory = os.path.dirname(
        os.path.abspath(filepath)
    )

    filepath_name = os.path.basename(
        filepath
    )

    filepath_name = (
        str(filepath_name)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )

    filepath_name = re.sub(
        r"[\x00-\x1F\x7F]",
        " ",
        filepath_name
    )

    filepath_name = re.sub(
        r'[<>:"/\\|?*]',
        "",
        filepath_name
    )

    filepath_name = re.sub(
        r"\s+",
        " ",
        filepath_name
    ).strip()

    filepath_name = filepath_name.rstrip(
        " ."
    )

    if not filepath_name:
        filepath_name = (
            "soundcloud_track.mp3"
        )

    filepath = os.path.join(
        filepath_directory,
        filepath_name
    )

    if filepath != original_filepath:
        print(
            "SoundCloud: итоговое имя файла "
            "очищено от недопустимых символов."
        )

        print(
            "SoundCloud: новое имя:"
        )

        print(
            os.path.basename(filepath)
        )

    output_dir = os.path.dirname(
        os.path.abspath(filepath)
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    base_without_ext = os.path.join(
        output_dir,
        ".soundcloud_temp_download"
    )

    temp_template = (
        base_without_ext
        + ".soundcloud_temp.%(ext)s"
    )

    def cleanup_temp():

        directory = os.path.dirname(
            os.path.abspath(filepath)
        )

        if not os.path.isdir(
            directory
        ):
            return

        prefix = os.path.basename(
            base_without_ext
            + ".soundcloud_temp."
        )

        for name in os.listdir(
            directory
        ):

            if not name.startswith(
                prefix
            ):
                continue

            path = os.path.join(
                directory,
                name
            )

            try:

                if os.path.isfile(
                    path
                ):
                    os.remove(path)

            except Exception:
                pass

    def find_temp_file():

        directory = os.path.dirname(
            os.path.abspath(filepath)
        )

        prefix = os.path.basename(
            base_without_ext
            + ".soundcloud_temp."
        )

        if not os.path.isdir(
            directory
        ):
            return None

        candidates = []

        for name in os.listdir(
            directory
        ):

            if not name.startswith(
                prefix
            ):
                continue

            path = os.path.join(
                directory,
                name
            )

            if not os.path.isfile(
                path
            ):
                continue

            try:

                size = os.path.getsize(
                    path
                )

            except Exception:
                continue

            if size < MIN_FILE_SIZE:
                continue

            candidates.append(
                path
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda x:
                os.path.getsize(x),
            reverse=True
        )

        return candidates[0]

    def run_ytdlp(
        input_url,
        format_spec
    ):

        command = [
            YTDLP,
            "--no-playlist",
            "--no-warnings",
            "--newline",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            "--socket-timeout",
            str(
                SOUNDCLOUD_DOWNLOAD_TIMEOUT
            ),
            "--format",
            format_spec,
            "--output",
            temp_template,
            input_url,
        ]

        try:

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=(
                    SOUNDCLOUD_DOWNLOAD_TIMEOUT
                    + 30
                )
            )

        except subprocess.TimeoutExpired:

            print(
                "SoundCloud: "
                "превышено время ожидания "
                "загрузки."
            )

            return False

        except Exception as error:

            print(
                "SoundCloud: "
                f"ошибка запуска yt-dlp: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return False

        output = (
            (process.stdout or "")
            + "\n"
            + (process.stderr or "")
        ).strip()

        if process.returncode != 0:

            if output:

                print(
                    "SoundCloud yt-dlp: "
                    + output[-1200:]
                )

            return False

        return True

    def convert_to_mp3(
        source
    ):

        if not source:
            return False

        if not os.path.isfile(
            source
        ):
            return False

        command = [
            FFMPEG,
            "-y",
            "-i",
            source,
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            filepath,
        ]

        try:

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120
            )

        except Exception as error:

            print(
                "SoundCloud: "
                f"ошибка конвертации: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return False

        if process.returncode != 0:

            error_text = (
                process.stderr
                or process.stdout
                or ""
            )

            print(
                "SoundCloud FFmpeg: "
                + error_text[-1200:]
            )

            return False

        if not os.path.isfile(
            filepath
        ):
            return False

        try:

            if os.path.getsize(
                filepath
            ) < MIN_FILE_SIZE:
                return False

        except Exception:
            return False

        return True

    def validate_duration():

        if (
            target_duration is None
            or not os.path.isfile(filepath)
        ):
            return True

        try:

            command = [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default="
                "noprint_wrappers=1:"
                "nokey=1",
                filepath,
            ]

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )

            if process.returncode != 0:
                return True

            actual_duration = float(
                process.stdout.strip()
            )

            requested_duration = float(
                target_duration
            )

            difference = abs(
                actual_duration
                - requested_duration
            )

            duration_tolerance = (
                EXACT_MATCH_TOLERANCE
                if exact_match
                else SOUNDCLOUD_DURATION_TOLERANCE
            )

            if difference > duration_tolerance:

                print(
                    "SoundCloud: "
                    f"длительность отличается "
                    f"на {difference:.1f} сек."
                )

                print(
                    "SoundCloud: допустимый предел: "
                    f"{duration_tolerance:.1f} сек."
                )

                return False

            if (
                exact_match
                and difference
                > SOUNDCLOUD_DURATION_TOLERANCE
            ):

                print(
                    "SoundCloud: точный кандидат "
                    "принят с расширенным допуском "
                    f"({difference:.1f} сек. из "
                    f"{duration_tolerance:.1f} сек.)."
                )

        except Exception:
            return True

        return True

    cleanup_temp()

    # ========================================================
    # ПОПЫТКА 1:
    # прямой полноценный stream SoundCloud API
    # ========================================================

    print(
        "SoundCloud: попытка получить "
        "полноценный stream через API..."
    )

    full_stream_url = (
        get_soundcloud_full_stream_url(
            soundcloud_url
        )
    )

    if full_stream_url:

        print(
            "SoundCloud: полноценный stream "
            "получен через API."
        )

        print(
            "SoundCloud: скачивание "
            "полноценного stream..."
        )

        # Для прямого HTTP MP3 подходит best.
        # Для HLS/AAC yt-dlp также сможет
        # обработать доступный URL.
        if run_ytdlp(
            full_stream_url,
            "best"
        ):

            temp_file = (
                find_temp_file()
            )

            if temp_file:

                extension = (
                    os.path.splitext(
                        temp_file
                    )[1].lower()
                )

                if extension == ".mp3":

                    try:

                        if os.path.exists(
                            filepath
                        ):
                            os.remove(
                                filepath
                            )

                        shutil.move(
                            temp_file,
                            filepath
                        )

                    except Exception:
                        cleanup_temp()

                else:

                    if not convert_to_mp3(
                        temp_file
                    ):

                        cleanup_temp()

                    else:

                        try:
                            os.remove(
                                temp_file
                            )
                        except Exception:
                            pass

                if os.path.isfile(
                    filepath
                ):

                    if validate_duration():

                        cleanup_temp()

                        print(
                            "SoundCloud: "
                            "полноценный stream "
                            "успешно скачан."
                        )

                        return True

                    print(
                        "SoundCloud: "
                        "полученный stream "
                        "не прошёл проверку "
                        "длительности."
                    )

                    try:

                        os.remove(
                            filepath
                        )

                    except Exception:
                        pass

                    cleanup_temp()

        else:

            cleanup_temp()

    else:

        print(
            "SoundCloud: полноценный stream "
            "через API не получен."
        )

        # ========================================================
        # SOUNDCLOUD PREVIEW GATE
        #
        # Если API явно сообщает, что трек имеет
        # policy=SNIP и все доступные transcoding
        # являются snipped=True, НЕ запускаем yt-dlp.
        #
        # Это важно: 30-секундное preview не должно
        # скачиваться только для того, чтобы потом
        # ffprobe обнаружил неправильную длительность.
        # ========================================================
        try:
            preview_track_info = (
                get_soundcloud_track_info(
                    soundcloud_url
                )
            )
        except Exception:
            preview_track_info = None

        if is_soundcloud_confirmed_preview(
            preview_track_info
        ):
            preview_duration = (
                preview_track_info.get(
                    "duration"
                )
            )
            full_duration = (
                preview_track_info.get(
                    "full_duration"
                )
            )

            print(
                "SoundCloud: трек доступен "
                "только как preview."
            )

            print(
                "SoundCloud: длительность preview: "
                f"{float(preview_duration) / 1000.0:.1f} сек."
            )

            print(
                "SoundCloud: полная длительность: "
                f"{float(full_duration) / 1000.0:.1f} сек."
            )

            print(
                "SoundCloud: полная версия "
                "недоступна для скачивания через API."
            )

            print(
                "SoundCloud: yt-dlp не запускается "
                "для preview."
            )

            return False


    # ========================================================
    # ПОПЫТКА 2:
    # обычный yt-dlp.
    #
    # Это сохраняет прежнее поведение
    # для Gizzaru и остальных рабочих
    # SoundCloud-треков.
    # ========================================================

    format_attempts = (
        "bestaudio/best",
        "best",
    )

    for format_spec in format_attempts:

        print(
            "SoundCloud: попытка загрузки "
            f"({format_spec})..."
        )

        if not run_ytdlp(
            soundcloud_url,
            format_spec
        ):

            cleanup_temp()
            continue

        temp_file = find_temp_file()

        if not temp_file:

            cleanup_temp()
            continue

        extension = (
            os.path.splitext(
                temp_file
            )[1].lower()
        )

        if extension == ".mp3":

            try:

                if os.path.exists(
                    filepath
                ):
                    os.remove(
                        filepath
                    )

                shutil.move(
                    temp_file,
                    filepath
                )

            except Exception:

                cleanup_temp()
                continue

        else:

            if not convert_to_mp3(
                temp_file
            ):

                cleanup_temp()
                continue

            try:
                os.remove(
                    temp_file
                )
            except Exception:
                pass

        if not os.path.isfile(
            filepath
        ):

            cleanup_temp()
            continue

        try:

            if os.path.getsize(
                filepath
            ) < MIN_FILE_SIZE:

                cleanup_temp()
                continue

        except Exception:

            cleanup_temp()
            continue

        if not validate_duration():

            try:
                os.remove(
                    filepath
                )
            except Exception:
                pass

            cleanup_temp()
            continue

        cleanup_temp()

        print(
            "SoundCloud: "
            "загрузка успешно завершена."
        )

        return True

    cleanup_temp()

    print(
        "SoundCloud: "
        "не удалось получить аудиопоток."
    )

    return False


def clean_soundcloud_text(text):
    """
    Удаляет только служебные модификаторы, не являющиеся
    основной частью названия трека.

    Пример:
        Artist - Track (Prod by XXX) [Sped Up]
        ->
        Artist - Track
    """
    text = html.unescape(str(text or ""))
    text = unquote(text)

    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("_", " ")

    # Удаляем конструкции produced by / prod by с последующим именем.
    text = re.sub(
        r"\b(?:prod(?:uced)?\s*by)\b[\s:.-]*"
        r"[^()\[\]{}|/,;]+",
        " ",
        text,
        flags=re.I
    )

    # Удаляем распространённые модификаторы внутри скобок/квадратных скобок.
    modifier_pattern = (
        r"\b(?:remix|slowed|slowed\s*\+\s*reverb|"
        r"sped\s*up|speed\s*up|speedup|nightcore|phonk|"
        r"edit|version|mix|extended(?:\s+mix)?|"
        r"remastered|remaster|rework|bootleg|flip|mashup|"
        r"live|acoustic|instrumental|club|hardstyle|bass)\b"
    )

    for _ in range(3):
        text = re.sub(
            rf"[\(\[\{{][^()\[\]{{}}]*?{modifier_pattern}"
            rf"[^()\[\]{{}}]*?[\)\]\}}]",
            " ",
            text,
            flags=re.I
        )

    # После удаления содержимого могут остаться пустые скобки.
    text = re.sub(r"\(\s*\)|\[\s*\]|\{\s*\}", " ", text)

    # Удаляем одиночные служебные слова, если они остались вне скобок.
    text = re.sub(
        modifier_pattern,
        " ",
        text,
        flags=re.I
    )

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[-:|]+\s*", " ", text)

    return normalize(text)


def soundcloud_query_variants(artist, title):
    """
    Возвращает каскад поисковых запросов:

    1. artist + original title
    2. artist + cleaned title
    3. cleaned title
    4. flexible words
    """
    original_artist = normalize(artist)
    original_title = normalize(title)

    cleaned_artist = clean_soundcloud_text(artist)
    cleaned_title = clean_soundcloud_text(title)

    variants = []

    def add(value):
        value = re.sub(r"\s+", " ", value or "").strip()
        if value and value not in variants:
            variants.append(value)

    # 1. Строго.
    add(f"{original_artist} {original_title}")

    # 2. Исполнитель + очищенное название.
    add(f"{original_artist} {cleaned_title}")

    # Дополнительный вариант с очищенным исполнителем.
    add(f"{cleaned_artist} {cleaned_title}")

    # 3. Только очищенное название.
    add(cleaned_title)

    # 4. Гибкий поиск.
    artist_words = [
        word for word in normalize_words(cleaned_artist)
        if len(word) >= 2
    ]
    title_words = [
        word for word in normalize_words(cleaned_title)
        if len(word) >= 2
    ]

    # Сначала сохраняем наиболее информативные слова.
    flexible_words = []
    for word in artist_words + title_words:
        if word not in flexible_words:
            flexible_words.append(word)

    if flexible_words:
        add(" ".join(flexible_words))

    return variants


def soundcloud_candidate_score(
    found_artist,
    found_title,
    requested_artist,
    requested_title,
    stage
):
    """
    Оценивает SoundCloud-кандидата.

    Важное отличие от старой логики:
    служебные модификаторы не являются автоматическим reject.

    На поздних этапах поиска допускается, что исполнитель может
    находиться внутри title, а title может частично совпадать
    с artist/title в разных полях.
    """
    found_artist = normalize(found_artist)
    found_title = normalize(found_title)

    requested_artist = normalize(requested_artist)
    requested_title = normalize(requested_title)

    cleaned_artist = clean_soundcloud_text(requested_artist)
    cleaned_title = clean_soundcloud_text(requested_title)

    candidate_text = normalize(
        f"{found_artist} {found_title}"
    )

    if not candidate_text:
        return -100000

    artist_words = normalize_words(cleaned_artist)
    title_words = normalize_words(cleaned_title)
    candidate_words = normalize_words(candidate_text)

    if not artist_words or not title_words:
        return -100000

    artist_hits = len(artist_words & candidate_words)
    title_hits = len(title_words & candidate_words)

    artist_ratio = artist_hits / len(artist_words)
    title_ratio = title_hits / len(title_words)

    # Строгие этапы требуют нормального совпадения.
    if stage <= 2:
        if artist_ratio < 0.5 or title_ratio < 0.5:
            return -100000

    # На гибком этапе допускаем отсутствие исполнителя в user.username,
    # если он присутствует непосредственно в title.
    if stage >= 3:
        if title_ratio < 0.5:
            return -100000

    score = 0

    # Основное совпадение названия.
    score += int(title_ratio * 700)

    # Исполнитель.
    score += int(artist_ratio * 500)

    # Точное название.
    if cleaned_title and cleaned_title in candidate_text:
        score += 350

    # Точный исполнитель.
    if cleaned_artist and cleaned_artist in candidate_text:
        score += 300

    # Полное сочетание.
    combined_1 = normalize(f"{cleaned_artist} {cleaned_title}")
    combined_2 = normalize(f"{cleaned_title} {cleaned_artist}")

    if combined_1 and combined_1 in candidate_text:
        score += 450

    if combined_2 and combined_2 in candidate_text:
        score += 400

    # Проверяем отдельно поля SoundCloud.
    if cleaned_artist:
        if cleaned_artist in found_artist:
            score += 250

        if cleaned_artist in found_title:
            score += 180

    if cleaned_title:
        if cleaned_title in found_title:
            score += 300

        if cleaned_title in found_artist:
            score += 80

    # Штраф за слова, не относящиеся к artist/title.
    expected_words = artist_words | title_words
    extra_words = candidate_words - expected_words

    # Служебные слова не должны давать огромный штраф.
    service_words = set()
    for modifier in SOUNDCLOUD_SERVICE_MODIFIERS:
        service_words.update(normalize_words(modifier))

    meaningful_extra_words = extra_words - service_words

    score -= len(meaningful_extra_words) * 12

    # Служебные модификаторы дают небольшой штраф,
    # но не выбрасывают кандидата.
    modifier_hits = 0
    for modifier in SOUNDCLOUD_SERVICE_MODIFIERS:
        modifier_words = normalize_words(modifier)
        if modifier_words and modifier_words.issubset(candidate_words):
            requested_words = normalize_words(
                f"{requested_artist} {requested_title}"
            )
            if not modifier_words.issubset(requested_words):
                modifier_hits += 1

    score -= modifier_hits * 35

    # На строгом этапе наличие лишних модификаторов снижает рейтинг сильнее,
    # но всё ещё не является абсолютным reject.
    if stage == 1:
        score -= modifier_hits * 60

    return score
