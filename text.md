[27.08.2026 16:12] Константин: Да. Делаем всё одним комплексным обновлением, но не будем вслепую менять bot.py.

Оптимальная схема:

1. Режим скачивания

Обычный + текст

Обычный без текста

Без цензуры + текст

Без цензуры без текста



2. LRC

Подключаем уже существующую LRC-логику downloader.py.

Для режима без текста LRC вообще не ищем и не скачиваем.



3. Обычный режим

YouTube Music → прямое скачивание через существующий yt-dlp.

Яндекс Музыка → получаем метаданные → ищем соответствующий YouTube/YouTube Music → скачиваем напрямую.

SoundCloud/MP3Party/MP3TM/AudioStart здесь не используются.



4. Режим без цензуры

Используем существующую цепочку поиска источников.

Сохраняем текущую рабочую логику.



5. Telegram-архив

Не храним архив MP3 локально.

Используем приватный Telegram-канал.

Для начала я бы сделал две отдельные темы/ветки: NORMAL и UNCENSORED, если выбранный тип Telegram-чата и API позволяют корректно работать с ними.

Если с темами возникнут технические ограничения, запасной вариант — два отдельных приватных канала.

Бот будет знать режим архива независимо от имени/метаданных MP3.



6. Порядок поиска

Пользователь
↓
выбор режима
↓
ссылка
↓
проверка Telegram-архива
↓
┌─────────────── найден ───────────────┐
↓ ↓
MP3 → пользователю LRC → пользователю
│
└── если не найдено
↓
обычный / без цензуры
↓
скачивание
↓
LRC при необходимости
↓
сохранить результат в архив
↓
отправить пользователю
↓
снова показать меню


7. Главное сообщение бота После /start, после одиночного трека и после полного плейлиста бот возвращается в состояние ожидания следующей ссылки.


8. Для плейлистов Выбранный режим применяется ко всему плейлисту, чтобы не спрашивать пользователя перед каждым треком.



Как будем внедрять

Я предлагаю сделать один основной патч bot.py + минимальный патч downloader.py, а не четыре-пять последовательных патчей.

Но перед этим сделаем техническую проверку текущих файлов и функций. Особенно нужно точно выяснить:

как сейчас реализована LRC-логика;

как сейчас find_and_download_track() выбирает источник;

как реализовано прямое скачивание YouTube;

как Яндекс → YouTube уже связывается;

как устроена обработка плейлистов;

какие функции Telegram уже есть;

куда лучше встроить архив, чтобы не сломать работающий downloader.


Первым действием сейчас нужно получить актуальные bot.py и downloader.py. Если они находятся в том же проекте, выполни в папке engine:

findstr /n /r /c:"^def " bot.py
findstr /n /r /c:"^def " downloader.py

И пришли оба вывода.

После этого я построю точную схему изменений и дам один автоматический патч с резервными копиями, AST/compile-проверкой и проверкой всех новых функций.
[27.08.2026 16:12] Константин: Отлично. Теперь структура зафиксирована. Уже видно, что не нужно переписывать весь проект.

У нас есть чёткие точки интеграции:

bot.py

send_message() — меню и сообщения ожидания;

process_track() — одиночные треки;

process_yandex_playlist() — Яндекс-плейлисты;

process_youtube_playlist() — YouTube-плейлисты;

telegram_upload_file() — отправка файлов;

edit_message() — обновление статусов.


downloader.py

get_yandex_music_info() — Яндекс-метаданные;

get_youtube_music_info() — YouTube-метаданные;

search_lrclib() / save_lrc() / process_lrc() — существующая LRC-система;

download_with_ytdlp() — прямое скачивание;

find_youtube_fallback_url() — поиск YouTube;

find_and_download_track() — текущий поиск источников;

process_single_track() — существующая логика одиночного скачивания.



Как будем делать

Патч №1 — bot.py

Внедряем пользовательский интерфейс и состояние:

/start
↓
[Обычный + текст] [Обычный без текста]
[Без цензуры + текст] [Без цензуры без текста]
↓
Ожидание ссылки

Состояние пользователя передаём непосредственно в обработку трека/плейлиста.

Патч №2 — downloader.py

Добавляем отдельный быстрый путь:

normal
↓
YouTube / YouTube Music
↓
yt-dlp

и для Яндекса:

Yandex
↓
metadata
↓
YouTube поиск
↓
yt-dlp

При этом существующий find_and_download_track() не ломаем — он остаётся путём uncensored.

Патч №3 — Telegram-архив

Я бы пока не смешивал его с первыми двумя патчами. Сначала добиваемся стабильной работы четырёх режимов + LRC. Затем подключаем архив.

Причина простая: если сразу добавить ещё file_id, поиск архива, темы, сохранение сообщений и плейлистную логику, при ошибке будет намного сложнее определить источник проблемы.

Итого фактически получится 3 контролируемых изменения, а не один монолитный патч:

1. Меню + 4 режима + состояние
↓
2. Быстрый режим + LRC
↓
3. Telegram Archive

При этом каждый патч будет:

создавать .backup_YYYYMMDD_HHMMSS;

проверять структуру до изменения;

вносить изменения автоматически;

проверять AST;

выполнять py_compile;

проверять наличие необходимых функций;

прекращать работу при неожиданной структуре файла.


Следующий шаг: перед первым патчем нужно посмотреть конкретный код send_message, process_track, обеих функций плейлистов и LRC-функций. Это позволит сделать патч точно под текущую версию, а не угадывать.
[27.08.2026 16:12] Константин: 1 часть
:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[390..535]"

============================================================

STATUS MESSAGE STATE

============================================================

_STATUS_MESSAGES = {}
_STATUS_LOCK = threading.Lock()

def edit_message(chat_id, message_id, text):

return telegram_request(
"editMessageText",
{
"chat_id": chat_id,
"message_id": message_id,
"text": text
}
)

def send_message(chat_id, text):

technical_error_patterns = (
"TimeoutError:",
"ConnectionError:",
"ConnectionResetError:",
"ConnectionAbortedError:",
"ConnectionRefusedError:",
"socket.timeout",
"WinError 10060",
"WinError 10061",
"WinError 10054",
"Traceback (most recent call last)",
)

text_string = str(
text or ""
)

if any(
pattern in text_string
for pattern in technical_error_patterns
):

print(
"Telegram: С‚РµС…РЅРёС‡РµСЃРєР°СЏ РѕС€РёР±РєР° "
"РЅРµ РѕС‚РїСЂР°РІР»РµРЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ."
)

return {
"ok": False,
"suppressed": True
}

try:

status_states = globals().setdefault(
"_STATUS_MESSAGES",
{}
)

status_lock = globals().get(
"_STATUS_LOCK"
)

if status_lock is None:

status_lock = threading.Lock()

globals()[
"_STATUS_LOCK"
] = status_lock

with status_lock:

status_message_id = (
status_states.get(
chat_id
)
)

if status_message_id:

try:

result = edit_message(
chat_id,
status_message_id,
text_string
)

if result.get("ok"):

return result

except Exception as edit_error:

print(
"Telegram: РЅРµ СѓРґР°Р»РѕСЃСЊ "
"РѕС‚СЂРµРґР°РєС‚РёСЂРѕРІР°С‚СЊ СЃС‚Р°С‚СѓСЃ:"
)

print(
f"{type(edit_error).name}: "
f"{edit_error}"
)

status_states.pop(
chat_id,
None
)

result = telegram_request(
"sendMessage",
{
"chat_id": chat_id,
"text": text_string
}
)

if result.get("ok"):

message = result.get(
"result",
{}
)

message_id = message.get(
"message_id"
)

if message_id:

status_states[
chat_id
] = message_id

return result

except Exception:

raise

def telegram_upload_file(

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[1560..1825]"
)

def process_track(chat_id, url, playlist_progress=None):

try:

# ----------------------------------------------------
# РќРѕРІР°СЏ РѕРґРёРЅРѕС‡РЅР°СЏ СЃСЃС‹Р»РєР° РґРѕР»Р¶РЅР° РїРѕР»СѓС‡РёС‚СЊ РЅРѕРІРѕРµ
# СЂРµРґР°РєС‚РёСЂСѓРµРјРѕРµ СЃС‚Р°С‚СѓСЃРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ.
#
# Р”Р»СЏ С‚СЂРµРєР° РІРЅСѓС‚СЂРё РїР»РµР№Р»РёСЃС‚Р° СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ
# СЃРѕС…СЂР°РЅСЏРµРј.
# ----------------------------------------------------

if not playlist_progress:

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

print()
print("=" * 70)
print("РќРђР§РђР›Рћ РћР‘Р РђР‘РћРўРљР РўР Р•РљРђ")
print("=" * 70)
print()
print(f"URL: {url}")
[27.08.2026 16:12] Константин: if playlist_progress:
current_index, total_tracks = playlist_progress

send_message(
chat_id,
(
f"РћР±СЂР°Р±РѕС‚РєР° С‚СЂРµРєР° "
f"{current_index}/{total_tracks}...\n\n"
f"РџРѕР»СѓС‡Р°СЋ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С‚СЂРµРєРµ..."
)
)
else:
send_message(
chat_id,
"РџРѕР»СѓС‡Р°СЋ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С‚СЂРµРєРµ..."
)

# ----------------------------------------------------
# 1. РџРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё
# ----------------------------------------------------

print()
print("РџРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё РёР· downloader.py...")

if downloader.is_yandex_music_url(url):

print()
print("РСЃС‚РѕС‡РЅРёРє: РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°")
print("РџРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё РёР· РЇРЅРґРµРєСЃ РњСѓР·С‹РєРё...")

info = downloader.get_yandex_music_info(
url
)

else:

print()
print("РСЃС‚РѕС‡РЅРёРє: YouTube Music")
print("РџРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё РёР· YouTube Music...")

info = downloader.get_youtube_music_info(
url
)

if not info:

send_message(
chat_id,
"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С‚СЂРµРєРµ."
)

