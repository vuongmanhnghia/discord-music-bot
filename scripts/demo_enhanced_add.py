#!/usr/bin/env python3
"""
Demo script for testing enhanced /add commands
Shows both /add (active playlist) and /addto (specific playlist) commands
"""

import asyncio
import sys
import os

# Add parent directory to path to import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.domain.entities.library import LibraryManager
from bot.services.playlist_service import PlaylistService
from bot.domain.valueobjects.source_type import SourceType


def demo_enhanced_add_commands():
    """Demo enhanced add commands with active playlist tracking"""
    print("=" * 60)
    print("🎵 ENHANCED /ADD COMMANDS DEMO")
    print("=" * 60)

    # Initialize services
    library = LibraryManager()
    service = PlaylistService(library)

    # Create multiple playlists
    print("\n📝 Creating multiple playlists...")
    playlists_to_create = ["My Favorites", "Rock Classics", "Pop Hits"]

    for playlist_name in playlists_to_create:
        success, msg = service.create_playlist(playlist_name)
        print(f"   {msg}")

    # Simulate active playlist tracking (what bot would do)
    guild_id = 12345
    active_playlists = {}

    print(f"\n🔄 Simulating /use command to set active playlist...")
    active_playlist = "My Favorites"
    active_playlists[guild_id] = active_playlist
    print(f"   📌 Active playlist for guild {guild_id}: **{active_playlist}**")

    # Demo /addto command (specific playlist)
    print(f"\n➕ Testing /addto command (specific playlist)...")
    test_songs_addto = [
        ("Rock Classics", "Bohemian Rhapsody", "Queen - Bohemian Rhapsody"),
        ("Rock Classics", "Hotel California", "Eagles - Hotel California"),
        ("Pop Hits", "Shape of You", "Ed Sheeran - Shape of You"),
        ("Pop Hits", "Blinding Lights", "The Weeknd - Blinding Lights"),
    ]

    for target_playlist, song_input, title in test_songs_addto:
        success, msg = service.add_to_playlist(
            target_playlist, song_input, SourceType.SEARCH_QUERY, title
        )
        print(f'   /addto "{target_playlist}" "{song_input}"')
        print(f"   ✅ {msg}")

    # Demo /add command (active playlist)
    print(f"\n➕ Testing /add command (active playlist)...")
    # Check if there's an active playlist
    current_active = active_playlists.get(guild_id)
    if current_active:
        print(f"   📋 Active playlist: '{current_active}'")

        test_songs_add = [
            ("Never Gonna Give You Up", "Rick Astley - Never Gonna Give You Up"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Rick Roll Official"),
            ("Perfect", "Ed Sheeran - Perfect"),
        ]

        for song_input, title in test_songs_add:
            # Detect source type
            if "youtube.com" in song_input or "youtu.be" in song_input:
                source_type = SourceType.YOUTUBE
            else:
                source_type = SourceType.SEARCH_QUERY

            success, msg = service.add_to_playlist(
                current_active, song_input, source_type, title
            )
            print(f'   /add "{song_input}"')
            print(f"   ✅ Added to '{current_active}': {title}")
    else:
        print(f"   ❌ No active playlist - would show error message")

    # Show all playlists with their contents
    print(f"\n📄 Final playlist contents:")
    all_playlists = service.list_playlists()

    for playlist_name in all_playlists:
        info = service.get_playlist_info(playlist_name)
        if info:
            is_active = (
                "🎵 ACTIVE" if playlist_name == active_playlists.get(guild_id) else ""
            )
            print(f"\n   📋 {info['name']} ({info['total_songs']} songs) {is_active}")

            for i, entry in enumerate(info["entries"], 1):
                source_icon = {
                    "youtube": "🔴",
                    "spotify": "🟢",
                    "soundcloud": "🟠",
                    "search": "🔍",
                }.get(entry["source_type"], "❓")
                print(f"      {i}. {source_icon} {entry['title']}")

    # Demo changing active playlist
    print(f"\n🔄 Simulating switching active playlist...")
    new_active = "Rock Classics"
    active_playlists[guild_id] = new_active
    print(f"   📌 New active playlist: **{new_active}**")

    # Add more songs to the new active playlist
    print(f"\n➕ Adding to new active playlist with /add...")
    success, msg = service.add_to_playlist(
        new_active,
        "Stairway to Heaven",
        SourceType.SEARCH_QUERY,
        "Led Zeppelin - Stairway to Heaven",
    )
    print(f'   /add "Stairway to Heaven"')
    print(f"   ✅ Added to '{new_active}': Led Zeppelin - Stairway to Heaven")

    print(f"\n" + "=" * 60)
    print(f"✅ Enhanced /add commands demo completed!")
    print(f"💡 Key differences:")
    print(f"   • /add <song>           - Adds to currently active playlist")
    print(f"   • /addto <playlist> <song> - Adds to specific playlist")
    print(f"   • Active playlist tracking per guild")
    print(f"   • User-friendly error messages")
    print(f"   • Workflow: /use -> /add, /add, /add...")
    print("=" * 60)


if __name__ == "__main__":
    try:
        demo_enhanced_add_commands()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        raise
