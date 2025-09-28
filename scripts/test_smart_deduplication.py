#!/usr/bin/env python3
"""
Test script to verify smart deduplication system works correctly.
This prevents duplicate processing between /use and /play commands.
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from bot.services.playlist_service import PlaylistService
from bot.domain.entities.queue import QueueManager
from bot.domain.entities.library import LibraryManager
from bot.domain.entities.song import Song
from bot.domain.valueobjects.song_status import SongStatus
from bot.domain.valueobjects.source_type import SourceType
from bot.pkg.logger import logger


async def test_smart_deduplication():
    """Test the smart deduplication system"""
    logger.info("🧪 Testing Smart Deduplication System")

    # Create test environment
    guild_id = 12345
    library = LibraryManager()
    playlist_service = PlaylistService(library)
    queue_manager = QueueManager(guild_id)
    test_playlist = "test_playlist"
    user = "test_user"

    # Step 1: Create a test playlist with some songs
    logger.info(f"1️⃣ Creating test playlist '{test_playlist}'")
    success, message = playlist_service.create_playlist(test_playlist)
    print(f"✅ {message}")

    # Add some test songs to playlist
    test_songs = [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "Rick Astley - Never Gonna Give You Up",
        ),
        ("https://www.youtube.com/watch?v=3JZ_D3ELwOQ", "Baby Shark"),
        ("https://www.youtube.com/watch?v=kJQP7kiw5Fk", "Despacito"),
    ]

    for url, title in test_songs:
        success, msg = playlist_service.add_to_playlist(
            test_playlist, url, SourceType.YOUTUBE, title
        )
        if success:
            print(f"  ➕ Added: {title}")

    # Step 2: First load (simulate /use command)
    logger.info(f"2️⃣ First load - simulating /use {test_playlist}")
    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id
    )

    if success:
        print(f"✅ {message}")
        print(f"   Queue size: {queue_manager.queue_size}")
    else:
        print(f"❌ {message}")

    # Step 3: Second load (simulate /play without query)
    logger.info(f"3️⃣ Second load - simulating /play (should detect duplicate)")
    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id
    )

    if success:
        print(f"✅ {message}")
        print(f"   Queue size: {queue_manager.queue_size}")
        if "already loaded" in message:
            print("🎯 Smart deduplication working correctly!")
        else:
            print("⚠️ Deduplication may not be working as expected")
    else:
        print(f"❌ {message}")

    # Step 4: Test force reload
    logger.info(f"4️⃣ Force reload test")
    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id, force_reload=True
    )

    if success:
        print(f"✅ Force reload: {message}")
        print(f"   Queue size: {queue_manager.queue_size}")
    else:
        print(f"❌ {message}")

    # Step 5: Test clearing tracking
    logger.info(f"5️⃣ Test clearing playlist tracking")
    playlist_service.clear_loaded_playlist_tracking(guild_id, test_playlist)
    print("🧹 Cleared playlist tracking")

    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id
    )

    if success:
        print(f"✅ After clearing tracking: {message}")
        print(f"   Queue size: {queue_manager.queue_size}")
        if "already loaded" not in message:
            print("🎯 Tracking clear working correctly!")
        else:
            print("⚠️ Tracking may not have been cleared properly")
    else:
        print(f"❌ {message}")

    # Step 6: Test multiple guilds
    logger.info(f"6️⃣ Test multiple guilds isolation")
    guild_id_2 = 67890

    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id_2
    )

    if success:
        print(f"✅ Different guild: {message}")
        if "already loaded" not in message:
            print("🎯 Guild isolation working correctly!")
        else:
            print("⚠️ Guild isolation may not be working")
    else:
        print(f"❌ {message}")

    logger.info("🏁 Smart deduplication test completed")


if __name__ == "__main__":
    asyncio.run(test_smart_deduplication())
