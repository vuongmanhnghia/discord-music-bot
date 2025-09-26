from src.bot.main import MusicBot


def init_bot(spotdl_instance) -> MusicBot:
    return MusicBot(spotdl_instance=spotdl_instance)
