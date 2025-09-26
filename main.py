import discord
import os
import glob
from dotenv import load_dotenv

from src.initialize.init_spotdl import init_spotdl
from src.initialize.init_bot import init_bot
from src.initialize.init_spotify_client import init_spotify_client
from src.initialize.init_downloader import init_downloader

load_dotenv()

# Opus library setup
opus_paths = [
    "libopus.so",
    "libopus.so.0",
    "/usr/lib/x86_64-linux-gnu/libopus.so.0",
    "/usr/lib/libopus.so.0",
]

# Thêm các đường dẫn từ Nix store nếu có
if "NIX_STORE" in os.environ:
    nix_opus = glob.glob("/nix/store/*/lib/libopus.so*")
    opus_paths.extend(nix_opus)

opus_loaded = False
for path in opus_paths:
    try:
        discord.opus.load_opus(path)
        print(f"Loaded Opus from: {path}")
        opus_loaded = True
        break
    except (discord.opus.OpusNotLoaded, OSError):
        continue

if not opus_loaded:
    print("Warning: Could not load Opus library. Voice features may not work.")

# Main execution
if __name__ == "__main__":
    # Initialize the Spotify Client
    spotify_client = {
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
        "user_auth": False,
        "cache_path": None,
        "no_cache": False,
        "headless": False,
    }
    client = init_spotify_client(spotify_client)

    # Initialize the Downloader
    output_directory = "playlist/spotify"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    downloader_settings = {
        "output": output_directory,
        "format": "mp3",
        "bitrate": "320k",
        "threads": 4,
        "preload": False,
        "m3u_name": "{playlist_name}.m3u",
        "file_name": "{title} - {artist}",  # Format tên file
    }
    downloader = init_downloader(downloader_settings)

    # Initialize the Spotdl
    spotdl = init_spotdl(client, downloader)

    # Initialize the Bot
    bot = init_bot(spotdl)

    song_links = [
        "https://open.spotify.com/track/5IO873C4IP8pXdsXcJiBes?si=2e354799844a47b9",
        "https://open.spotify.com/track/1WbTOu4D2oHK9fg2qR6msd?si=3df438007c6940fb",
    ]

    bot.run_bot()
