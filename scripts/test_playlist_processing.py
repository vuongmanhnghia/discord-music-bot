#!/usr/bin/env python3
"""
Test Song Processing in Playlist Fix
Tests that songs from playlists are properly processed and ready to play
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


async def test_playlist_song_processing():
    """Test that playlist songs are processed and ready to play"""

    print("🎵 Testing Playlist Song Processing Fix")
    print("=" * 50)

    # Initialize services
    library_manager = LibraryManager()
    playlist_service = PlaylistService(library_manager)

    # Test playlist name
    playlist_name = "processing_test_playlist"

    # Clean up from previous runs
    if library_manager.exists(playlist_name):
        library_manager.delete_playlist(playlist_name)
        print(f"🧹 Cleaned up existing playlist: {playlist_name}")

    print(f"\n🔧 Testing Song Processing in Playlist")
    print("-" * 40)

    # Step 1: Create playlist and add a YouTube URL
    print(f"1️⃣ Creating playlist with YouTube URL...")
    success, msg = playlist_service.create_playlist(playlist_name)
    print(f"   Create result: {msg}")

    if not success:
        print("❌ Failed to create playlist")
        return

    # Add a real YouTube URL (same as in your example)
    test_url = (
        "https://www.youtube.com/watch?v=zwX1hJu9Lds&list=RDzwX1hJu9Lds&start_radio=1"
    )
    success, msg = playlist_service.add_to_playlist(
        playlist_name, test_url, SourceType.YOUTUBE, "Test YouTube Video"
    )
    print(f"   Add result: {msg}")

    if not success:
        print("❌ Failed to add song to playlist")
        return

    # Step 2: Load playlist to queue and check song processing
    print(f"\n2️⃣ Loading playlist to queue (this should process songs)...")
    guild_id = 12345
    queue_manager = QueueManager(guild_id)
    user = "TestUser#1234"

    print(f"   🔄 Loading playlist '{playlist_name}' to queue...")
    try:
        success, message = await playlist_service.load_playlist_to_queue(
            playlist_name, queue_manager, user, guild_id
        )

        print(f"   Load Success: {success}")
        print(f"   Load Message: '{message}'")

        if success:
            print(f"   ✅ Playlist loaded to queue successfully!")
        else:
            print(f"   ❌ Failed to load playlist to queue")
            return

    except Exception as e:
        print(f"   ❌ Exception during playlist loading: {e}")
        return

    # Step 3: Check queue and song status
    print(f"\n3️⃣ Checking queue and song status...")

    current_song = queue_manager.current_song
    upcoming = queue_manager.get_upcoming(5)

    print(f"   Queue stats:")
    print(f"   - Current song: {'Yes' if current_song else 'None'}")
    print(f"   - Upcoming songs: {len(upcoming)}")

    if current_song:
        print(f"\n   📍 Current Song Analysis:")
        print(f"   - Display name: {current_song.display_name}")
        print(f"   - Original input: {current_song.original_input}")
        print(f"   - Source type: {current_song.source_type.value}")
        print(f"   - Status: {current_song.status.value}")
        print(f"   - Has metadata: {'Yes' if current_song.metadata else 'No'}")
        print(f"   - Has stream URL: {'Yes' if current_song.stream_url else 'No'}")
        print(
            f"   - IS READY TO PLAY: {'✅ YES' if current_song.is_ready else '❌ NO'}"
        )

        if current_song.metadata:
            print(f"   - Title: {current_song.metadata.title}")
            print(f"   - Duration: {current_song.duration_formatted}")

        if not current_song.is_ready:
            print(
                f"   ⚠️ Song is NOT ready - this explains the 'chưa có bài nào sẵn sàng phát' message"
            )
            print(f"   🔍 Reason analysis:")
            if current_song.status.value != "ready":
                print(
                    f"      - Status is '{current_song.status.value}' instead of 'ready'"
                )
            if not current_song.metadata:
                print(f"      - Missing metadata")
            if not current_song.stream_url:
                print(f"      - Missing stream URL")
        else:
            print(f"   ✅ Song IS ready - should be able to play!")

    else:
        print(f"   ❌ No current song in queue")

    # Step 4: Compare with direct /play behavior
    print(f"\n4️⃣ Comparison Analysis")
    print("-" * 30)
    print(f"🎯 Root Cause Analysis:")
    print(f"   The bug 'chưa có bài nào sẵn sàng phát' happens when:")
    print(f"   1. Songs are loaded to queue from playlist")
    print(f"   2. But songs have status='pending' (not processed)")
    print(f"   3. song.is_ready = False because no metadata/stream_url")
    print(f"   4. audio_service.play_next_song() fails because song not ready")

    print(f"\n💡 The Fix:")
    print(f"   - BEFORE: Playlist songs added to queue without processing")
    print(f"   - AFTER: Playlist songs processed (like /play) before adding to queue")
    print(f"   - RESULT: Songs have metadata + stream_url → is_ready = True")

    if current_song and current_song.is_ready:
        print(f"\n✅ FIX SUCCESSFUL!")
        print(f"   Playlist songs are now processed and ready to play!")
    elif current_song and not current_song.is_ready:
        print(f"\n⚠️ PARTIAL FIX:")
        print(f"   Song processing may have failed or is still in progress")
        print(f"   This could be due to network issues or invalid URL")
    else:
        print(f"\n❌ FIX NOT WORKING:")
        print(f"   No songs in queue after loading playlist")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    success, msg = playlist_service.delete_playlist(playlist_name)
    print(f"🗑️ {msg}")

    print(f"\n✅ Playlist Song Processing Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_playlist_song_processing())
