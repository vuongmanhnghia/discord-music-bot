import os

from spotdl.download.downloader import Downloader
from spotdl.utils.spotify import SpotifyClient
from src.spotdl.main import Spotdl

from dotenv import load_dotenv

load_dotenv()


# Danh sách các link Spotify bạn muốn tải
song_links = [
    "https://open.spotify.com/track/5IO873C4IP8pXdsXcJiBes?si=2e354799844a47b9",
    "https://open.spotify.com/track/1WbTOu4D2oHK9fg2qR6msd?si=3df438007c6940fb",
]

# Tạo thư mục nếu chưa tồn tại
output_directory = "playlist/spotify"
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Cài đặt downloader
downloader_settings = {
    "output": output_directory,
    "format": "mp3",
    "bitrate": "320k",
    "threads": 4,
    "preload": False,
    "m3u_name": "{playlist_name}.m3u",
    "file_name": "{title} - {artist}",  # Format tên file
}

if __name__ == "__main__":
    # Khởi tạo SpotifyClient
    client = SpotifyClient.init(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        user_auth=False,
        cache_path=None,
        no_cache=False,
        headless=False,
    )

    # Initialize Downloader
    if downloader_settings is None:
        downloader_settings = {}
    downloader = Downloader(
        settings=downloader_settings,
        loop=None,
    )

    # Khởi tạo Spotdl
    spotdl = Spotdl(
        client=client,
        downloader=downloader,
    )

    # Tìm kiếm và chuyển đổi links thành Song objects
    songs = spotdl.search(song_links)
    print(songs)

    # Tải nhạc
    spotdl.download_songs(songs)
    print("Đã tải xong!")
