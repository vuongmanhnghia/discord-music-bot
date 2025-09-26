import asyncio
import concurrent
from pathlib import Path
from typing import List, Optional, Tuple
from dotenv.main import logger
from spotdl.types.song import Song
from spotdl.utils.search import parse_query
from spotdl.download.downloader import Downloader
from spotdl.utils.spotify import SpotifyClient


class Spotdl:
    def __init__(
        self,
        client: SpotifyClient,
        downloader: Downloader,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):

        # Initialize the SpotifyClient singleton
        self.client = client
        self.downloader = downloader

    def download(self, song: Song) -> Tuple[Song, Optional[Path]]:
        """
        - Download and convert song to the output format.
        - song: Song object => A tuple containing the song and the path to the downloaded file if successful.
        """

        return self.downloader.download_song(song)

    def download_songs(self, songs: List[Song]) -> List[Tuple[Song, Optional[Path]]]:
        """
        - Download and convert songs to the output format.
        - songs: List of Song objects => A list of tuples containing the song and the path to the downloaded file if successful.
        """

        return self.downloader.download_multiple_songs(songs)

    def get_download_urls(self, songs: List[Song]) -> List[Optional[str]]:
        """
        - Get the download urls for a list of songs.
        - songs: List of Song objects => A list of urls if successful.
        - Notes: This function is multi-threaded.
        """

        urls: List[Optional[str]] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.downloader.settings["threads"]
        ) as executor:
            future_to_song = {
                executor.submit(self.downloader.search, song): song for song in songs
            }
            for future in concurrent.futures.as_completed(future_to_song):
                song = future_to_song[future]
                try:
                    data = future.result()
                    urls.append(data)
                except Exception as exc:
                    logger.error("%s generated an exception: %s", song, exc)

        return urls

    def search(self, query: List[str]) -> List[Song]:
        """
        - Search for songs.
        - query: List of search queries => A list of Song objects
        - Notes: query can be a list of song titles, urls, uris
        """

        return parse_query(
            query=query,
            threads=self.downloader.settings["threads"],
            use_ytm_data=self.downloader.settings["ytm_data"],
            playlist_numbering=self.downloader.settings["playlist_numbering"],
            album_type=self.downloader.settings["album_type"],
            playlist_retain_track_cover=self.downloader.settings[
                "playlist_retain_track_cover"
            ],
        )
