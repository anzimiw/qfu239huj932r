import requests
import re
import html
import base64
import json
import subprocess
import os
import time
import shutil
from urllib.parse import unquote

# Пытаемся импортировать mutagen для обложек и тегов
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("ВНИМАНИЕ: Библиотека mutagen не установлена. Обложки не будут вшиваться.")
    print("Для установки введите в консоли: pip install mutagen\n")

# Ищем yt-dlp.exe в той же папке, где находится сам скрипт
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(SCRIPT_DIR, "yt-dlp.exe")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive"
}

TIMEOUT = 20
MIN_FILE_SIZE = 10 * 1024
MP3PARTY_RETRIES = 3
LRCLIB_DELAY = 1.0


def status(message):
    print(f"\n{message}")


def normalize(text):
    text = html.unescape(str(text))
    text = text.replace("–", "-").replace("—", "-").replace("_", " ")
    text = re.sub(r"\(MP3\.tm\)", "", text, flags=re.I)
    text = re.sub(r"\(audiostart\.net\)", "", text, flags=re.I)
    text = re.sub(r"\.mp3$", "", text, flags=re.I)
    text = re.sub(r"[,;|/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def normalize_words(text):
    return {word for word in normalize(text).split() if word}


def clean_filename(text):
    text = unquote(text)
    text = re.sub(r"\(MP3\.tm\)\.mp3$", "", text, flags=re.I)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_filename(text):
    return re.sub(r'[<>:"/\\|?*]', "", str(text)).strip()


def format_duration(seconds):
    if seconds is None:
        return "??:??"
    try:
        seconds = int(round(float(seconds)))
    except Exception:
        return "??:??"
    return f"{seconds // 60}:{seconds % 60:02d}"


def get_youtube_music_info(url):
    status("Получение информации из YouTube Music...")
    
    if not os.path.exists(YTDLP):
        print(f"ОШИБКА: yt-dlp.exe не найден в папке {SCRIPT_DIR}")
        return None

    command = [
        YTDLP, "--dump-single-json", "--no-download",
        "--no-playlist", "--quiet", "--no-warnings", url
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60
        )

        if result.returncode != 0:
            print("\nНе удалось получить информацию о треке.")
            return None

        data = json.loads(result.stdout)
        artist = data.get("artist") or data.get("uploader") or data.get("creator")
        title = data.get("track") or data.get("title")
        album = data.get("album") or ""
        duration = data.get("duration")

        # Получаем ссылку на обложку (обычно лучшего качества)
        thumbnail_url = None
        if data.get("thumbnails"):
            thumbnail_url = data["thumbnails"][-1].get("url")
        elif data.get("thumbnail"):
            thumbnail_url = data["thumbnail"]

        if not artist or not title:
            print("\nНе удалось определить исполнителя или название.")
            return None

        return {
            "artist": artist,
            "title": title,
            "album": album,
            "duration": duration,
            "cover_url": thumbnail_url
        }

    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"\nОШИБКА получения данных: {e}")
        return None


