"""
Censuru.net source registry.

Единая точка доступа к источникам.

На первом этапе функции вызываются через
downloader.py. После постепенного переноса
реализации этот реестр станет диспетчером
между независимыми модулями.
"""

SOURCE_MODULES = (
    "sources_youtube",
    "sources_yandex",
    "sources_soundcloud",
    "sources_mp3party",
    "sources_mp3tm",
    "sources_audiostart",
)


def get_source_modules():
    return SOURCE_MODULES
