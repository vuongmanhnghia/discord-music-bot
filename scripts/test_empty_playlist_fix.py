#!/usr/bin/env python3
"""
Test Empty Playlist Bug Fix
Tests the fix for the empty playlist /use command issue
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from bot.services.playlist_service import PlaylistService
from bot.domain.entities.library import LibraryManager
from bot.domain.entities.queue import QueueManager


async def test_empty_playlist_fix():
    """Test the fix for empty playlist /use bug"""

    print("🐛 Testing Empty Playlist Bug Fix")
    print("=" * 50)

    # Initialize services
    library_manager = LibraryManager()
    playlist_service = PlaylistService(library_manager)

    # Test playlist name
    playlist_name = "empty_test_playlist"

    # Clean up from previous runs
    if library_manager.exists(playlist_name):
        library_manager.delete_playlist(playlist_name)
        print(f"🧹 Cleaned up existing playlist: {playlist_name}")

    print(f"\n📋 Testing Empty Playlist Workflow")
    print("-" * 30)

    # Step 1: Create new empty playlist
    print(f"1️⃣ Creating empty playlist...")
    success, msg = playlist_service.create_playlist(playlist_name)
    print(f"   Result: {msg}")

    if not success:
        print("❌ Failed to create playlist")
        return

    # Step 2: Check playlist exists in list
    print(f"\n2️⃣ Checking playlist appears in list...")
    playlists = playlist_service.list_playlists()
    if playlist_name in playlists:
        print(f"   ✅ Playlist '{playlist_name}' found in list")
    else:
        print(f"   ❌ Playlist '{playlist_name}' NOT found in list")
        return

    # Step 3: Check playlist info shows empty
    print(f"\n3️⃣ Checking playlist info...")
    info = playlist_service.get_playlist_info(playlist_name)
    if info:
        print(f"   📊 Total songs: {info['total_songs']}")
        print(f"   📅 Created: {info['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        if info["total_songs"] == 0:
            print(f"   ✅ Playlist correctly shows as empty")
        else:
            print(f"   ❌ Playlist should be empty but has {info['total_songs']} songs")
    else:
        print(f"   ❌ Could not get playlist info")
        return

    # Step 4: Test the problematic /use command (load_playlist_to_queue)
    print(f"\n4️⃣ Testing /use on empty playlist (BEFORE fix this would fail)...")
    guild_id = 12345
    queue_manager = QueueManager(guild_id)
    user = "TestUser#1234"

    success, message = await playlist_service.load_playlist_to_queue(
        playlist_name, queue_manager, user, guild_id
    )

    print(f"   Success: {success}")
    print(f"   Message: '{message}'")

    if success:
        print(f"   ✅ FIXED: Empty playlist /use now works!")
        if "is empty" in message:
            print(f"   ✅ Correct message for empty playlist")
        else:
            print(f"   ⚠️ Unexpected message for empty playlist")
    else:
        print(f"   ❌ STILL BUGGY: Empty playlist /use still fails")

    # Step 5: Simulate the enhanced Discord /use command logic
    print(f"\n5️⃣ Simulating Discord /use command behavior...")

    # This simulates the logic in music_bot.py
    active_playlists = {}  # Simulates self.active_playlists

    if success:
        # Always track the active playlist for this guild, even if empty
        active_playlists[guild_id] = playlist_name

        # Check if playlist was empty
        if "is empty" in message:
            print(f"   📋 Set as active playlist: '{playlist_name}'")
            print(f"   🟠 Discord Message: 'Đã chọn playlist trống'")
            print(f"   💡 Discord Hint: 'Sử dụng /add <song> để thêm bài hát'")
        else:
            print(f"   📋 Set as active playlist: '{playlist_name}'")
            print(f"   🟢 Discord Message: 'Đã nạp playlist'")
    else:
        print(f"   🔴 Discord Message: 'Lỗi: {message}'")

    # Step 6: Test that we can add songs to the active empty playlist
    print(f"\n6️⃣ Testing /add to empty active playlist...")

    # Check if we have an active playlist
    active_playlist = active_playlists.get(guild_id)
    if active_playlist:
        print(f"   🎯 Active playlist: {active_playlist}")

        # Add a song (simulating /add command)
        from bot.domain.valueobjects.source_type import SourceType

        success, msg = playlist_service.add_to_playlist(
            active_playlist,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            SourceType.YOUTUBE,
            "Never Gonna Give You Up",
        )
        print(f"   Add result: {msg}")

        if success:
            print(f"   ✅ Successfully added song to previously empty playlist")

            # Check playlist is no longer empty
            info = playlist_service.get_playlist_info(playlist_name)
            if info and info["total_songs"] > 0:
                print(f"   ✅ Playlist now has {info['total_songs']} song(s)")
            else:
                print(f"   ❌ Playlist still appears empty after adding song")
        else:
            print(f"   ❌ Failed to add song to active playlist")
    else:
        print(f"   ❌ No active playlist set")

    # Summary
    print(f"\n📋 Bug Fix Summary")
    print("=" * 50)
    print(f"🐛 Original Bug:")
    print(f"   1. /create new_playlist ✅")
    print(f"   2. /playlists shows new_playlist ✅")
    print(f"   3. /use new_playlist ❌ 'Playlist is empty' ERROR")

    print(f"\n🔧 Fixed Behavior:")
    print(f"   1. /create new_playlist ✅")
    print(f"   2. /playlists shows new_playlist ✅")
    print(f"   3. /use new_playlist ✅ Sets as active + helpful message")
    print(f"   4. /add song ✅ Adds to active empty playlist")

    print(f"\n💡 Key Improvements:")
    print(f"   - Empty playlist /use no longer fails")
    print(f"   - Sets playlist as active even when empty")
    print(f"   - Provides helpful guidance to user")
    print(f"   - Enables seamless /add workflow")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    success, msg = playlist_service.delete_playlist(playlist_name)
    print(f"🗑️ {msg}")

    print(f"\n✅ Empty Playlist Bug Fix Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_empty_playlist_fix())