def search_lrclib(artist, title, album=None, duration=None):
    status("Поиск синхронизированного текста...")
    if duration is None:
        print("Недостаточно данных для точного поиска текста.")
        return None

    try:
        params = {
            "track_name": title, "artist_name": artist,
            "album_name": album or "", "duration": int(round(float(duration)))
        }
        response = requests.get(
            "https://lrclib.net/api/get", params=params,
            headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"},
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            print("Синхронизированный текст не найден.")
            return None

        lyrics = response.json().get("syncedLyrics")
        if not lyrics:
            print("Синхронизированный текст не найден.")
            return None
        return lyrics.strip()
    except Exception:
        print("Не удалось получить текст.")
        return None


def save_lrc(mp3_filepath, lyrics):
    lrc_filepath = os.path.splitext(mp3_filepath)[0] + ".lrc"
    try:
        with open(lrc_filepath, "w", encoding="utf-8-sig", newline="\n") as file:
            file.write(lyrics)
        print("LRC готов.")
        return True
    except Exception as e:
        print(f"\nНе удалось сохранить LRC: {e}")
        return False


def get_playlist_tracks(url):
    status("Получение списка треков плейлиста...")
    command = [
        YTDLP, "--flat-playlist", "--dump-single-json", "--quiet", "--no-warnings", url
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        tracks = []
        for entry in data.get("entries", []):
            if not entry: continue
            track_url = entry.get("webpage_url") or entry.get("original_url") or entry.get("url")
            if track_url:
                if not track_url.startswith("http"):
                    track_url = "https://music.youtube.com/watch?v=" + track_url
                tracks.append(track_url)

        return {"title": data.get("title") or "YouTube Music", "tracks": tracks} if tracks else None
    except Exception as e:
        print(f"\nОшибка получения плейлиста: {e}")
        return None


def validate_audio_file(filename):
    if not os.path.exists(filename): return False
    try:
        if os.path.getsize(filename) < MIN_FILE_SIZE: return False
        command = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=format_name,duration", "-of", "json", filename
        ]
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        if result.returncode != 0: return False
        duration = json.loads(result.stdout).get("format", {}).get("duration")
        return float(duration) > 0 if duration else False
    except Exception:
        return False


def get_duration(url):
    try:
        command = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", url
        ]
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        return float(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None
    except Exception:
        return None


def download_file(url, filename, referer=None, retries=1):
    status("Скачивание аудиофайла...")
    temp_filename = filename + ".tmp"

    for attempt in range(1, retries + 1):
        try:
            if os.path.exists(temp_filename): os.remove(temp_filename)
            headers = dict(HEADERS)
            headers["Accept"] = "audio/mpeg,audio/*;q=0.9,*/*;q=0.8"
            headers["Range"] = "bytes=0-"
            if referer: headers["Referer"] = referer

            with requests.Session() as session:
                response = session.get(url, headers=headers, timeout=60, stream=True, allow_redirects=True)
                if response.status_code not in (200, 206):
                    if attempt < retries:
                        time.sleep(1)
                        continue
                    return False

                total = 0
                with open(temp_filename, "wb") as file:
                    for chunk in response.iter_content(chunk_size=262144):
                        if chunk:
                            file.write(chunk)
                            total += len(chunk)

                print(f"\nПолучено: {round(total / 1024 / 1024, 2)} МБ")
                if total < MIN_FILE_SIZE or not validate_audio_file(temp_filename):
                    if attempt < retries:
                        time.sleep(1)
                        continue
                    return False

                if os.path.exists(filename): os.remove(filename)
                os.replace(temp_filename, filename)
                print("Аудиофайл готов.")
                return True
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            return False
    return False


def embed_metadata(filepath, artist, title, album, cover_url):
    """Скачивает обложку и вшивает метаданные в MP3 через mutagen"""
    if not MUTAGEN_AVAILABLE:
        return
        
    status("Вшивание обложки и тегов...")
    cover_data = None
    if cover_url:
        try:
            r = requests.get(cover_url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                cover_data = r.content
        except Exception as e:
            print(f"Не удалось скачать обложку: {e}")

    try:
        audio = MP3(filepath, ID3=ID3)
        # Если тегов нет, создаем их
        if audio.tags is None:
            audio.add_tags()

        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        if album:
            audio.tags.add(TALB(encoding=3, text=album))

        # Добавляем обложку (тип 3 - Front Cover)
        if cover_data:
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_data
            ))
        
        audio.save()
        print("Теги и обложка успешно добавлены.")
    except Exception as e:
        print(f"Ошибка при сохранении метаданных: {e}")


