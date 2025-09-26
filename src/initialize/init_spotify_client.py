from spotdl.utils.spotify import SpotifyClient


def init_spotify_client(spotify_client) -> SpotifyClient:
    return SpotifyClient.init(
        client_id=spotify_client["client_id"],
        client_secret=spotify_client["client_secret"],
        user_auth=spotify_client["user_auth"],
        cache_path=spotify_client["cache_path"],
        no_cache=spotify_client["no_cache"],
        headless=spotify_client["headless"],
    )
