from src.bot.main import MusicBot


def init_bot(spotify_client, downloader) -> MusicBot:
    return MusicBot(
        # spotify_client=spotify_client,
        # downloader=downloader,
        # loop=None,
    )
