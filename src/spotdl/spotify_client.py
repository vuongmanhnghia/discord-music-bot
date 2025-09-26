from typing import Optional

from spotdl.utils.spotify import (
    SpotifyError,
    CacheFileHandler,
    MemoryCacheHandler,
    SpotifyOAuth,
    SpotifyClientCredentials,
    get_cache_path,
)


class SpotifyClient:
    def __init__(self):
        self._instance = None
        self.user_auth = False
        self.no_cache = False
        self.max_retries = 3
        self.use_cache_file = False

    def init(  # pylint: disable=bad-mcs-method-argument
        self,
        client_id: str,
        client_secret: str,
        user_auth: bool = False,
        no_cache: bool = False,
        headless: bool = False,
        max_retries: int = 3,
        use_cache_file: bool = False,
        auth_token: Optional[str] = None,
        cache_path: Optional[str] = None,
    ):
        """
        Initializes the SpotifyClient.

        ### Arguments
        - client_id: The client ID of the application.
        - client_secret: The client secret of the application.
        - auth_token: The access token to use.
        - user_auth: Whether or not to use user authentication.
        - cache_path: The path to the cache file.
        - no_cache: Whether or not to use the cache.
        - open_browser: Whether or not to open the browser.

        ### Returns
        - The instance of the SpotifyClient.
        """

        # check if initialization has been completed, if yes, raise an Exception
        if self._instance is not None:
            raise SpotifyError("A spotify client has already been initialized")

        credential_manager = None

        cache_handler = (
            CacheFileHandler(cache_path or get_cache_path())
            if not no_cache
            else MemoryCacheHandler()
        )
        # Use SpotifyOAuth as auth manager
        if user_auth:
            credential_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://127.0.0.1:9900/",
                scope="user-library-read,user-follow-read,playlist-read-private",
                cache_handler=cache_handler,
                open_browser=not headless,
            )
        # Use SpotifyClientCredentials as auth manager
        else:
            credential_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
                cache_handler=cache_handler,
            )
        if auth_token is not None:
            credential_manager = None

        self.user_auth = user_auth
        self.no_cache = no_cache
        self.max_retries = max_retries
        self.use_cache_file = use_cache_file

        # Store the credential manager for later use
        self._instance = credential_manager

        # Return self for method chaining
        return self
