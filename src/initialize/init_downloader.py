from spotdl.download.downloader import Downloader


def init_downloader(downloader_settings) -> Downloader:
    if downloader_settings is None:
        downloader_settings = {}
    downloader = Downloader(
        settings=downloader_settings,
        loop=None,
    )

    return downloader
