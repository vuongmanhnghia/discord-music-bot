# Danh sách các link Spotify bạn muốn tải
import asyncio
from src.tracking.tracking import spotdl_save


song_links = [
    "https://open.spotify.com/track/5IO873C4IP8pXdsXcJiBes?si=2e354799844a47b9",
    "https://open.spotify.com/track/1WbTOu4D2oHK9fg2qR6msd?si=3df438007c6940fb",
]


async def main():
    save_file = "playlist.txt"
    playlist_url = "https://open.spotify.com/track/1WbTOu4D2oHK9fg2qR6msd?si=3df438007c6940fb"  # nếu bạn truyền vào là URL
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, spotdl_save, save_file, playlist_url)
    # await ctx.send(f"Đã lưu tracking vào `{save_file}`")


asyncio.run(main())
