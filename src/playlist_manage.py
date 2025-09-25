import os
import random
from dotenv import load_dotenv

load_dotenv()

PLAYLIST_FOLDER = os.getenv("PLAYLIST_FOLDER")
if not PLAYLIST_FOLDER:
    raise ValueError("PLAYLIST_FOLDER environment variable is not set")
if not os.path.exists(PLAYLIST_FOLDER):
    raise ValueError(f"PLAYLIST_FOLDER path does not exist: {PLAYLIST_FOLDER}")

async def check_playlist_exists(playlist_name: str) -> tuple[bool, str | None]:
    playlist_path = os.path.join(PLAYLIST_FOLDER, f"{playlist_name}.mp3")
        
    if not os.path.exists(playlist_path):
        found = False
        for ext in ['.wav', '.ogg', '.m4a']:
            temp_path = os.path.join(PLAYLIST_FOLDER, f"{playlist_name}{ext}")
            if os.path.exists(temp_path):
                playlist_path = temp_path
                found = True
                break
        if not found:
            return False, None
    
    return True, playlist_path

async def get_all_songs() -> list[str]:
    all_songs = []
    for file in os.listdir(PLAYLIST_FOLDER):
        if file.endswith(('.mp3', '.wav', '.ogg', '.m4a')):
            all_songs.append(os.path.join(PLAYLIST_FOLDER, file))
    
    if not all_songs:
        return []
    random.shuffle(all_songs)
    return all_songs