print(
"РћРЁРР‘РљРђ: РїРѕР»СѓС‡РµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё РІРµСЂРЅСѓР»Рѕ "
"РїСѓСЃС‚РѕР№ СЂРµР·СѓР»СЊС‚Р°С‚."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

print()
print("РРЅС„РѕСЂРјР°С†РёСЏ РїРѕР»СѓС‡РµРЅР°:")
print(info)

artist = info.get(
"artist",
""
)

title = info.get(
"title",
""
)

duration = info.get(
"duration",
0
)

source = info.get(
"source",
"youtube"
)

youtube_age_restricted = info.get(
"youtube_age_restricted",
False
)

if not artist or not title or not duration:

send_message(
chat_id,
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ РёСЃРїРѕР»РЅРёС‚РµР»СЏ, РЅР°Р·РІР°РЅРёРµ РёР»Рё РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ."
)

print(
"РћРЁРР‘РљРђ: РЅРµРїРѕР»РЅС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

# ----------------------------------------------------
# Р¤РѕСЂРјР°С‚ РґР»РёС‚РµР»СЊРЅРѕСЃС‚Рё: MM:SS
# ----------------------------------------------------

try:

duration_seconds = int(
float(duration)
)

minutes = duration_seconds // 60
seconds = duration_seconds % 60

duration_text = (
f"{minutes}:{seconds:02d}"
)

except Exception:

duration_text = str(
duration
)

# ----------------------------------------------------
# 2. РЎРѕРѕР±С‰РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
# ----------------------------------------------------

if playlist_progress:

current_index, total_tracks = playlist_progress

status_text = (
f"РћР±СЂР°Р±РѕС‚РєР° С‚СЂРµРєР° "
f"{current_index}/{total_tracks}\n\n"
f"{artist} вЂ” {title}\n"
f"Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ: {duration_text}\n\n"
f"РќР°С‡РёРЅР°СЋ РїРѕРёСЃРє Р°СѓРґРёРѕС„Р°Р№Р»Р°..."
)

else:
[27.08.2026 16:12] Константин: status_text = (
f"РўСЂРµРє РЅР°Р№РґРµРЅ:\n\n"
f"РСЃРїРѕР»РЅРёС‚РµР»СЊ: {artist}\n"
f"РќР°Р·РІР°РЅРёРµ: {title}\n"
f"Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ: {duration_text}\n\n"
f"РќР°С‡РёРЅР°СЋ РїРѕРёСЃРє Р°СѓРґРёРѕС„Р°Р№Р»Р°..."
)

send_message(
chat_id,
status_text
)

# ----------------------------------------------------
# 3. Р—Р°РїСѓСЃРє СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ downloader.py
# ----------------------------------------------------

print()
print("Р—Р°РїСѓСЃРє find_and_download_track()...")

result = downloader.find_and_download_track(
artist,
title,
duration,
TRACKS_FOLDER,
url,
source,
youtube_age_restricted
)

print()
print("Р РµР·СѓР»СЊС‚Р°С‚ downloader.py:")
print(repr(result))

if not result:

send_message(
chat_id,
(
"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРєР°С‡Р°С‚СЊ Р°СѓРґРёРѕС„Р°Р№Р».\n\n"
f"{artist} вЂ” {title}"
)
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

# ----------------------------------------------------
# 4. РџСЂРѕРІРµСЂРєР° С„Р°Р№Р»Р°
# ----------------------------------------------------

file_path = str(result)

if not os.path.isfile(file_path):

send_message(
chat_id,
"downloader.py Р·Р°РІРµСЂС€РёР»СЃСЏ, РЅРѕ MP3-С„Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ."
)

print(
f"Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ: {file_path}"
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
[27.08.2026 16:12] Константин: :\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[1045..1305]"

============================================================

РћР‘Р РђР‘РћРўРљРђ РџР›Р•Р™Р›РРЎРўРђ РЇРќР”Р•РљРЎ РњРЈР—Р«РљР

============================================================

def process_yandex_playlist(chat_id, url):

try:

print()
print("=" * 70)
print("РќРђР§РђР›Рћ РћР‘Р РђР‘РћРўРљР РџР›Р•Р™Р›РРЎРўРђ")
print("=" * 70)
print()
print(f"URL РїР»РµР№Р»РёСЃС‚Р°: {url}")

send_message(
chat_id,
"РџРѕР»СѓС‡Р°СЋ СЃРїРёСЃРѕРє С‚СЂРµРєРѕРІ РЇРЅРґРµРєСЃ РњСѓР·С‹РєРё..."
)

print()
print("РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°: РїРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° С‚СЂРµРєРѕРІ...")

playlist = downloader.get_playlist_tracks(
url
)

if not playlist:

send_message(
chat_id,
"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє С‚СЂРµРєРѕРІ РЇРЅРґРµРєСЃ-РїР»РµР№Р»РёСЃС‚Р°."
)

print(
"РћРЁРР‘РљРђ: get_playlist_tracks() РІРµСЂРЅСѓР» РїСѓСЃС‚РѕР№ СЂРµР·СѓР»СЊС‚Р°С‚."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return

playlist_title = (
playlist.get("title")
or "РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°"
)

tracks = (
playlist.get("tracks")
or []
)

print()
print(
f"РќР°Р·РІР°РЅРёРµ РїР»РµР№Р»РёСЃС‚Р°: {playlist_title}"
)

print(
f"РќР°Р№РґРµРЅРѕ С‚СЂРµРєРѕРІ: {len(tracks)}"
)

if not tracks:

send_message(
chat_id,
"Р’ РїР»РµР№Р»РёСЃС‚Рµ РЅРµ РЅР°Р№РґРµРЅРѕ С‚СЂРµРєРѕРІ."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return

total_tracks = len(tracks)

send_message(
chat_id,
(
f"РџР»РµР№Р»РёСЃС‚ РЅР°Р№РґРµРЅ.\n\n"
f"{playlist_title}\n"
f"РўСЂРµРєРѕРІ: {total_tracks}\n\n"
f"РќР°С‡РёРЅР°СЋ РѕР±СЂР°Р±РѕС‚РєСѓ..."
)
)

successful = 0
failed = 0

for index, track_url in enumerate(
tracks,
1
):

print()
print("=" * 70)
print(
f"РџР›Р•Р™Р›РРЎРў: РўР Р•Рљ {index}/{total_tracks}"
)
print("=" * 70)
print()
print(
f"URL С‚СЂРµРєР°: {track_url}"
)

try:

success = process_track(
chat_id,
track_url,
playlist_progress=(
index,
total_tracks
)
)

if success:
successful += 1
else:
failed += 1

send_message(
chat_id,
(
f"РўСЂРµРє {index}/{total_tracks} "
f"РЅРµ РѕР±СЂР°Р±РѕС‚Р°РЅ.\n\n"
f"РџСЂРѕРґРѕР»Р¶Р°СЋ РїР»РµР№Р»РёСЃС‚..."
)
)

except Exception as track_error:

failed += 1

print()
print(
"РћРЁРР‘РљРђ РўР Р•РљРђ РџР›Р•Р™Р›РРЎРўРђ:"
)

print(
f"{type(track_error).name}: "
f"{track_error}"
)

try:

send_message(
chat_id,
(
f"РўСЂРµРє {index}/{total_tracks} "
f"РЅРµ РѕР±СЂР°Р±РѕС‚Р°РЅ.\n\n"
f"РџСЂРѕРґРѕР»Р¶Р°СЋ РїР»РµР№Р»РёСЃС‚..."
)
)
[27.08.2026 16:12] Константин: except Exception as telegram_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ:"
)

print(
f"{type(telegram_error).name}: "
f"{telegram_error}"
)

print()
print("=" * 70)
print("РџР›Р•Р™Р›РРЎРў Р—РђР’Р•Р РЁРЃРќ")
print("=" * 70)
print()

print(
f"Р’СЃРµРіРѕ С‚СЂРµРєРѕРІ: {total_tracks}"
)

print(
f"РЈСЃРїРµС€РЅРѕ: {successful}"
)

print(
f"РћС€РёР±РѕРє: {failed}"
)

send_message(
chat_id,
(
f"РћР±СЂР°Р±РѕС‚РєР° РїР»РµР№Р»РёСЃС‚Р° Р·Р°РІРµСЂС€РµРЅР°.\n\n"
f"{playlist_title}\n\n"
f"Р’СЃРµРіРѕ С‚СЂРµРєРѕРІ: {total_tracks}\n"
f"РЈСЃРїРµС€РЅРѕ: {successful}\n"
f"РћС€РёР±РѕРє: {failed}"
)
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

except Exception as e:

print()
print("=" * 70)
print("РћРЁРР‘РљРђ РћР‘Р РђР‘РћРўРљР РџР›Р•Р™Р›РРЎРўРђ")
print("=" * 70)
print()

print(
f"{type(e).name}: {e}"
)

try:

send_message(
chat_id,
"РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РїР»РµР№Р»РёСЃС‚Р°."
)

except Exception as telegram_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ:"
)

print(
f"{type(telegram_error).name}: "
f"{telegram_error}"
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

============================================================

РћР‘Р РђР‘РћРўРљРђ РџР›Р•Р™Р›РРЎРўРђ YOUTUBE MUSIC

============================================================

def process_youtube_playlist(chat_id, url):

try:

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[1295..1565]"
None
)

============================================================

РћР‘Р РђР‘РћРўРљРђ РџР›Р•Р™Р›РРЎРўРђ YOUTUBE MUSIC

============================================================

def process_youtube_playlist(chat_id, url):

try:

print()
print("=" * 70)
print("РќРђР§РђР›Рћ РћР‘Р РђР‘РћРўРљР YOUTUBE MUSIC РџР›Р•Р™Р›РРЎРўРђ")
print("=" * 70)
print()
print(f"URL РїР»РµР№Р»РёСЃС‚Р°: {url}")

send_message(
chat_id,
"РџРѕР»СѓС‡Р°СЋ СЃРїРёСЃРѕРє С‚СЂРµРєРѕРІ YouTube Music..."
)

print()
print(
"YouTube Music: РїРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° С‚СЂРµРєРѕРІ "
"С‡РµСЂРµР· downloader.py..."
)

playlist = downloader.get_youtube_playlist_tracks(
url
)

if not playlist:

send_message(
chat_id,
"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє С‚СЂРµРєРѕРІ YouTube Music."
)

print(
"РћРЁРР‘РљРђ: get_youtube_playlist_tracks() "
"РІРµСЂРЅСѓР» РїСѓСЃС‚РѕР№ СЂРµР·СѓР»СЊС‚Р°С‚."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return

playlist_title = (
playlist.get("title")
or "YouTube Music"
)

tracks = (
playlist.get("tracks")
or []
)

print()
print(
f"РќР°Р·РІР°РЅРёРµ РїР»РµР№Р»РёСЃС‚Р°: {playlist_title}"
)

print(
f"РќР°Р№РґРµРЅРѕ С‚СЂРµРєРѕРІ: {len(tracks)}"
)

if not tracks:

send_message(
chat_id,
"Р’ YouTube Music РїР»РµР№Р»РёСЃС‚Рµ РЅРµ РЅР°Р№РґРµРЅРѕ С‚СЂРµРєРѕРІ."
)
[27.08.2026 16:12] Константин: globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return

total_tracks = len(tracks)

send_message(
chat_id,
(
f"РџР»РµР№Р»РёСЃС‚ РЅР°Р№РґРµРЅ.\n\n"
f"{playlist_title}\n"
f"РўСЂРµРєРѕРІ: {total_tracks}\n\n"
f"РќР°С‡РёРЅР°СЋ РѕР±СЂР°Р±РѕС‚РєСѓ..."
)
)

successful = 0
failed = 0

for index, track_url in enumerate(
tracks,
1
):

print()
print("=" * 70)
print(
f"YOUTUBE MUSIC: РўР Р•Рљ "
f"{index}/{total_tracks}"
)
print("=" * 70)
print()
print(
f"URL С‚СЂРµРєР°: {track_url}"
)

try:

success = process_track(
chat_id,
track_url,
playlist_progress=(
index,
total_tracks
)
)

if success:

successful += 1

else:

failed += 1

send_message(
chat_id,
(
f"РўСЂРµРє {index}/{total_tracks} "
f"РЅРµ РѕР±СЂР°Р±РѕС‚Р°РЅ.\n\n"
f"РџСЂРѕРґРѕР»Р¶Р°СЋ РїР»РµР№Р»РёСЃС‚..."
)
)

except Exception as track_error:

failed += 1

print()
print(
"РћРЁРР‘РљРђ РўР Р•РљРђ YOUTUBE MUSIC РџР›Р•Р™Р›РРЎРўРђ:"
)

print(
f"{type(track_error).name}: "
f"{track_error}"
)

try:

send_message(
chat_id,
(
f"РўСЂРµРє {index}/{total_tracks} "
f"РЅРµ РѕР±СЂР°Р±РѕС‚Р°РЅ.\n\n"
f"РџСЂРѕРґРѕР»Р¶Р°СЋ РїР»РµР№Р»РёСЃС‚..."
)
)

except Exception as telegram_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ:"
)

print(
f"{type(telegram_error).name}: "
f"{telegram_error}"
)

print()
print("=" * 70)
print("YOUTUBE MUSIC РџР›Р•Р™Р›РРЎРў Р—РђР’Р•Р РЁРЃРќ")
print("=" * 70)
print()

print(
f"РќР°Р·РІР°РЅРёРµ: {playlist_title}"
)

print(
f"Р’СЃРµРіРѕ С‚СЂРµРєРѕРІ: {total_tracks}"
)

print(
f"РЈСЃРїРµС€РЅРѕ: {successful}"
)

print(
f"РћС€РёР±РѕРє: {failed}"
)

send_message(
chat_id,
(
f"РћР±СЂР°Р±РѕС‚РєР° РїР»РµР№Р»РёСЃС‚Р° Р·Р°РІРµСЂС€РµРЅР°.\n\n"
f"{playlist_title}\n\n"
f"Р’СЃРµРіРѕ С‚СЂРµРєРѕРІ: {total_tracks}\n"
f"РЈСЃРїРµС€РЅРѕ: {successful}\n"
f"РћС€РёР±РѕРє: {failed}"
)
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

except Exception as e:

print()
print("=" * 70)
print("РћРЁРР‘РљРђ РћР‘Р РђР‘РћРўРљР YOUTUBE MUSIC РџР›Р•Р™Р›РРЎРўРђ")
print("=" * 70)
print()

print(
f"{type(e).name}: {e}"
)

try:

send_message(
chat_id,
"РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ YouTube Music РїР»РµР№Р»РёСЃС‚Р°."
)

except Exception as telegram_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ:"
)

print(
f"{type(telegram_error).name}: "
f"{telegram_error}"
)
[27.08.2026 16:12] Константин: globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

def process_track(chat_id, url, playlist_progress=None):

try:
[27.08.2026 16:13] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[1820..2200]"
globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

file_size = os.path.getsize(
file_path
)

print()
print("MP3 СЃРѕР·РґР°РЅ:")
print(f" {file_path}")
print(f" Р Р°Р·РјРµСЂ: {file_size:,} Р±Р°Р№С‚")

# ----------------------------------------------------
# Р”РѕР±Р°РІР»РµРЅРёРµ embedded cover Рё ID3-С‚РµРіРѕРІ
# ----------------------------------------------------

print()
print("Р”РѕР±Р°РІР»РµРЅРёРµ РѕР±Р»РѕР¶РєРё РІ MP3...")

downloader.embed_cover(
file_path,
info.get("cover_url"),
artist,
title,
info.get("album", "")
)

# ----------------------------------------------------
# РџСЂРѕРІРµСЂРєР° embedded cover
# ----------------------------------------------------

try:

from mutagen.id3 import ID3

tags = ID3(file_path)

apic_count = len(
tags.getall("APIC:")
)

print(
f"Embedded cover APIC: {apic_count}"
)

if apic_count > 0:
print(
"OK: РѕР±Р»РѕР¶РєР° РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ Р·Р°РїРёСЃР°РЅР° РІ MP3."
)
else:
print(
"Р’РќРРњРђРќРР•: APIC РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РІ MP3."
)

except Exception as cover_check_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ embedded cover:",
cover_check_error
)

# ----------------------------------------------------
# РЎС‚Р°С‚СѓСЃ РїРµСЂРµРґ РѕС‚РїСЂР°РІРєРѕР№ MP3
# ----------------------------------------------------

send_message(
chat_id,
(
f"РўСЂРµРє СЃРєР°С‡Р°РЅ.\n\n"
f"{artist} вЂ” {title}"
)
)

print()
print("Р­РўРђРџ РЎРљРђР§РР’РђРќРРЇ РЈРЎРџР•РЁРќРћ Р—РђР’Р•Р РЁРЃРќ.")

# ----------------------------------------------------
# РћС‚РїСЂР°РІРєР° MP3 РІ Telegram
# ----------------------------------------------------

print()
print("РћС‚РїСЂР°РІРєР° MP3 РІ Telegram...")

upload_result = send_audio(
chat_id,
file_path
)

if upload_result.get("ok"):

print(
"MP3 СѓСЃРїРµС€РЅРѕ РѕС‚РїСЂР°РІР»РµРЅ РІ Telegram."
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return True

print(
"РћС€РёР±РєР° РѕС‚РїСЂР°РІРєРё MP3:"
)

print(
upload_result
)

send_message(
chat_id,
(
"РўСЂРµРє СЃРєР°С‡Р°РЅ, РЅРѕ Telegram "
"РЅРµ РїСЂРёРЅСЏР» MP3 РїСЂРё РѕС‚РїСЂР°РІРєРµ."
)
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

except Exception as e:

print()
print("=" * 70)
print("РћРЁРР‘РљРђ РћР‘Р РђР‘РћРўРљР РўР Р•РљРђ")
print("=" * 70)
print()

print(
f"{type(e).name}: {e}"
)

try:

send_message(
chat_id,
"РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ С‚СЂРµРєР°."
)

except Exception as telegram_error:

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ:"
)

print(
f"{type(telegram_error).name}: "
f"{telegram_error}"
)

globals().get(
"_STATUS_MESSAGES",
{}
).pop(
chat_id,
None
)

return False

============================================================

START
[27.08.2026 16:13] Константин: ============================================================

print("=" * 70)
print("CENSURU.NET вЂ” TELEGRAM BOT")
print("=" * 70)

print()
print(f"Bot API IP: {TELEGRAM_IP}")
print(f"Host/SNI: {TELEGRAM_HOST}")
print()
print(f"TRACKS_FOLDER:")
print(f" {TRACKS_FOLDER}")
print()

print("downloader.py: OK")

============================================================

РџР РћР’Р•Р РљРђ BOT API

============================================================

print()
print("РџСЂРѕРІРµСЂРєР° Bot API...")

try:

result = telegram_request(
"getMe"
)

if not result.get("ok"):

print("РћРЁРР‘РљРђ Telegram API:")
print(result)

raise SystemExit(2)

bot = result["result"]

print()
print("Bot API: OK")
print(
f"Р‘РѕС‚: @{bot.get('username')}"
)

except Exception as e:

print()
print("РћРЁРР‘РљРђ РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Telegram:")
print(
f"{type(e).name}: {e}"
)

raise SystemExit(3)

============================================================

LONG POLLING

============================================================

print()
print("-" * 70)
print("Р‘РћРў Р—РђРџРЈР©Р•Рќ")
print("-" * 70)

print()
print("РџРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ РІРІРѕРґ:")
print(" YouTube Music")
print(" РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°")
print()
print("Р”Р»СЏ РѕСЃС‚Р°РЅРѕРІРєРё РЅР°Р¶РјРё Ctrl+C.")
print()

offset = None

while True:

try:

response = get_updates(
offset
)

if not response.get("ok"):

print(
"РћС€РёР±РєР° getUpdates:",
response
)

time.sleep(3)
continue

updates = response.get(
"result",
[]
)

for update in updates:

offset = (
update["update_id"] + 1
)

message = update.get(
"message"
)

if not message:
continue

chat = message.get(
"chat",
{}
)

chat_id = chat.get(
"id"
)

text = message.get(
"text",
""
).strip()

if not chat_id:
continue

print()
print(
f"[MESSAGE] {chat_id}: {text}"
)

# ------------------------------------------------
# START
# ------------------------------------------------

if text == "/start":

send_message(
chat_id,
(
"Р¦РµРЅР·СѓСЂС‹.РЅРµС‚\n\n"
"РћС‚РїСЂР°РІСЊ СЃСЃС‹Р»РєСѓ РЅР° С‚СЂРµРє "
"YouTube Music РёР»Рё РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°."
)
)

continue

# ------------------------------------------------
# РџСЂРѕРІРµСЂРєР° СЃСЃС‹Р»РєРё
# ------------------------------------------------

is_youtube = (
"youtube.com" in text
or "youtu.be" in text
)

is_yandex = (
"music.yandex.ru" in text
or "music.yandex.com" in text
)

if not is_youtube and not is_yandex:

send_message(
chat_id,
(
"РћС‚РїСЂР°РІСЊ СЃСЃС‹Р»РєСѓ РЅР° С‚СЂРµРє "
"YouTube Music РёР»Рё РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°."
)
)

continue

# ------------------------------------------------
# РћРїСЂРµРґРµР»СЏРµРј: РѕРґРёРЅРѕС‡РЅС‹Р№ С‚СЂРµРє РёР»Рё РїР»РµР№Р»РёСЃС‚
# ------------------------------------------------

if downloader.is_playlist_url(text):

print()
print(
"РћР±РЅР°СЂСѓР¶РµРЅ РїР»РµР№Р»РёСЃС‚."
)

if downloader.is_yandex_music_url(text):

print(
"РСЃС‚РѕС‡РЅРёРє РїР»РµР№Р»РёСЃС‚Р°: "
"РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°"
)
[27.08.2026 16:13] Константин: thread = threading.Thread(
target=process_yandex_playlist,
args=(
chat_id,
text
),

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginepowershell -NoProfile -Command "$p=Get-Content downloader.py; $p[2420..2735]"
return None

print()
print(
f"РќР°Р·РІР°РЅРёРµ РїР»РµР№Р»РёСЃС‚Р°: "
f"{playlist_title}"
)

print(
f"РќР°Р№РґРµРЅРѕ С‚СЂРµРєРѕРІ: "
f"{len(tracks)}"
)

return {
"title": playlist_title,
"tracks": tracks
}

GENERAL TRACK INFO

def get_track_info(
url,
youtube_retries=1
):
if is_yandex_music_url(url):
return get_yandex_music_info(url)

return get_youtube_music_info(
url,
retries=youtube_retries
)

LRCLIB

def search_lrclib(
artist,
title,
album=None,
duration=None
):
status(
"РџРѕРёСЃРє С‚РµРєСЃС‚Р° РїРµСЃРЅРё..."
)

clean_art = clean_search_query(
artist
)

clean_tit = clean_search_query(
title
)

if duration is not None:
try:
response = requests.get(
"https://lrclib.net/api/get",
params={
"track_name": clean_tit,
"artist_name": clean_art,
"duration": int(
round(
float(duration)
)
)
},
headers={
"User-Agent": HEADERS[
"User-Agent"
],
"Accept": "application/json"
},
timeout=TIMEOUT
)

if response.status_code == 200:
data = response.json()

synced = data.get(
"syncedLyrics"
)

plain = data.get(
"plainLyrics"
)

if (
synced
and synced.strip()
):
return synced.strip()

if (
plain
and plain.strip()
):
return plain.strip()

except Exception:
pass

queries = [
f"{clean_art} {clean_tit}",
f"{clean_tit}"
]

plain_fallback = None

for query in queries:
try:
response = requests.get(
"https://lrclib.net/api/search",
params={
"q": query
},
headers={
"User-Agent": HEADERS[
"User-Agent"
],
"Accept": "application/json"
},
timeout=TIMEOUT
)

if response.status_code != 200:
continue

results = response.json()

if (
not isinstance(
results,
list
)
or not results
):
continue

norm_target_title = normalize(
title
)

for item in results:
if not isinstance(
item,
dict
):
continue

synced = item.get(
"syncedLyrics"
)

plain = item.get(
"plainLyrics"
)

if not synced and not plain:
continue

item_track = normalize(
item.get(
"trackName"
)
or ""
)

target_words = normalize_words(
title
)

item_words = normalize_words(
item_track
)
[27.08.2026 16:13] Константин: if (
target_words
and not (
target_words
& item_words
)
and norm_target_title
not in item_track
and item_track
not in norm_target_title
):
continue

if (
synced
and synced.strip()
):
return synced.strip()

if (
plain
and plain.strip()
and not plain_fallback
):
plain_fallback = (
plain.strip()
)

except Exception:
continue

return plain_fallback

def save_lrc(
mp3_filepath,
lyrics
):
path = (
os.path.splitext(
mp3_filepath
)[0]
+ ".lrc"
)

try:
with open(
path,
"w",
encoding="utf-8-sig",
newline="\n"
) as f:
f.write(lyrics)

print(
"РўРµРєСЃС‚ СЃРѕС…СЂР°РЅРµРЅ РІ LRC."
)

return True

except Exception:
print(
"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ LRC."
)

return False

def process_lrc(
artist,
title,
album,
duration,
mp3_filepath
):
lyrics = search_lrclib(
artist,
title,
album,
duration
)

if not lyrics:
print(
"РўРµРєСЃС‚ РїРµСЃРЅРё РЅРµ РЅР°Р№РґРµРЅ."
)

return False

is_synced = bool(
re.search(
r"\d{2}:\d{2}\.\d{2,3}",
lyrics
)
)

if is_synced:
print(
"РќР°Р№РґРµРЅ СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°РЅРЅС‹Р№ "
"С‚РµРєСЃС‚ СЃ С‚Р°Р№РјРєРѕРґР°РјРё."
)

else:
print(
"РќР°Р№РґРµРЅ РЅРµСЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°РЅРЅС‹Р№ "
"РѕР±С‹С‡РЅС‹Р№ С‚РµРєСЃС‚."
)

status(
"РЎРѕС…СЂР°РЅРµРЅРёРµ С‚РµРєСЃС‚Р°..."
)

return save_lrc(
mp3_filepath,
lyrics
)

PLAYLIST

def _decode_yandex_text(value):
"""
Р‘РµР·РѕРїР°СЃРЅРѕРµ РґРµРєРѕРґРёСЂРѕРІР°РЅРёРµ СЃС‚СЂРѕРє РЇРЅРґРµРєСЃ РњСѓР·С‹РєРё.

РќРµ РїСЂРѕРіРѕРЅСЏРµС‚ РѕР±С‹С‡РЅС‹Р№ UTF-8 Unicode С‡РµСЂРµР·
unicode_escape, РїРѕСЃРєРѕР»СЊРєСѓ СЌС‚Рѕ РїРѕСЂС‚РёС‚ РєРёСЂРёР»Р»РёС†Сѓ.

РџСЂРё СЌС‚РѕРј РєРѕСЂСЂРµРєС‚РЅРѕ РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚ JSON-style
escape-РїРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅРѕСЃС‚Рё РІСЂРѕРґРµ:
\u0410
\/
\"
\\

РћР±С‹С‡РЅС‹Р№ Unicode-С‚РµРєСЃС‚ РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ Р±РµР· РёР·РјРµРЅРµРЅРёР№.
"""

if value is None:
return ""

value = str(value)

if "\\" not in value:
[27.08.2026 16:13] Константин: Да. Теперь у нас достаточно структуры, чтобы делать это не четырьмя разрозненными патчами, а одним согласованным обновлением архитектуры.

Но перед патчем я хочу проверить ещё два конкретных участка, чтобы не ломать уже работающий downloader:

1. bot.py — оставшуюся часть основного while True, включая обработку ссылок и запуск потоков.


2. downloader.py — process_single_track(), process_playlist() и find_and_download_track(), чтобы правильно подключить режим «обычный / без цензуры» и LRC.



Пришли выводы этих команд:

powershell -NoProfile -Command "$p=Get-Content bot.py; $p[2190..2500]"

powershell -NoProfile -Command "$p=Get-Content downloader.py; $p[4230..4645]"

После этого я соберу один итоговый патч с резервной копией и автоматическими проверками, в котором сразу будут:

стартовое сообщение: «Cenzuru.net — отправь ссылку на трек или плейлист YouTube Music или Яндекс Музыка»;

после завершения одиночного трека — возврат к этому сообщению;

после завершения плейлиста — возврат к нему;

4 режима:

1. обычный + текст;


2. обычный без текста;


3. без цензуры + текст;


4. без цензуры без текста;



выбор режима до отправки ссылки;

выбранный режим сохраняется для следующей ссылки пользователя;

обычный режим максимально быстро использует прямое скачивание через YouTube/yt-dlp, а не SoundCloud/MP3Party;

режим без цензуры продолжает использовать существующую цепочку поиска;

LRC скачивается только если пользователь выбрал вариант с текстом;

LRC отправляется пользователю вместе с MP3;

архив Telegram будет заложен так, чтобы обычные и нецензурные файлы никогда не смешивались;

локального архива MP3 не добавляем;

существующую рабочую систему SoundCloud/MP3Party/AudioStart не ломаем.


И главное: архив Telegram я бы подключал уже в этом же патче как отдельный слой, но сам поиск в архиве сделаем до внешнего поиска. Это даст максимальный выигрыш именно для повторно запрашиваемых треков.
[27.08.2026 16:13] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>powershell -NoProfile -Command "$p=Get-Content bot.py; $p[2190..2500]"
print(
"РСЃС‚РѕС‡РЅРёРє РїР»РµР№Р»РёСЃС‚Р°: "
"РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°"
)

thread = threading.Thread(
target=process_yandex_playlist,
args=(
chat_id,
text
),
daemon=True
)

else:

print(
"РСЃС‚РѕС‡РЅРёРє РїР»РµР№Р»РёСЃС‚Р°: "
"YouTube Music"
)

# РўРµРєСѓС‰СѓСЋ РѕР±СЂР°Р±РѕС‚РєСѓ YouTube-РїР»РµР№Р»РёСЃС‚РѕРІ
# РїРѕРєР° РЅРµ РјРµРЅСЏРµРј.
thread = threading.Thread(
target=process_youtube_playlist,
args=(
chat_id,
text
),
daemon=True
)

else:

thread = threading.Thread(
target=process_track,
args=(
chat_id,
text
),
daemon=True
)

thread.start()

except KeyboardInterrupt:

print()
print("Р‘РѕС‚ РѕСЃС‚Р°РЅРѕРІР»РµРЅ.")
break

except Exception as e:

print()
print(
"РћС€РёР±РєР° polling:",
f"{type(e).name}: {e}"
)

print(
"РџРѕРІС‚РѕСЂ С‡РµСЂРµР· 3 СЃРµРєСѓРЅРґС‹..."
)

time.sleep(3)

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginepowershell -NoProfile -Command "$p=Get-Content downloader.py; $p[4230..4645]"

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРєР°С‡Р°С‚СЊ "
"РїРѕРґС…РѕРґСЏС‰РёР№ Р°СѓРґРёРѕС„Р°Р№Р»."
)

return None

SINGLE TRACK

def process_single_track(
url,
output_folder,
youtube_retries=1,
return_failure=False
):
info = get_track_info(
url,
youtube_retries=youtube_retries
)

if not info:
reason = (
LAST_YOUTUBE_ERROR
if LAST_YOUTUBE_ERROR
else
"РРЅС„РѕСЂРјР°С†РёСЏ РёР· "
"YouTube Music РЅРµ РїРѕР»СѓС‡РµРЅР°."
)

failure = {
"artist": "",
"title": "",
"url": url,
"reason": reason
}

if return_failure:
return (
False,
failure
)

return False

source = info.get(
"source",
"youtube"
)

youtube_age_restricted = bool(
info.get(
"age_restricted",
False
)
)

artist = info["artist"]
title = info["title"]
album = info["album"]
duration = info["duration"]
cover_url = info.get(
"cover_url"
)

print()
print("=" * 60)
print("РРќР¤РћР РњРђР¦РРЇ Рћ РўР Р•РљР•")
print("=" * 60)

print(
f"РСЃС‚РѕС‡РЅРёРє: {source}"
)

print(
f"РСЃРїРѕР»РЅРёС‚РµР»СЊ: {artist}"
)

print(
f"РќР°Р·РІР°РЅРёРµ: {title}"
)

if album:
print(
f"РђР»СЊР±РѕРј: {album}"
)

print(
f"Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ: "
f"{format_duration(duration)}"
)

print(
"РћР±Р»РѕР¶РєР°: "
f"{'РќРђР™Р”Р•РќРђ' if cover_url else 'РќР• РќРђР™Р”Р•РќРђ'}"
)

source_url = (
url
if source == "youtube"
else None
)

filepath = find_and_download_track(
artist,
title,
duration,
output_folder,
source_url,
source,
youtube_age_restricted=youtube_age_restricted
)

if not filepath:
failure = {
"artist": artist,
"title": title,
"url": url,
"reason": (
"РџРѕРґС…РѕРґСЏС‰РёР№ Р°СѓРґРёРѕС„Р°Р№Р» "
"РЅРµ РЅР°Р№РґРµРЅ РёР»Рё "
"РЅРµ РїСЂРѕС€С‘Р» РїСЂРѕРІРµСЂРєСѓ."
)
}

if return_failure:
return (
False,
failure
)

return False
[27.08.2026 16:13] Константин: # Р•СЃР»Рё С„Р°Р№Р» РІСЃС‘-С‚Р°РєРё СЃРєР°С‡Р°РЅ, Р»СЋР±С‹Рµ РїСЂРµРґС‹РґСѓС‰РёРµ
# age restriction РѕС€РёР±РєРё СѓР¶Рµ РЅРµ РёРјРµСЋС‚ Р·РЅР°С‡РµРЅРёСЏ.

embed_cover(
filepath,
cover_url,
artist,
title,
album
)

if DOWNLOAD_LRC:
time.sleep(
LRCLIB_DELAY
)

process_lrc(
artist,
title,
album,
duration,
filepath
)

if return_failure:
return (
True,
None
)

return True

FAILED TRACKS

def save_failed_tracks(
output_folder,
failed_tracks
):
if not failed_tracks:
return None

filepath = os.path.join(
output_folder,
"failed_tracks.txt"
)

try:
with open(
filepath,
"w",
encoding="utf-8"
) as f:

f.write(
"РќР•РЎРљРђР§РђРќРќР«Р• РўР Р•РљР\n"
)

f.write(
"=" * 60
+ "\n\n"
)

for index, track in enumerate(
failed_tracks,
1
):
artist = (
track.get("artist")
or "РќРµРёР·РІРµСЃС‚РЅС‹Р№ РёСЃРїРѕР»РЅРёС‚РµР»СЊ"
)

title = (
track.get("title")
or "РќР°Р·РІР°РЅРёРµ РЅРµ РѕРїСЂРµРґРµР»РµРЅРѕ"
)

url = (
track.get("url")
or ""
)

reason = (
track.get("reason")
or "РџСЂРёС‡РёРЅР° РЅРµ РѕРїСЂРµРґРµР»РµРЅР°"
)

f.write(
f"{index}. "
f"{artist} вЂ” {title}\n"
)

f.write(
f"РЎСЃС‹Р»РєР°: {url}\n"
)

f.write(
f"РџСЂРёС‡РёРЅР°: {reason}\n"
)

f.write(
"\n"
)

return filepath

except Exception as e:
print()
print(
"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ "
"failed_tracks.txt:"
)

print(
e
)

return None

PLAYLIST PROCESSING

def process_playlist(url):
playlist = get_playlist_tracks(
url
)

if not playlist:
print(
"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ "
"РїР»РµР№Р»РёСЃС‚."
)

return

playlist_title = safe_filename(
playlist["title"]
)

output_folder = os.path.join(
PROJECT_FOLDER,
playlist_title
)

os.makedirs(
output_folder,
exist_ok=True
)

tracks = playlist["tracks"]

print()
print("=" * 60)
print("РџР›Р•Р™Р›РРЎРў")
print("=" * 60)

print(
f"РќР°Р·РІР°РЅРёРµ: "
f"{playlist['title']}"
)

print(
f"РўСЂРµРєРѕРІ: {len(tracks)}"
)

downloaded = 0
failed = 0

failed_tracks = []

for index, track_url in enumerate(
tracks,
1
):
print()
print(
f"РўСЂРµРє {index}/{len(tracks)}"
)

success, failure = (
process_single_track(
track_url,
output_folder,
youtube_retries=YOUTUBE_INFO_RETRIES,
return_failure=True
)
)

if success:
downloaded += 1

else:
failed += 1

if failure:
failed_tracks.append(
failure
)

failed_file = save_failed_tracks(
output_folder,
failed_tracks
)

print()
print("=" * 60)
print("РџР›Р•Р™Р›РРЎРў Р—РђР’Р•Р РЁРЃРќ")
print("=" * 60)

print(
f"Р’СЃРµРіРѕ С‚СЂРµРєРѕРІ: {len(tracks)}"
)

print(
f"РЎРєР°С‡Р°РЅРѕ: {downloaded}"
)

print(
f"РќРµ СЃРєР°С‡Р°РЅРѕ: {failed}"
)

if failed_tracks:
print()
print(
"РќР• РЎРљРђР§РђРќРќР«Р• РўР Р•РљР:"
)

print()
[27.08.2026 16:13] Константин: for index, track in enumerate(
failed_tracks,
1
):
artist = (
track.get("artist")
or "РСЃРїРѕР»РЅРёС‚РµР»СЊ РЅРµ РѕРїСЂРµРґРµР»С‘РЅ"
)

title = (
track.get("title")
or "РќР°Р·РІР°РЅРёРµ РЅРµ РѕРїСЂРµРґРµР»РµРЅРѕ"
)

reason = (
track.get("reason")
or "РџСЂРёС‡РёРЅР° РЅРµ РѕРїСЂРµРґРµР»РµРЅР°"
)

print(
f"{index}. "
f"{artist} вЂ” {title}"
)

print(
f" РџСЂРёС‡РёРЅР°: {reason}"
)

if failed_file:
print()
print(
"РџРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє СЃРѕ СЃСЃС‹Р»РєР°РјРё:"
)

print(
failed_file
)

print()
print(
f"РџР°РїРєР°: {output_folder}"
)

URL HELPERS

def is_playlist_url(url):
if not url:
return False

lowered = url.lower()

if (
"music.yandex.ru/playlists/"
in lowered
or
[27.08.2026 16:13] Константин: Да. Этих двух фрагментов уже достаточно, чтобы понять основную архитектуру. Но сейчас патч ещё не делаем: для четырёх режимов нам обязательно нужно увидеть саму реализацию скачивания через find_and_download_track() и проверить, есть ли в bot.py какая-либо обработка callback_query.

Пришли один вывод:

findstr /n /i /c:"callback" /c:"reply_markup" /c:"inline_keyboard" /c:"answerCallbackQuery" /c:"send_document" /c:"send_audio" bot.py

И ещё:

powershell -NoProfile -Command "$p=Get-Content downloader.py; $p[3880..4245]"

Что уже подтверждено

У нас есть хорошая база:

send_message() уже существует — предыдущая ошибка NameError устранена.

Есть отдельные process_track(), process_yandex_playlist() и process_youtube_playlist().

Downloader уже умеет process_lrc().

process_single_track() уже умеет получать LRC через DOWNLOAD_LRC.

find_and_download_track() — правильное место для разделения:

обычного режима → прямой YouTube/yt-dlp;

без цензуры → существующий поиск SoundCloud → MP3Party → AudioStart и т. д.


Telegram-архив можно встроить до внешнего поиска.


Как я предлагаю сделать итоговый патч

Не будем делать четыре последовательных патча. Сделаем один архитектурный патч V1, который добавит состояние пользователя:

РЕЖИМ:
обычный + LRC
обычный без LRC
без цензуры + LRC
без цензуры без LRC

После /start:

Cenzuru.net

Отправь ссылку на трек или плейлист
YouTube Music или Яндекс Музыка.

Выбери режим скачивания:
[ Обычный + текст ]
[ Обычный без текста ]
[ Без цензуры + текст ]
[ Без цензуры без текста ]

После выбора бот не начинает скачивание, а ждёт ссылку.

После получения ссылки выбранный режим передаётся в обработку. После окончания одиночного трека или всего плейлиста состояние сохраняется, и бот снова показывает меню/сообщение ожидания.

Архив

Архив тоже закладываем сразу:

Telegram archive
├── обычные
└── без цензуры

Я бы не стал использовать темы как основу первой версии. Два отдельных канала технически проще и надёжнее: бот однозначно знает, из какого архива брать файл. Пользовательские MP3 при этом вообще не получают никаких служебных пометок.

И самое важное: никакого хранения архива MP3 на ноутбуке.

Но сначала нужен последний вывод выше. После него я уже смогу собрать патч так, чтобы не переделывать его повторно из-за особенностей текущего find_and_download_track().
[27.08.2026 16:13] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginefindstr /n /i /c:"callback" /c:"reply_markup" /c:"inline_keyboard" /c:"answerCallbackQuery" /c:"send_document" /c:"send_audio" bot.py
1000:def send_audio(
1015:def send_document(
1911: upload_result = send_audio(

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginepowershell -NoProfile -Command "$p=Get-Content downloader.py; $p[3880..4245]"
"РєР°РЅРґРёРґР°С‚ РїСЂРѕС€С‘Р» РїСЂРѕРІРµСЂРєСѓ."
)

return best_url

def find_and_download_track(
artist,
title,
duration,
output_folder,
source_url,
source,
youtube_age_restricted=False
):
print()
print("=" * 60)
print("РџРћРРЎРљ РђРЈР”РРћР¤РђР™Р›Рђ")
print("=" * 60)

filename = (
f"{safe_filename(artist)} - "
f"{safe_filename(title)}.mp3"
)

filepath = os.path.join(
output_folder,
filename
)

# ========================================================
# 1. SOUNDCLOUD
# ========================================================

status(
"РџСЂРѕРІРµСЂРєР° SoundCloud..."
)

result = search_soundcloud(
artist,
title,
duration
)

if result:
soundcloud_candidates = [
result
]

alternatives = result.get(
"alternatives",
[]
)

if isinstance(
alternatives,
list
):
soundcloud_candidates.extend(
alternatives
)

soundcloud_candidates = (
soundcloud_candidates[:5]
)

print(
"SoundCloud: РєР°РЅРґРёРґР°С‚РѕРІ "
"РґР»СЏ РїСЂРѕРІРµСЂРєРё: "
f"{len(soundcloud_candidates)}"
)

for candidate_index, candidate_result in enumerate(
soundcloud_candidates,
1
):
print()
print(
"SoundCloud: РїСЂРѕРІРµСЂРєР° РєР°РЅРґРёРґР°С‚Р° "
f"{candidate_index}/"
f"{len(soundcloud_candidates)}"
)

print(
"SoundCloud: score: "
f"{candidate_result.get('score', 0):.1f}"
)

print(
"SoundCloud: РЅР°Р·РІР°РЅРёРµ РєР°РЅРґРёРґР°С‚Р°: "
f"{candidate_result.get('title', '')}"
)

print(
"SoundCloud: РёСЃРїРѕР»РЅРёС‚РµР»СЊ РєР°РЅРґРёРґР°С‚Р°: "
f"{candidate_result.get('artist', '')}"
)

candidate_url = (
candidate_result.get(
"url"
)
)

if not candidate_url:
print(
"SoundCloud: Сѓ РєР°РЅРґРёРґР°С‚Р° "
"РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ URL. РџСЂРѕРїСѓСЃРє."
)
continue

if download_from_soundcloud(
candidate_url,
filepath,
duration,
candidate_result.get(
"exact_match",
False
)
):
print(
"SoundCloud: РєР°РЅРґРёРґР°С‚ "
f"{candidate_index} РїРѕРґС…РѕРґРёС‚."
)

return filepath

print(
"SoundCloud: РєР°РЅРґРёРґР°С‚ "
f"{candidate_index} РЅРµ РїРѕРґРѕС€С‘Р»."
)

print(
"SoundCloud: РІСЃРµ РєР°РЅРґРёРґР°С‚С‹ "
"РЅРµ РїРѕРґРѕС€Р»Рё."
)

# ========================================================
# 2. MP3PARTY
# ========================================================

status(
"РџСЂРѕРІРµСЂРєР° MP3Party..."
)

result = search_mp3party(
artist,
title,
duration
)

if result and download_file(
result["url"],
filepath,
result["referer"],
MP3PARTY_RETRIES
):
return filepath

# ========================================================
# 3. MP3TM
# ========================================================

status(
"РџСЂРѕРІРµСЂРєР° MP3TM..."
)

result = search_mp3tm(
artist,
title,
duration
)
[27.08.2026 16:13] Константин: if result and download_file(
result["url"],
filepath,
result["referer"],
2
):
return filepath

# ========================================================
# 4. AUDIOSTART
# ========================================================

status(
"РџСЂРѕРІРµСЂРєР° AudioStart..."
)

result = search_audiostart(
artist,
title,
duration
)

if result and download_file(
result["url"],
filepath,
result["referer"],
2
):
return filepath

# ========================================================
# 5. YOUTUBE / YT-DLP
# ========================================================

print()
print(
"YouTube fallback: "
"РїСЂРѕРІРµСЂРєР° С„РёРЅР°Р»СЊРЅРѕРіРѕ СЌС‚Р°РїР°..."
)

print(
"YouTube fallback: "
f"source = {source!r}"
)

print(
"YouTube fallback: "
f"source_url = {source_url!r}"
)

print(
"YouTube fallback: "
f"youtube_age_restricted = "
f"{youtube_age_restricted!r}"
)

# --------------------------------------------------------
# РЎС†РµРЅР°СЂРёР№ 1:
# РСЃС…РѕРґРЅР°СЏ СЃСЃС‹Р»РєР° YouTube Music.
# Р•СЃР»Рё Р±С‹Р»Рѕ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РІРѕР·СЂР°СЃС‚Р° вЂ”
# yt-dlp РќР• Р·Р°РїСѓСЃРєР°РµРј.
# --------------------------------------------------------

if (
source == "youtube"
and youtube_age_restricted
):
print()
print(
"YouTube fallback: "
"СЃРєР°С‡РёРІР°РЅРёРµ РїСЂРѕРїСѓС‰РµРЅРѕ."
)

print(
"РџСЂРёС‡РёРЅР°: РёСЃС…РѕРґРЅС‹Р№ YouTube "
"Р·Р°РїСЂРѕСЃРёР» РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РІРѕР·СЂР°СЃС‚Р°."
)

# --------------------------------------------------------
# РЎС†РµРЅР°СЂРёР№ 2:
# РћР±С‹С‡РЅР°СЏ YouTube Music Р±РµР· age restriction.
# РСЃРїРѕР»СЊР·СѓРµРј РёСЃС…РѕРґРЅС‹Р№ URL.
# --------------------------------------------------------

elif (
source == "youtube"
and source_url
):
print()
print(
"YouTube fallback: "
"РІРѕР·СЂР°СЃС‚РЅРѕРµ РѕРіСЂР°РЅРёС‡РµРЅРёРµ "
"РЅРµ РѕР±РЅР°СЂСѓР¶РµРЅРѕ."
)

print(
"YouTube fallback: "
"Р·Р°РїСѓСЃРє yt-dlp..."
)

if download_with_ytdlp(
source_url,
filepath
):
print(
"YouTube fallback: "
"Р°СѓРґРёРѕС„Р°Р№Р» СѓСЃРїРµС€РЅРѕ РїРѕР»СѓС‡РµРЅ."
)

return filepath

print(
"YouTube fallback: "
"yt-dlp РЅРµ СЃРјРѕРі СЃРєР°С‡Р°С‚СЊ "
"Р°СѓРґРёРѕС„Р°Р№Р»."
)

# --------------------------------------------------------
# РЎС†РµРЅР°СЂРёР№ 3:
# РСЃС…РѕРґРЅР°СЏ СЃСЃС‹Р»РєР° РЇРЅРґРµРєСЃ РњСѓР·С‹РєРё.
#
# РџСЂСЏРјРѕРµ СЃРєР°С‡РёРІР°РЅРёРµ СЃ РЇРЅРґРµРєСЃР° РќР• РёСЃРїРѕР»СЊР·СѓРµРј.
# РС‰РµРј СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РёР№ С‚СЂРµРє РЅР° YouTube
# РїРѕ Р°СЂС‚РёСЃС‚Сѓ + РЅР°Р·РІР°РЅРёСЋ.
# --------------------------------------------------------

elif source == "yandex":
print()
print(
"YouTube fallback: "
"РёСЃС…РѕРґРЅС‹Р№ РёСЃС‚РѕС‡РЅРёРє вЂ” РЇРЅРґРµРєСЃ РњСѓР·С‹РєР°."
)

print(
"YouTube fallback: "
"РїРѕРёСЃРє СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РµРіРѕ С‚СЂРµРєР° "
"РЅР° YouTube РїРѕ РјРµС‚Р°РґР°РЅРЅС‹Рј."
)

fallback_url = (
find_youtube_fallback_url(
artist,
title,
duration
)
)

if fallback_url:
print(
"YouTube fallback: "
"Р·Р°РїСѓСЃРє yt-dlp..."
)

if download_with_ytdlp(
fallback_url,
filepath
):
print(
"YouTube fallback: "
"Р°СѓРґРёРѕС„Р°Р№Р» СѓСЃРїРµС€РЅРѕ РїРѕР»СѓС‡РµРЅ."
)

return filepath

print(
"YouTube fallback: "
"yt-dlp РЅРµ СЃРјРѕРі СЃРєР°С‡Р°С‚СЊ "
"РЅР°Р№РґРµРЅРЅС‹Р№ YouTube-С‚СЂРµРє."
)
[27.08.2026 16:13] Константин: else:
print()
print(
"YouTube fallback: "
"РЅРµ Р·Р°РїСѓС‰РµРЅ вЂ” РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ "
"РїРѕРґС…РѕРґСЏС‰РёР№ РёСЃС‚РѕС‡РЅРёРє."
)

print(
"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРєР°С‡Р°С‚СЊ "
"РїРѕРґС…РѕРґСЏС‰РёР№ Р°СѓРґРёРѕС„Р°Р№Р»."
)

return None

SINGLE TRACK

def process_single_track(
url,
output_folder,
youtube_retries=1,
return_failure=False
[27.08.2026 16:14] Константин: Да. Теперь картина по bot.py и downloader.py достаточно полная, чтобы двигаться дальше.

Я вижу текущую архитектуру:

bot.py

Сейчас он отвечает сразу за несколько вещей:

Telegram API;

статусные сообщения;

определение типа ссылки;

обработку одиночного трека;

обработку Yandex-плейлистов;

обработку YouTube Music-плейлистов;

запуск downloader.find_and_download_track();

отправку готового MP3 в Telegram.


При этом логика источников MP3 в bot.py не находится, что хорошо.

downloader.py

Сейчас find_and_download_track() фактически является главным маршрутизатором:

SoundCloud
↓
MP3Party
↓
MP3TM
↓
AudioStart
↓
YouTube / yt-dlp

Именно эту часть я бы сейчас и разделял.

Причём важно: порядок источников и существующее поведение пока не менять. Разделяем код физически, но оставляем тот же результат.

Предлагаемая структура:

engine/
│
├── bot.py
├── downloader.py
│
├── sources/
│ ├── init.py
│ ├── soundcloud.py
│ ├── mp3party.py
│ ├── mp3tm.py
│ └── audiostart.py
│
└── ...

И далее:

downloader.py
│
├── получение metadata YouTube/Yandex
├── LRC
├── cover / ID3
├── общие функции
│
└── find_and_download_track()
│
├── sources.soundcloud
├── sources.mp3party
├── sources.mp3tm
└── sources.audiostart

Что особенно важно по присланному коду

process_single_track() уже нормально использует:

find_and_download_track(...)

То есть боту вообще не нужно знать, откуда скачивается MP3.

Это хороший уровень абстракции. Поэтому bot.py я бы пока вообще не трогал.

Также find_and_download_track() сейчас содержит непосредственно вызовы:

search_soundcloud(...)
download_from_soundcloud(...)

search_mp3party(...)
download_file(...)

search_mp3tm(...)
download_file(...)

search_audiostart(...)
download_file(...)

Вот это и есть естественная граница для выноса.

Следующий шаг я бы сделал не патчем вслепую. Сначала снимем точные границы функций каждого источника — SoundCloud, MP3Party, MP3TM, AudioStart — чтобы автоматический патч не зацепил общие функции и зависимости.

Присылай следующую часть downloader.py с этими функциями. После этого я смогу собрать один автоматический патч с backup + AST/compile-проверкой + проверкой импортов, в том же стиле, как мы делали раньше.
[27.08.2026 16:14] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginepowershell -NoProfile -Command "Select-String -Path downloader.py -Pattern '^def (search_soundcloud|download_from_soundcloud|evaluate_soundcloud_candidate|fetch_soundcloud_results|normalize_soundcloud_metadata|search_mp3party|search_mp3tm|search_audiostart|download_file)' | ForEach-Object { '{0}: {1}' -f $.LineNumber, $.Line }"
3103: def download_file(

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\enginepowershell -NoProfile -Command "$p=Get-Content downloader.py; $p[0..180]"
import requests
import re
import html
import base64
import json
import subprocess
import os
import time
import io
from urllib.parse import unquote

from sources_soundcloud import (
search_soundcloud,
download_from_soundcloud,
)

from sources_mp3party import search_mp3party
from sources_mp3tm import search_mp3tm
from sources_audiostart import search_audiostart

ENGINE_FOLDER = os.path.dirname(
os.path.abspath(file)
)

PROJECT_FOLDER = os.path.dirname(
ENGINE_FOLDER
)

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

TRACKS_FOLDER = os.path.join(
PROJECT_FOLDER,
"tracks"
)

try:
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
MUTAGEN_AVAILABLE = True
except ImportError:
MUTAGEN_AVAILABLE = False

try:
from PIL import Image
PIL_AVAILABLE = True
except ImportError:
PIL_AVAILABLE = False

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/139.0.0.0 Safari/537.36"
),
"Accept": (
"text/html,application/xhtml+xml,application/xml;"
"q=0.9,image/avif,image/webp,/;q=0.8"
),
"Accept-Language": (
"ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
),
"Connection": "keep-alive"
}

YANDEX_HEADERS = {
"User-Agent": HEADERS["User-Agent"],
"Accept": "application/json, text/plain, /",
"Accept-Language": HEADERS["Accept-Language"],
"Referer": "https://music.yandex.ru/"
}

TIMEOUT = 20
MIN_FILE_SIZE = 10 * 1024
MP3PARTY_RETRIES = 3
DOWNLOAD_LRC = False
LRCLIB_DELAY = 1.0
DURATION_TOLERANCE = 3.0

YOUTUBE_INFO_RETRIES = 3

YOUTUBE_INFO_RETRY_DELAYS = (
2,
5
)

РџРѕСЃР»РµРґРЅСЏСЏ РґРёР°РіРЅРѕСЃС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР° yt-dlp.

Р’Р°Р¶РЅРѕ:

age restriction РЅРµ СЃС‡РёС‚Р°РµС‚СЃСЏ РѕРєРѕРЅС‡Р°С‚РµР»СЊРЅРѕР№ РѕС€РёР±РєРѕР№,

РµСЃР»Рё РїРѕР·Р¶Рµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РјРµС‚Р°РґР°РЅРЅС‹Рµ РёР»Рё СЃРєР°С‡Р°С‚СЊ С„Р°Р№Р».

LAST_YOUTUBE_ERROR = ""

РљР­РЁ SOUNDCLOUD CLIENT ID

def status(message):
print()
print(message)

def normalize(text):
text = html.unescape(str(text))
text = unquote(text)
text = text.replace("вЂ“", "-").replace("вЂ”", "-").replace("_", " ")
text = re.sub(r"\(MP3.tm\)", "", text, flags=re.I)
text = re.sub(r"\(audiostart.net\)", "", text, flags=re.I)
text = re.sub(r".mp3$", "", text, flags=re.I)
text = text.lower()
text = re.sub(r"\bof\s+buda\b", "og buda", text)
text = re.sub(r"\bfeaturing\b", "feat", text)
text = re.sub(r"\bft.?\b", "feat", text)
text = re.sub(r"\bfeat.?\b", " ", text)
text = re.sub(r"[,;|/\]+", " ", text)
text = re.sub(r"[()[]{}]", " ", text)
return re.sub(r"\s+", " ", text).strip()

def normalize_words(text):
return {
word
for word in normalize(text).split()
if word
}

def clean_search_query(text):
text = re.sub(
r"\(feat.[^)]+\)",
"",
text,
flags=re.I
)

text = re.sub(
r"feat\.[^]+\]",
"",
text,
flags=re.I
)

text = re.sub(
r"ft\.[^)]+",
"",
text,
flags=re.I
)

text = re.sub(
r"[()[\]{}]",
" ",
text
)

return re.sub(
r"\s+",
" ",
text
).strip()

def clean_filename(text):
text = unquote(text)

text = re.sub(
r"MP3\.tm\.mp3$",
"",
text,
[27.08.2026 16:14] Константин: Отлично. И здесь уже есть важный факт: источники уже вынесены из downloader.py на уровень импортов:

sources_soundcloud.py
sources_mp3party.py
sources_mp3tm.py
sources_audiostart.py

То есть перенос, который мы собирались делать, уже выполнен. downloader.py сейчас выступает как оркестратор и импортирует источники:

from sources_soundcloud import (
search_soundcloud,
download_from_soundcloud,
)

from sources_mp3party import search_mp3party
from sources_mp3tm import search_mp3tm
from sources_audiostart import search_audiostart

Поэтому сейчас ничего переносить не надо.

Но команда Select-String показала только download_file(), потому что регулярка ищет именно ^def, а импортированные функции физически находятся в отдельных файлах. Это как раз подтверждает структуру.

Что я предлагаю проверить сейчас

Нужно убедиться, что все четыре отдельных файла действительно существуют и корректно импортируются, а не просто прописаны в downloader.py.

Выполни:

powershell -NoProfile -Command "Get-ChildItem -Name sources_*.py; Write-Host ''; python -c "import sources_soundcloud, sources_mp3party, sources_mp3tm, sources_audiostart; print('ALL SOURCE IMPORTS: OK')""

И отдельно:

python -m py_compile sources_soundcloud.py sources_mp3party.py sources_mp3tm.py sources_audiostart.py downloader.py bot.py

Пришли вывод обеих команд.

Если обе проверки пройдут, структура источников уже отделена нормально, и следующим шагом имеет смысл не переносить код, а проверить зависимости каждого sources_*.py: чтобы, например, sources_mp3party.py не зависел случайно от внутренних переменных downloader.py.
[27.08.2026 16:17] Константин: Да, тут первая команда сломалась только из-за кавычек CMD, а не из-за Python.

Вторая команда прошла: py_compile не сообщил ни одной SyntaxError. Есть только предупреждение в downloader.py:2724 про \/.

И ещё важный момент: у тебя появился sources_utils.py. Это хорошо — значит, при разделении источников мы уже вынесли и общие функции.

Теперь нужно проверить реальные зависимости между модулями. Это важнее, чем просто импорт.

Выполни по очереди эти команды:

python -c "import sources_utils; print('sources_utils: OK')"

python -c "import sources_soundcloud; print('sources_soundcloud: OK')"

python -c "import sources_mp3party; print('sources_mp3party: OK')"

python -c "import sources_mp3tm; print('sources_mp3tm: OK')"

python -c "import sources_audiostart; print('sources_audiostart: OK')"

И затем главное:

python -c "import downloader; print('downloader: OK')"

Что нам нужно получить

В идеале:

sources_utils: OK
sources_soundcloud: OK
sources_mp3party: OK
sources_mp3tm: OK
sources_audiostart: OK
downloader: OK

Если какая-нибудь команда выдаст ImportError, NameError или другую ошибку — ничего пока не исправляй, просто пришли полный вывод.

Предупреждение:

downloader.py:2724: SyntaxWarning: "\/" is an invalid escape sequence

пока не трогаем. Это отдельная мелочь, она не мешает компиляции. Сначала проверим архитектуру после разделения источников.
[27.08.2026 16:17] Константин: Отлично. Значит, после выноса источников базовая структура сейчас целая:

sources_soundcloud.py — импортируется.

sources_mp3party.py — импортируется.

sources_mp3tm.py — импортируется.

sources_audiostart.py — импортируется.

sources_utils.py — импортируется.

downloader.py — импортируется.

bot.py — успешно проходит py_compile.


И главное: в downloader.py уже действительно используются отдельные модули:

from sources_soundcloud import ...
from sources_mp3party import ...
from sources_mp3tm import ...
from sources_audiostart import ...

То есть этап физического разделения источников выполнен нормально.

Следующим шагом я бы не стал сразу что-либо переписывать. Сначала нужно проверить, что каждый источник функционально работает через новую архитектуру, а не только импортируется.

Я бы проверил в таком порядке:

1. SoundCloud — поиск + скачивание.


2. MP3Party — поиск + скачивание.


3. MP3TM — поиск + скачивание.


4. AudioStart — поиск + скачивание.


5. Затем полный process_single_track().


6. После этого — один реальный трек через bot.py.



Так мы сразу увидим, не потерялась ли какая-нибудь функция/переменная при переносе.
[27.08.2026 16:17] Константин: Давай. Начинаем с безопасной функциональной проверки, ничего в коде пока не меняем.

Сначала проверим, какие публичные функции реально находятся в каждом модуле. Выполни одну команду:

python -c "import sources_soundcloud as sc, sources_mp3party as party, sources_mp3tm as tm, sources_audiostart as audio; print('SOUNDCLOUD:', [x for x in dir(sc) if not x.startswith('_')]); print('MP3PARTY:', [x for x in dir(party) if not x.startswith('_')]); print('MP3TM:', [x for x in dir(tm) if not x.startswith('_')]); print('AUDIOSTART:', [x for x in dir(audio) if not x.startswith('_')])"

Пришли весь вывод.

После этого я дам тест именно для поиска/скачивания, уже с учётом фактических сигнатур функций. Не будем придумывать аргументы и рисковать поломать рабочий downloader.
[27.08.2026 16:18] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>python -c "import sources_soundcloud as sc, sources_mp3party as party, sources_mp3tm as tm, sources_audiostart as audio; print('SOUNDCLOUD:', [x for x in dir(sc) if not x.startswith('')]); print('MP3PARTY:', [x for x in dir(party) if not x.startswith('')]); print('MP3TM:', [x for x in dir(tm) if not x.startswith('')]); print('AUDIOSTART:', [x for x in dir(audio) if not x.startswith('')])"
SOUNDCLOUD: ['ENGINE_FOLDER', 'EXACT_MATCH_TOLERANCE', 'FFMPEG', 'FFPROBE', 'HEADERS', 'MIN_FILE_SIZE', 'SOUNDCLOUD_CLIENT_ID_CACHE', 'SOUNDCLOUD_CLIENT_ID_TIMEOUT', 'SOUNDCLOUD_DOWNLOAD_TIMEOUT', 'SOUNDCLOUD_DURATION_TOLERANCE', 'SOUNDCLOUD_HEADERS', 'SOUNDCLOUD_SEARCH_RESULTS', 'SOUNDCLOUD_SEARCH_TIMEOUT', 'SOUNDCLOUD_SEARCH_URL', 'SOUNDCLOUD_SERVICE_MODIFIERS', 'YTDLP', 'clean_soundcloud_text', 'download_from_soundcloud', 'evaluate_soundcloud_candidate', 'fetch_soundcloud_results', 'get_soundcloud_client_id', 'get_soundcloud_full_stream_url', 'get_soundcloud_track_info', 'html', 'is_soundcloud_confirmed_preview', 'normalize', 'normalize_soundcloud_metadata', 'normalize_words', 'os', 're', 'requests', 'search_soundcloud', 'shutil', 'soundcloud_candidate_score', 'soundcloud_is_preview_only', 'soundcloud_query_variants', 'subprocess', 'unquote']
MP3PARTY: ['DURATION_TOLERANCE', 'ENGINE_FOLDER', 'FFPROBE', 'HEADERS', 'TIMEOUT', 'candidate_text_score', 'get_duration', 'html', 'is_duration_acceptable', 'os', 're', 'requests', 'search_mp3party', 'subprocess']
MP3TM: ['HEADERS', 'TIMEOUT', 'candidate_text_score', 'clean_filename', 'get_duration', 'html', 'is_duration_acceptable', 're', 'requests', 'search_mp3tm']
AUDIOSTART: ['HEADERS', 'TIMEOUT', 'base64', 'candidate_text_score', 'get_duration', 'html', 'is_duration_acceptable', 're', 'requests', 'search_audiostart', 'unquote']
[27.08.2026 16:18] Константин: Отлично. Теперь видно, что разделение сделано не поверхностно: функции поиска действительно находятся в отдельных модулях, а SoundCloud дополнительно содержит весь свой внутренний набор функций.

Следующий шаг — проверить сигнатуры. Это позволит дать точный тест без догадок.

Выполни:

python -c "import inspect, sources_soundcloud as sc, sources_mp3party as party, sources_mp3tm as tm, sources_audiostart as audio; print('--- SOUNDCLOUD ---'); print('search_soundcloud:', inspect.signature(sc.search_soundcloud)); print('download_from_soundcloud:', inspect.signature(sc.download_from_soundcloud)); print('--- MP3PARTY ---'); print('search_mp3party:', inspect.signature(party.search_mp3party)); print('--- MP3TM ---'); print('search_mp3tm:', inspect.signature(tm.search_mp3tm)); print('--- AUDIOSTART ---'); print('search_audiostart:', inspect.signature(audio.search_audiostart))"

Пришли вывод.

Пока реальные скачивания не запускаем. Сначала зафиксируем интерфейсы модулей. Затем сделаем тест поиска на одном конкретном треке и проверим, что каждый источник возвращает именно тот формат результата, который ожидает find_and_download_track().
[27.08.2026 16:18] Константин: --- SOUNDCLOUD ---
search_soundcloud: (artist, title, duration=None)
download_from_soundcloud: (soundcloud_url, filepath, target_duration=None, exact_match=False)
--- MP3PARTY ---
search_mp3party: (artist, title, target_duration=None)
--- MP3TM ---
search_mp3tm: (artist, title, target_duration=None)
--- AUDIOSTART ---
search_audiostart: (artist, title, target_duration=None)
[27.08.2026 16:18] Константин: Да. Интерфейсы совпадают с тем, как find_and_download_track() их вызывает. Следовательно, следующий шаг — реальный поиск без скачивания.

Нам нужен один тестовый трек, который мы уже знаем. Возьмём конкретный трек из твоих предыдущих тестов — но чтобы не угадывать его название, лучше сначала получить его метаданные из downloader.py.

Выполни:

python -c "import downloader; url=input('URL трека: ').strip(); info=downloader.get_track_info(url); print(); print('RESULT:'); print(info)"

Вставь туда одну рабочую ссылку на YouTube Music или Яндекс Музыку.

Пришли весь результат RESULT:.

После этого я дам один диагностический скрипт, который:

возьмёт artist/title/duration;

отдельно вызовет search_soundcloud();

отдельно search_mp3party();

отдельно search_mp3tm();

отдельно search_audiostart();

ничего не скачает;

покажет, какой источник нашёл кандидата и что именно вернул.


Это будет чистая проверка нового разделения источников перед реальным скачиванием.
[27.08.2026 16:18] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>python -c "import downloader; url=input('URL трека: https://music.youtube.com/watch?v=NrVkY2niE6k').strip(); info=downloader.get_track_info(url); print(); print('RESULT:'); print(info)"
URL трека: https://music.youtube.com/watch?v=NrVkY2niE6k

Получение информации из YouTube Music...

Получение метаданных непосредственно со страницы YouTube Music...

Не удалось получить информацию о треке.
Диагностика yt-dlp:
ERROR: [generic] '' is not a valid URL

RESULT:
None

Я ссылку неправильно вставил?
[27.08.2026 16:19] Константин: C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>python -c "import sources_soundcloud as sc, sources_mp3party as party, sources_mp3tm as tm, sources_audiostart as audio; artist='Voskresenskii'; title='Стиралка'; duration=101; print('='*70); print('SOUNDCLOUD'); print('='*70); print(sc.search_soundcloud(artist,title,duration)); print(); print('='*70); print('MP3PARTY'); print('='*70); print(party.search_mp3party(artist,title,duration)); print(); print('='*70); print('MP3TM'); print('='*70); print(tm.search_mp3tm(artist,title,duration)); print(); print('='*70); print('AUDIOSTART'); print('='*70); print(audio.search_audiostart(artist,title,duration))"

SOUNDCLOUD

SoundCloud: запуск поиска...
SoundCloud: исполнитель: Voskresenskii
SoundCloud: название: Стиралка
SoundCloud: длительность: 101
SoundCloud: нормализованный исполнитель: Voskresenskii
SoundCloud: исходное название: Стиралка
SoundCloud: очищенное название: Стиралка
SoundCloud: основной исполнитель для fallback-поиска: Voskresenskii
SoundCloud: базовое очищенное название для fallback-поиска: Стиралка
SoundCloud: client_id получен.


---

SoundCloud: ЭТАП 1/4
SoundCloud: режим: исполнитель + очищенное название
SoundCloud: поисковый запрос: Voskresenskii Стиралка
SoundCloud: максимум результатов: 50

SoundCloud API: HTTP-код: 200
SoundCloud API: размер ответа: 21990 байт
SoundCloud API: collection = 5
SoundCloud: получено результатов: 5
SoundCloud: подходящих кандидатов на этом этапе: 1

SoundCloud: КАНДИДАТ НАЙДЕН.
SoundCloud: этап: 1/4
SoundCloud: запрос: Voskresenskii Стиралка
SoundCloud: score: 1000.0
SoundCloud: название кандидата: Стиралка
SoundCloud: исполнитель кандидата: Voskresenskii
SoundCloud: URL: https://soundcloud.com/voskresenskii/stiralka-2
SoundCloud: используем результат этапа 1.
{'url': 'https://soundcloud.com/voskresenskii/stiralka-2', 'title': 'Стиралка', 'artist': 'Voskresenskii', 'duration': 99415, 'score': 1000.0, 'candidate': {'artwork_url': 'https://i1.sndcdn.com/artworks-gCJ8ztiEARledzj9-VXsdXg-large.jpg', 'caption': None, 'commentable': True, 'comment_count': 52, 'created_at': '2026-08-13T21:09:22Z', 'description': '', 'downloadable': False, 'download_count': 0, 'duration': 99415, 'full_duration': 99369, 'embeddable_by': 'all', 'genre': '', 'has_downloads_left': False, 'id': 2381308074, 'kind': 'track', 'label_name': '', 'last_modified': '2026-08-13T21:09:22Z', 'license': 'all-rights-reserved', 'likes_count': 2580, 'permalink': 'stiralka-2', 'permalink_url': 'https://soundcloud.com/voskresenskii/stiralka-2', 'playback_count': 74052, 'public': True, 'publisher_metadata': {'id': 2381308074, 'urn': 'soundcloud:tracks:2381308074', 'artist': 'Voskresenskii', 'publisher': '', 'explicit': False}, 'purchase_title': None, 'purchase_url': None, 'release_date': None, 'reposts_count': 16, 'secret_token': None, 'sharing': 'public', 'state': 'finished', 'streamable': True, 'tag_list': '', 'title': 'Стиралка', 'uri': 'https://api.soundcloud.com/tracks/soundcloud%3Atracks%3A2381308074', 'urn': 'soundcloud:tracks:2381308074', 'user_id': 1329782949, 'visuals': None, 'waveform_url': 'https://wave.sndcdn.com/4lttRJ0sZR7l_m.json', 'display_date': '2026-08-13T21:09:22Z', 'media': {'transcodings': [{'url': 'https://api-v2.soundcloud.com/media/soundcloud:tracks:2381308074/3c4119d9-f569-4f54-9fa1-557ba685655b/stream/hls', 'preset': 'aac_160k', 'duration': 99415, 'snipped': False, 'format': {'protocol': 'hls', 'mime_type': 'audio/mp4; codecs="mp4a.40.2"'}, 'quality': 'sq', 'is_legacy_transcoding': False}, {'url': 'https://api-v2.soundcloud.com/media/soundcloud:tracks:2381308074/9d30e1ef-343f-4388-8945-dbd08e6771d7/stream/hls', 'preset': 'aac_96k', 'duration': 99415, 'snipped': False, 'format': {'protocol': 'hls', 'mime_type': 'audio/mp4; codecs="mp4a.40.2"'}, 'quality': 'lq', 'is_legacy_transcoding': False}, {'url': 'https://api-v2.soundcloud.com/media/soundcloud:tracks:2381308074/0bf7ba3e-6e4a-42f1-8772-a8bb2c6b0ebe/stream/hls', 'preset': 'abr_sq', 'duration': 99415, 'snipped': False, 'format': {'protocol': 'hls', 'mime_type': 'audio/mpegurl'},
[27.08.2026 16:19] Константин: 'quality': 'sq', 'is_legacy_transcoding': False}, {'url': 'https://api-v2.soundcloud.com/media/soundcloud:tracks:2381308074/8beb5335-1560-41d7-98ad-ab9ce9e487d1/stream/hls', 'preset': 'mp3_1_0', 'duration': 99369, 'snipped': False, 'format': {'protocol': 'hls', 'mime_type': 'audio/mpeg'}, 'quality': 'sq', 'is_legacy_transcoding': True}, {'url': 'https://api-v2.soundcloud.com/media/soundcloud:tracks:2381308074/8beb5335-1560-41d7-98ad-ab9ce9e487d1/stream/progressive', 'preset': 'mp3_1_0', 'duration': 99369, 'snipped': False, 'format': {'protocol': 'progressive', 'mime_type': 'audio/mpeg'}, 'quality': 'sq', 'is_legacy_transcoding': True}]}, 'station_urn': 'soundcloud:system-playlists:track-stations:2381308074', 'station_permalink': 'track-stations:2381308074', 'track_authorization': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJnZW8iOiJSVSIsInN1YiI6IiIsInJpZCI6IjNlMTRjNjkxLTNmOWEtNGYzNi1iOGVlLWE5MjlkMzE0NzNhNSIsImlhdCI6MTc4NzgyODg5OX0.Fan1fRLMADM5JUD1KatZXnuMflB3gsQh95Xd1hwC5Wo', 'monetization_model': 'NOT_APPLICABLE', 'policy': 'ALLOW', 'user': {'avatar_url': 'https://i1.sndcdn.com/avatars-unGdlcEzOOmDR69S-EZ4qJQ-large.jpg', 'city': None, 'comments_count': 0, 'country_code': None, 'created_at': None, 'creator_subscriptions': [{'product': {'id': 'free'}}], 'creator_subscription': {'product': {'id': 'free'}}, 'description': None, 'followers_count': 21239, 'followings_count': 2, 'first_name': 'Воскресенский', 'full_name': 'Воскресенский', 'groups_count': 0, 'id': 1329782949, 'kind': 'user', 'last_modified': '2026-08-06T22:25:27Z', 'last_name': '', 'likes_count': 0, 'playlist_likes_count': 0, 'permalink': 'voskresenskii', 'permalink_url': 'https://soundcloud.com/voskresenskii', 'playlist_count': 9, 'reposts_count': None, 'track_count': 139, 'uri': 'https://api.soundcloud.com/users/soundcloud%3Ausers%3A1329782949', 'urn': 'soundcloud:users:1329782949', 'username': 'Voskresenskii', 'verified': False, 'visuals': None, 'badges': {'pro': False, 'creator_mid_tier': False, 'pro_unlimited': False, 'verified': False}, 'station_urn': 'soundcloud:system-playlists:artist-stations:1329782949', 'station_permalink': 'artist-stations:1329782949', 'date_of_birth': None}}, 'search_stage': 1, 'search_query': 'Voskresenskii Стиралка', 'exact_match': True, 'alternatives': []}

======================================================================
MP3PARTY

{'url': 'https://dl2.mp3party.net/download/11732188', 'referer': 'https://mp3party.net/music/11732188'}

======================================================================
MP3TM

{'url': 'https://fine.sunproxy.net/file/ZjZ4WituRFp0bzBiQ281NEZ6L3FzWlpCcmxSVlZSMEs5MjRVcHE0Sm9xN2R2alR0enpURk90WE1Md08yRkxENVh6cDdXNlNQVVAvbmpQamhQZmcwaTAyNU8wZVZqcGtHTHN1aXh5ekk0azg9/Voskresenskii_-Stiralka(MP3.tm).mp3', 'referer': 'https://voskresenskii-стиралка.mp3tm.net/'}

======================================================================
AUDIOSTART

{'url': 'https://audiostart.net/getmp3/MC9ORGMwTkRrNU1qRXlYelExTmprMk56STRNVjlpT1RJNFlqRm1NV1EyTm1JNVpqRmlZbVZmTVdFeE5ERTJPRGszTW1Sa09HWTJZVGN4THp3aGZDRS1XeUpuY3lJc09Dd2lWbTl6YTNKbGMyVnVjMnRwYVNzbFJEQWxRVEVsUkRFbE9ESWxSREFsUWpnbFJERWxPREFsUkRBbFFqQWxSREFsUWtJbFJEQWxRa0VsUkRBbFFqQWlMREVzYm5Wc2JDd3dMRFV3TERCZC9Wb3NrcmVzZW5za2lpKy0rJUQwJUExJUQxJTgyJUQwJUI4JUQxJTgwJUQwJUIwJUQwJUJCJUQwJUJBJUQwJUIwXyhhdWRpb3N0YXJ0Lm5ldCkvVm9za3Jlc2Vuc2tpaSslRTIlODAlOTMrJUQwJUExJUQxJTgyJUQwJUI4JUQxJTgwJUQwJUIwJUQwJUJCJUQwJUJBJUQwJUIwXyhhdWRpb3N0YXJ0Lm5ldCk/cz12ayZyPSZjb29raWVzPTc5NjE0OTc0MjU0XzEuY29va2ll', 'referer': 'https://audiostart.net/'}
[27.08.2026 16:19] Константин: Отлично. Теперь картина ясная:

sources_soundcloud.py — импортируется, поиск работает.

sources_mp3party.py — поиск работает.

sources_mp3tm.py — поиск работает.

sources_audiostart.py — поиск работает.

Все четыре источника реально находят этот конкретный трек.

downloader.py уже использует новые модули через импорты.

То есть разделение поиска по источникам фактически завершено.


Следующий правильный шаг — не патчить дальше вслепую, а проверить именно скачивание из каждого источника. Особенно важно убедиться, что после выноса функций ничего не сломалось в download-части.

Сначала дай один точный вывод:

python -c "import downloader, inspect; print('download_file:', inspect.signature(downloader.download_file)); print('find_and_download_track:', inspect.signature(downloader.find_and_download_track))"

После этого я дам тест скачивания SoundCloud → MP3Party → MP3TM → AudioStart в отдельную временную папку, не затрагивая основной tracks и не меняя код. Если все четыре проходят — тогда уже можно делать финальную чистку downloader.py.
