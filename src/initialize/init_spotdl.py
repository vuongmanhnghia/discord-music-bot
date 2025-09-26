from src.spotdl.main import Spotdl


def init_spotdl(client, downloader) -> Spotdl:
    return Spotdl(
        client=client,
        downloader=downloader,
    )
