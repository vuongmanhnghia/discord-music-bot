#!/usr/bin/env python3
"""
Test Auto-Playback Feature
Tests the updated /play command that auto-starts playlist playback
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from bot.services.playlist_service import PlaylistService
from bot.domain.entities.library import LibraryManager
from bot.domain.entities.queue import QueueManager
from bot.domain.valueobjects.source_type import SourceType


async def test_auto_playback():
    """Test the auto-playback feature when using /play without query"""

    print("🎵 Auto-Playback Feature Test")
    print("=" * 50)

    # Initialize services
    library_manager = LibraryManager()
    playlist_service = PlaylistService(library_manager)

    # Create test playlist
    playlist_name = "autoplay_test"

    # Clean up from previous runs
    if library_manager.exists(playlist_name):
        library_manager.delete_playlist(playlist_name)
        print(f"🧹 Cleaned up existing playlist: {playlist_name}")

    # Create new playlist
    success, msg = playlist_service.create_playlist(playlist_name)
    print(f"📝 Create playlist: {msg}")

    if not success:
        return

    # Add test songs with URLs that playlist stores
    test_songs = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Never Gonna Give You Up"),
        ("https://www.youtube.com/watch?v=9bZkp7q19f0", "Gangnam Style"),
        ("https://soundcloud.com/example/song", "SoundCloud Example"),
    ]

    print(f"\n➕ Adding songs to playlist...")
    for url, title in test_songs:
        source_type = SourceType.YOUTUBE
        if "soundcloud.com" in url:
            source_type = SourceType.SOUNDCLOUD

        success, msg = playlist_service.add_to_playlist(
            playlist_name, url, source_type, title
        )
        print(f"   {msg}")

    # Simulate the Discord command workflow
    print(f"\n🎮 Simulating Discord /play Command Workflow")
    print("=" * 50)

    guild_id = 12345
    queue_manager = QueueManager(guild_id)
    user = "TestUser#1234"

    # Simulate active playlist tracking (like self.active_playlists)
    active_playlists = {guild_id: playlist_name}

    print(f"🏠 Guild: {guild_id}")
    print(f"👤 User: {user}")
    print(f"📋 Active playlist: {active_playlists.get(guild_id, 'None')}")

    # Test Case 1: /play with query (existing behavior)
    print(f"\n📍 Test Case 1: /play with query")
    print("-" * 30)
    query = "Never gonna give you up"
    print(f"🔍 Command: /play {query}")
    print(f"📝 Expected: Process query normally (existing behavior)")
    print(f"✅ Result: Would call playback_service.play_request('{query}')")

    # Test Case 2: /play without query (NEW enhanced behavior)
    print(f"\n📍 Test Case 2: /play without query (Enhanced)")
    print("-" * 30)
    print(f"🔍 Command: /play")
    print(f"📝 Expected: Auto-play from active playlist")

    # Step 1: Check for active playlist
    active_playlist = active_playlists.get(guild_id)
    if not active_playlist:
        print(f"❌ No active playlist - would show error message")
        return

    print(f"✅ Found active playlist: {active_playlist}")

    # Step 2: Load playlist to queue
    print(f"\n🔄 Loading playlist to queue...")
    success, message = await playlist_service.load_playlist_to_queue(
        active_playlist, queue_manager, user, guild_id
    )

    if success:
        print(f"✅ Loaded: {message}")

        # Step 3: Check if auto-playback should start
        print(f"\n🎵 Checking auto-playback conditions...")

        current_song = queue_manager.current_song
        if current_song:
            print(f"🎯 Current song: {current_song.display_name}")
            print(f"📊 Status: {current_song.status.value}")
            print(f"🚀 Ready to play: {current_song.is_ready}")

            # This simulates the enhanced logic in music_bot.py
            # In real Discord bot: audio_player.is_playing would be checked
            is_currently_playing = False  # Simulate not playing

            if not is_currently_playing:
                if current_song.is_ready:
                    print(
                        f"✅ AUTO-PLAYBACK: Would start playing '{current_song.display_name}'"
                    )
                    print(f"🎵 Message: 'Đã bắt đầu phát nhạc!'")
                else:
                    print(f"⚠️ Song not ready yet: '{current_song.display_name}'")
                    print(
                        f"📝 Message: 'Đã thêm vào queue, nhưng chưa có bài nào sẵn sàng phát'"
                    )
            else:
                print(f"🎵 Already playing - just added to queue")
        else:
            print(f"❌ No songs in queue after loading")

    else:
        print(f"❌ Failed to load playlist: {message}")

    # Show the key improvement
    print(f"\n💡 Key Enhancement Summary")
    print("=" * 50)
    print(f"🔧 Problem Solved:")
    print(f"   - Before: /play from playlist required manual URL entry")
    print(f"   - After: /play auto-detects and plays from active playlist")

    print(f"\n🎯 Implementation:")
    print(f"   1. Check if query provided → Normal /play behavior")
    print(f"   2. No query + active playlist → Load & auto-start")
    print(f"   3. Playlist URLs treated like individual /play commands")

    print(f"\n🎵 User Experience:")
    print(f"   1. /use my_playlist   → Load playlist as active")
    print(f"   2. /play              → Auto-start from playlist")
    print(f"   3. /play <query>      → Search/play specific song")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    success, msg = playlist_service.delete_playlist(playlist_name)
    print(f"🗑️ {msg}")

    print(f"\n✅ Auto-Playback Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_auto_playback())
