#!/usr/bin/env python3
"""
Demo script for testing enhanced /play command functionality
Shows both modes: with query and from active playlist
"""

import asyncio
import sys
import os

# Add parent directory to path to import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.domain.entities.library import LibraryManager
from bot.services.playlist_service import PlaylistService
from bot.domain.valueobjects.source_type import SourceType
from bot.domain.entities.queue import QueueManager


def demo_enhanced_play_command():
    """Demo enhanced /play command with two modes"""
    print("=" * 60)
    print("🎵 ENHANCED /PLAY COMMAND DEMO")
    print("=" * 60)

    # Initialize services
    library = LibraryManager()
    service = PlaylistService(library)

    # Create a demo playlist
    print("\n📝 Setting up demo playlist...")
    success, msg = service.create_playlist("Demo Mix")
    print(f"   {msg}")

    # Add some songs
    demo_songs = [
        ("Shape of You", SourceType.SEARCH_QUERY, "Ed Sheeran - Shape of You"),
        ("Blinding Lights", SourceType.SEARCH_QUERY, "The Weeknd - Blinding Lights"),
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            SourceType.YOUTUBE,
            "Never Gonna Give You Up",
        ),
    ]

    for song_input, source_type, title in demo_songs:
        success, msg = service.add_to_playlist(
            "Demo Mix", song_input, source_type, title
        )
        print(f"   {msg}")

    # Simulate guild queue setup
    guild_id = 12345
    queue_manager = QueueManager(guild_id)

    print(f"\n🔄 Simulating /use command to set active playlist...")
    # Load playlist to queue (simulating /use command)
    success, message = asyncio.run(
        service.load_playlist_to_queue("Demo Mix", queue_manager, "Demo User", guild_id)
    )
    print(f"   ✅ {message}")

    # Simulate active playlist tracking (what bot would do)
    active_playlists = {guild_id: "Demo Mix"}
    print(
        f"   📌 Active playlist for guild {guild_id}: **{active_playlists[guild_id]}**"
    )

    print(f"\n📊 Queue status after /use:")
    print(
        f"   Current song: {queue_manager.current_song.display_name if queue_manager.current_song else 'None'}"
    )
    print(f"   Queue size: {queue_manager.queue_size}")
    print(f"   Position: {queue_manager.position[0]}/{queue_manager.position[1]}")

    print(f"\n🎵 Enhanced /play command modes:")
    print(f"   Mode 1: /play <query>  - Traditional search/URL mode")
    print(f"   Mode 2: /play          - Load more from active playlist")

    # Demo Mode 2: /play without query
    print(f"\n🔄 Simulating /play without query (Mode 2)...")
    active_playlist = active_playlists.get(guild_id)
    if active_playlist:
        print(f"   📋 Active playlist detected: '{active_playlist}'")

        # Load more songs from active playlist
        success, message = asyncio.run(
            service.load_playlist_to_queue(
                active_playlist, queue_manager, "Demo User", guild_id
            )
        )
        print(f"   ✅ {message}")

        print(f"\n📊 Queue status after /play (no query):")
        print(f"   Queue size: {queue_manager.queue_size}")
        print(f"   Position: {queue_manager.position[0]}/{queue_manager.position[1]}")
    else:
        print(f"   ❌ No active playlist - would show error message")

    # Demo Mode 1: /play with query
    print(f"\n🔄 Simulating /play with query (Mode 1)...")
    print(f"   🔍 Query: 'Bohemian Rhapsody'")
    print(f"   ✅ Would process normally through existing play logic")
    print(f"   📝 This mode remains unchanged from original implementation")

    print(f"\n" + "=" * 60)
    print(f"✅ Enhanced /play command demo completed!")
    print(f"💡 Key features:")
    print(f"   • /play (no args) - Loads more from active playlist")
    print(f"   • /play <query>   - Traditional search/URL mode")
    print(f"   • Automatic active playlist tracking")
    print(f"   • User-friendly error messages")
    print("=" * 60)


if __name__ == "__main__":
    try:
        demo_enhanced_play_command()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        raise
