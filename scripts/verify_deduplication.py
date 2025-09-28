#!/usr/bin/env python3
"""
Final verification script for smart deduplication system.
Quick test to ensure the core functionality works as expected.
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from bot.services.playlist_service import PlaylistService
from bot.domain.entities.queue import QueueManager
from bot.domain.entities.library import LibraryManager
from bot.pkg.logger import logger


async def quick_verification():
    """Quick verification that smart deduplication is working"""
    print("🔍 Quick Smart Deduplication Verification")

    # Setup
    guild_id = 99999
    library = LibraryManager()
    playlist_service = PlaylistService(library)
    queue_manager = QueueManager(guild_id)

    test_playlist = "verification_playlist"
    user = "test_user"

    # Create minimal test playlist
    success, msg = playlist_service.create_playlist(test_playlist)
    print(f"Created playlist: {success}")

    # Add one test song
    from bot.domain.valueobjects.source_type import SourceType

    success, msg = playlist_service.add_to_playlist(
        test_playlist,
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        SourceType.YOUTUBE,
        "Test Song",
    )
    print(f"Added song: {success}")

    # Test 1: First load (should process normally)
    print("\n1️⃣ First load...")
    start_time = asyncio.get_event_loop().time()
    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id
    )
    first_duration = asyncio.get_event_loop().time() - start_time
    print(f"✅ {message} (took {first_duration:.1f}s)")

    # Test 2: Second load (should detect duplicate instantly)
    print("\n2️⃣ Second load (should be instant)...")
    start_time = asyncio.get_event_loop().time()
    success, message = await playlist_service.load_playlist_to_queue(
        test_playlist, queue_manager, user, guild_id
    )
    second_duration = asyncio.get_event_loop().time() - start_time
    print(f"✅ {message} (took {second_duration:.1f}s)")

    # Results
    if "already loaded" in message and second_duration < 2:
        print(f"\n🎯 SUCCESS: Smart deduplication working!")
        print(f"   First load: {first_duration:.1f}s")
        print(
            f"   Second load: {second_duration:.1f}s (saved {first_duration-second_duration:.1f}s)"
        )
    else:
        print(f"\n⚠️  Issue: Deduplication may not be working optimally")
        print(f"   Expected 'already loaded' message and < 2s response time")


if __name__ == "__main__":
    asyncio.run(quick_verification())