def search_mp3party(artist, title):
    status("Поиск на MP3Party...")
    try:
        response = requests.get(
            "https://mp3party.net/search", params={"q": f"{artist} {title}"},
            headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code != 200: return None

        text = html.unescape(response.text)
        pattern = re.compile(
            r'<div class="track__user-panel"[^>]*data-js-artist-name="([^"]+)"'
            r'[^>]*data-js-id="(\d+)"[^>]*data-js-song-title="([^"]+)"', re.I
        )
        wanted_artist, wanted_title = normalize(artist), normalize(title)
        
        for found_artist, song_id, found_title in pattern.findall(text):
            if normalize(found_artist) == wanted_artist and normalize(found_title) == wanted_title:
                return {"url": f"https://dl2.mp3party.net/download/{song_id}", "referer": "https://mp3party.net/"}
    except Exception:
        pass
    return None


def score_mp3tm_candidate(filename, artist, title):
    name = normalize(filename)
    wanted_artist, wanted_title = normalize(artist), normalize(title)
    name_words, artist_words, title_words = normalize_words(name), normalize_words(artist), normalize_words(title)

    score = 0
    if artist_words and len(artist_words & name_words) / len(artist_words) == 1: score += 300
    elif artist_words and len(artist_words & name_words) / len(artist_words) >= 0.5: score += 120
    else: return -10000

    if title_words and len(title_words & name_words) / len(title_words) == 1: score += 300
    elif title_words and len(title_words & name_words) / len(title_words) >= 0.5: score += 120
    else: return -10000

    if f"{wanted_artist} - {wanted_title}" in name: score += 500
    if f"{wanted_title} - {wanted_artist}" in name: score += 350
    if name == f"{wanted_artist} {wanted_title}": score += 500

    score -= len(name_words - (artist_words | title_words)) * 20

    modifiers = ["nightcore", "remix", "slowed", "sped", "speed", "bass", "edit", "instrumental", "cover", "live", "phonk", "prod"]
    requested_text = f"{wanted_artist} {wanted_title}"
    for modifier in modifiers:
        if modifier in name and modifier not in requested_text:
            score -= 100
    return score


def search_mp3tm(artist, title, target_duration=None):
    status("Поиск на MP3TM...")
    slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", f"{artist} {title}").strip("-").lower()
    page_url = f"https://{slug}.mp3tm.net/"

    try:
        response = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200: return None
        
        links = list(dict.fromkeys(re.findall(r'https?://[^"\']+\.mp3(?:\?[^"\']*)?', html.unescape(response.text), re.I)))
        candidates = []
        for link in links:
            score = score_mp3tm_candidate(clean_filename(link.split("/")[-1]), artist, title)
            if score > -1000: candidates.append({"url": link, "score": score, "duration": None})

        if not candidates: return None
        candidates.sort(key=lambda item: item["score"], reverse=True)
        top_candidates = [item for item in candidates if item["score"] == candidates[0]["score"]][:10]

        if target_duration is not None:
            for c in top_candidates: c["duration"] = get_duration(c["url"])
            valid = [c for c in top_candidates if c["duration"] is not None]
            best = min(valid, key=lambda item: abs(item["duration"] - target_duration)) if valid else top_candidates[0]
        else:
            best = top_candidates[0]

        return {"url": best["url"], "referer": page_url}
    except Exception:
        return None


def search_audiostart(artist, title):
    status("Поиск на AudioStart...")
    try:
        response = requests.get("https://audiostart.net/", params={"song": f"{artist} {title}"}, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200: return None
        
        links = list(dict.fromkeys(re.findall(r'href=["\']([^"\']*?/getmp3/[^"\']+)["\']', html.unescape(response.text), re.I)))
        wanted_artist, wanted_title = normalize(artist), normalize(title)

        for link in links:
            try:
                decoded = normalize(unquote(base64.b64decode(link.split("/getmp3/", 1)[1]).decode("utf-8", errors="ignore")))
                if wanted_artist in decoded and wanted_title in decoded:
                    return {"url": "https:" + link if link.startswith("//") else link, "referer": "https://audiostart.net/"}
            except Exception:
                continue
    except Exception:
        pass
    return None


def find_and_download_track(artist, title, duration, output_folder):
    print(f"\n{'='*60}\nТРЕК: {artist} — {title}\nДлительность: {format_duration(duration)}\n{'='*60}")
    filename = f"{safe_filename(artist)} - {safe_filename(title)}.mp3"
    filepath = os.path.join(output_folder, filename)

    sources = [
        (search_mp3party, 3),
        (lambda a, t: search_mp3tm(a, t, duration), 2),
        (search_audiostart, 2)
    ]

    for search_func, retries in sources:
        result = search_func(artist, title)
        if result and download_file(result["url"], filepath, referer=result["referer"], retries=retries):
            return filepath

    print("\nНе удалось найти подходящий аудиофайл.")
    return None


def process_single_track(url, output_folder, download_lrc=False):
    info = get_youtube_music_info(url)
    if not info: return False

    print(f"\n{'='*50}\nИНФОРМАЦИЯ О ТРЕКЕ\n{'='*50}\nИсполнитель: {info['artist']}\nНазвание:    {info['title']}")
    if info['album']: print(f"Альбом:      {info['album']}")
    print(f"Длительность: {format_duration(info['duration'])}")

    filepath = find_and_download_track(info['artist'], info['title'], info['duration'], output_folder)
    if not filepath: return False

    # Вшиваем теги и обложку
    embed_metadata(filepath, info['artist'], info['title'], info['album'], info['cover_url'])

    if download_lrc:
        time.sleep(LRCLIB_DELAY)
        lyrics = search_lrclib(info['artist'], info['title'], info['album'], info['duration'])
        if lyrics: save_lrc(filepath, lyrics)

    return True


def process_playlist(url, download_lrc=False):
    playlist = get_playlist_tracks(url)
    if not playlist:
        print(f"\n{'='*60}\nНЕ УДАЛОСЬ ПОЛУЧИТЬ ПЛЕЙЛИСТ\n{'='*60}")
        return

    output_folder = os.path.join(SCRIPT_DIR, safe_filename(playlist["title"]))
    os.makedirs(output_folder, exist_ok=True)
    tracks = playlist["tracks"]

    print(f"\n{'='*60}\nПЛЕЙЛИСТ\n{'='*60}\nНазвание: {playlist['title']}\nТреков: {len(tracks)}\n{'='*60}")
    
    downloaded, failed = 0, 0
    for index, track_url in enumerate(tracks, 1):
        print(f"\n\n{'#'*60}\nТРЕК {index}/{len(tracks)}\n{'#'*60}")
        if process_single_track(track_url, output_folder, download_lrc): downloaded += 1
        else: failed += 1

    print(f"\n\n{'='*60}\nПЛЕЙЛИСТ ЗАВЕРШЁН\n{'='*60}\nВсего треков: {len(tracks)}\nСкачано: {downloaded}\nНе скачано: {failed}\nПапка: {output_folder}")


def main():
    print("=" * 60)
    print("YTMUSIC DOWNLOADER (PRO)")
    print("=" * 60)

    # Проверка зависимостей
    if not shutil.which("ffprobe"):
        print("\nОШИБКА: Утилита ffprobe (FFmpeg) не найдена в системе!")
        print("Она необходима для проверки длительности скачанных файлов.")
        input("Нажмите Enter для выхода...")
        return
        
    if not os.path.exists(YTDLP):
        print(f"\nОШИБКА: yt-dlp.exe не найден в папке {SCRIPT_DIR}")
        input("Нажмите Enter для выхода...")
        return

    print("\nСкачивать текст песни в формате LRC?\n1 — Да\n2 — Нет\n")
    download_lrc = False
    while True:
        choice = input("Ваш выбор [1/2]: ").strip()
        if choice == "1":
            download_lrc = True
            break
        if choice == "2": break
        print("\nВведите 1 или 2.")

    url = input("\nСсылка на трек или плейлист YouTube Music: ").strip()
    if not url:
        print("\nСсылка не указана.")
        input("\nНажмите Enter для выхода...")
        return

    if "list=" in url and ("youtube.com" in url or "music.youtube.com" in url):
        process_playlist(url, download_lrc)
    else:
        tracks_folder = os.path.join(SCRIPT_DIR, "tracks")
        os.makedirs(tracks_folder, exist_ok=True)
        success = process_single_track(url, tracks_folder, download_lrc)
        
        if success:
            print(f"\n{'='*60}\nТРЕК УСПЕШНО СКАЧАН\n{'='*60}\nПапка: {tracks_folder}")
        else:
            print(f"\n{'='*60}\nТРЕК НЕ СКАЧАН\n{'='*60}")

    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
