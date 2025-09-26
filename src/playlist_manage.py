import os
import random
from dotenv import load_dotenv

load_dotenv()

MUSIC_FOLDER = os.getenv("MUSIC_FOLDER")
if not MUSIC_FOLDER:
    raise ValueError("MUSIC_FOLDER environment variable is not set")
if not os.path.exists(MUSIC_FOLDER):
    raise ValueError(f"MUSIC_FOLDER path does not exist: {MUSIC_FOLDER}")


async def _dir_for(subfolder: str | None) -> str:
    return os.path.join(MUSIC_FOLDER, subfolder) if subfolder else MUSIC_FOLDER


async def check_playlist_exists(
    playlist_name: str, *, subfolder: str | None = None
) -> tuple[bool, str | None]:
    base_dir = await _dir_for(subfolder)
    playlist_path = os.path.join(base_dir, f"{playlist_name}.mp3")

    if not os.path.exists(playlist_path):
        found = False
        for ext in [".wav", ".ogg", ".m4a"]:
            temp_path = os.path.join(base_dir, f"{playlist_name}{ext}")
            if os.path.exists(temp_path):
                playlist_path = temp_path
                found = True
                break
        if not found:
            return False, None

    return True, playlist_path


async def get_all_songs(*, subfolder: str | None = None) -> list[str]:
    base_dir = await _dir_for(subfolder)
    if not os.path.isdir(base_dir):
        return []
    all_songs = []
    for file in os.listdir(base_dir):
        if file.endswith((".mp3", ".wav", ".ogg", ".m4a")):
            all_songs.append(os.path.join(base_dir, file))

    if not all_songs:
        return []
    random.shuffle(all_songs)
    return all_songs
