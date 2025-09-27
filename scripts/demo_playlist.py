#!/usr/bin/env python3
"""
Demo script showing playlist system functionality
Usage: python demo_playlist.py
"""

import asyncio
import sys
import os

# Add parent directory to path to import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.domain.entities.library import LibraryManager
from bot.services.playlist_service import PlaylistService
from bot.domain.valueobjects.source_type import SourceType


def demo_basic_operations():
    """Demo basic playlist operations"""
    print("=" * 50)
    print("🎵 PLAYLIST SYSTEM DEMO")
    print("=" * 50)

    # Initialize
    library = LibraryManager()
    service = PlaylistService(library)

    # 1. Create playlists
    print("\n📝 Creating playlists...")
    success, msg = service.create_playlist("My Favorites")
    print(f"   {msg}")

    success, msg = service.create_playlist("Rock Classics")
    print(f"   {msg}")

    # 2. Add songs
    print("\n➕ Adding songs...")

    # Add to My Favorites
    songs_favorites = [
        (
            "Never Gonna Give You Up",
            SourceType.SEARCH_QUERY,
            "Rick Astley - Never Gonna Give You Up",
        ),
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            SourceType.YOUTUBE,
            "Rick Roll Official",
        ),
        (
            "https://open.spotify.com/track/4PTG3Z6ehGkBFwjybzWkR8",
            SourceType.SPOTIFY,
            "Never Gonna Give You Up - Spotify",
        ),
    ]

    for song_input, source_type, title in songs_favorites:
        success, msg = service.add_to_playlist(
            "My Favorites", song_input, source_type, title
        )
        print(f"   {msg}")

    # Add to Rock Classics
    songs_rock = [
        ("Bohemian Rhapsody", SourceType.SEARCH_QUERY, "Queen - Bohemian Rhapsody"),
        ("Hotel California", SourceType.SEARCH_QUERY, "Eagles - Hotel California"),
        (
            "Stairway to Heaven",
            SourceType.SEARCH_QUERY,
            "Led Zeppelin - Stairway to Heaven",
        ),
    ]

    for song_input, source_type, title in songs_rock:
        success, msg = service.add_to_playlist(
            "Rock Classics", song_input, source_type, title
        )
        print(f"   {msg}")

    # 3. List all playlists
    print("\n📋 All playlists:")
    playlists = service.list_playlists()
    for i, playlist_name in enumerate(playlists, 1):
        print(f"   {i}. {playlist_name}")

    # 4. Show playlist details
    print("\n📄 Playlist details:")
    for playlist_name in playlists:
        info = service.get_playlist_info(playlist_name)
        if info:
            print(f"\n   🎵 {info['name']} ({info['total_songs']} songs)")
            print(f"   Created: {info['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            for j, entry in enumerate(info["entries"], 1):
                source_icon = {
                    "youtube": "🔴",
                    "spotify": "🟢",
                    "soundcloud": "🟠",
                    "search": "🔍",
                }.get(entry["source_type"], "❓")
                print(f"      {j}. {source_icon} {entry['title']}")

    # 5. Remove a song
    print("\n➖ Removing a song...")
    success, msg = service.remove_from_playlist("My Favorites", 2)  # Remove 2nd song
    print(f"   {msg}")

    # Show updated playlist
    info = service.get_playlist_info("My Favorites")
    if info:
        print(f"\n   Updated My Favorites ({info['total_songs']} songs):")
        for j, entry in enumerate(info["entries"], 1):
            print(f"      {j}. {entry['title']}")

    print("\n" + "=" * 50)
    print("✅ Demo completed!")
    print("💡 Check the 'playlist/' directory for JSON files")
    print("=" * 50)


def demo_queue_integration():
    """Demo how playlist integrates with queue (simulation)"""
    print("\n🔄 QUEUE INTEGRATION SIMULATION")
    print("-" * 50)

    library = LibraryManager()
    service = PlaylistService(library)

    # Get a playlist
    info = service.get_playlist_info("My Favorites")
    if not info:
        print("   ❌ No 'My Favorites' playlist found. Run basic demo first.")
        return

    print(f"   📋 Loading '{info['name']}' into queue...")
    print(f"   📊 {info['total_songs']} songs to process:")

    # Simulate converting to Song objects
    from bot.domain.entities.song import Song
    from bot.domain.valueobjects.song_status import SongStatus

    simulated_songs = []
    for i, entry in enumerate(info["entries"], 1):
        song = Song(
            original_input=entry["original_input"],
            source_type=SourceType(entry["source_type"]),
            status=SongStatus.PENDING,
            requested_by="Demo User",
            guild_id=12345,
        )
        simulated_songs.append(song)

        source_icon = {
            "youtube": "🔴",
            "spotify": "🟢",
            "soundcloud": "🟠",
            "search": "🔍",
        }.get(entry["source_type"], "❓")

        print(f"      {i}. {source_icon} {entry['title']}")
        print(f"         Input: {entry['original_input'][:50]}...")
        print(f"         Status: {song.status.value}")

    print(f"\n   ✅ Successfully created {len(simulated_songs)} Song objects")
    print("   💡 These would be added to QueueManager in real usage")


if __name__ == "__main__":
    try:
        demo_basic_operations()
        demo_queue_integration()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        raise
