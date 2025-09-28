#!/usr/bin/env python3
"""
Test Enhanced /add Command
Tests the enhanced /add command that processes songs like /play but adds to playlist
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from bot.services.playlist_service import PlaylistService
from bot.services.playback import PlaybackService
from bot.domain.entities.library import LibraryManager
from bot.domain.entities.queue import QueueManager
from bot.domain.valueobjects.source_type import SourceType


async def test_enhanced_add_command():
    """Test the enhanced /add command workflow"""

    print("🎵 Testing Enhanced /add Command")
    print("=" * 50)

    # Initialize services
    library_manager = LibraryManager()
    playlist_service = PlaylistService(library_manager)
    playback_service = PlaybackService()

    # Test playlist name
    playlist_name = "enhanced_add_test"

    # Clean up from previous runs
    if library_manager.exists(playlist_name):
        library_manager.delete_playlist(playlist_name)
        print(f"🧹 Cleaned up existing playlist: {playlist_name}")

    print(f"\n🔧 Testing Enhanced /add Workflow")
    print("-" * 40)

    # Step 1: Create playlist and set as active
    print(f"1️⃣ Creating playlist...")
    success, msg = playlist_service.create_playlist(playlist_name)
    print(f"   Create result: {msg}")

    if not success:
        print("❌ Failed to create playlist")
        return

    # Simulate active playlist tracking
    guild_id = 12345
    user = "TestUser#1234"
    active_playlists = {guild_id: playlist_name}  # Simulates bot.active_playlists

    print(f"   🎯 Active playlist set: {active_playlists[guild_id]}")

    # Step 2: Test Enhanced /add workflow
    print(f"\n2️⃣ Testing Enhanced /add Command Simulation...")

    # Test input (YouTube URL)
    song_input = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    print(f"   📝 Input: {song_input}")
    print(f"   🔄 Simulating enhanced /add workflow...")

    try:
        # Step 2a: Process song like /play (this is the key enhancement)
        print(f"      🎵 Step 1: Processing song (like /play)...")
        success, response_message, song = await playback_service.play_request(
            user_input=song_input,
            guild_id=guild_id,
            requested_by=user,
            auto_play=False,  # Key difference: don't auto-play
        )

        if success and song:
            print(f"      ✅ Song processed successfully!")
            print(f"         - Display name: {song.display_name}")
            print(f"         - Source type: {song.source_type.value}")
            print(f"         - Status: {song.status.value}")
            print(f"         - Has metadata: {'Yes' if song.metadata else 'No'}")
            print(f"         - Has stream URL: {'Yes' if song.stream_url else 'No'}")
            print(f"         - Ready to play: {'✅ YES' if song.is_ready else '❌ NO'}")

            if song.metadata:
                print(f"         - Title: {song.metadata.title}")
                print(f"         - Duration: {song.duration_formatted}")

            # Step 2b: Add processed song to playlist
            print(f"      📋 Step 2: Adding to playlist...")
            title = song.metadata.title if song.metadata else song_input
            playlist_success, playlist_message = playlist_service.add_to_playlist(
                playlist_name, song.original_input, song.source_type, title
            )

            if playlist_success:
                print(f"      ✅ Added to playlist: {playlist_message}")
            else:
                print(f"      ❌ Failed to add to playlist: {playlist_message}")

        else:
            print(f"      ❌ Song processing failed: {response_message}")

    except Exception as e:
        print(f"      ❌ Exception during processing: {e}")

    # Step 3: Compare with old /add behavior
    print(f"\n3️⃣ Comparison: Old vs Enhanced /add")
    print("-" * 40)

    print(f"📊 OLD /add Behavior:")
    print(f"   1. Detect source type from URL")
    print(f"   2. Add raw URL to playlist (no processing)")
    print(f"   3. Song status: PENDING")
    print(f"   4. No metadata or stream URL")
    print(f"   5. Result: Song in playlist but not ready to play")

    print(f"\n📊 ENHANCED /add Behavior:")
    print(f"   1. Process song like /play (full processing)")
    print(f"   2. Extract metadata + stream URL")
    print(f"   3. Add processed song to queue AND playlist")
    print(f"   4. Song status: READY")
    print(f"   5. Result: Song ready to play immediately!")

    # Step 4: Verify playlist contents
    print(f"\n4️⃣ Verifying Playlist Contents...")

    playlist_info = playlist_service.get_playlist_info(playlist_name)
    if playlist_info:
        print(f"   📋 Playlist: {playlist_info['name']}")
        print(f"   📊 Total songs: {playlist_info['total_songs']}")

        if playlist_info["entries"]:
            for i, entry in enumerate(playlist_info["entries"], 1):
                print(f"   {i}. {entry['title']}")
                print(f"      - Source: {entry['source_type']}")
                print(f"      - Added: {entry['added_at']}")
        else:
            print(f"   📝 No entries found")
    else:
        print(f"   ❌ Could not get playlist info")

    # Step 5: Benefits summary
    print(f"\n💡 Enhanced /add Benefits")
    print("=" * 50)

    print(f"🎯 Key Improvements:")
    print(f"   1. **Immediate Playback**: Songs ready to play right after /add")
    print(f"   2. **Rich Metadata**: Proper title, duration, artist info")
    print(f"   3. **Consistent Experience**: Same processing as /play command")
    print(f"   4. **Better UX**: Detailed feedback with song info")
    print(f"   5. **Queue Integration**: Songs added to both playlist AND queue")

    print(f"\n🔄 Workflow Comparison:")
    print(f"   OLD: /add URL → Raw storage → Need /play later → Processing")
    print(f"   NEW: /add URL → Process immediately → Ready to play → Better UX")

    print(f"\n🎵 Use Cases:")
    print(f"   - Building playlist while music plays")
    print(f"   - Adding songs that are immediately playable")
    print(f"   - Getting rich metadata for playlist management")
    print(f"   - Seamless queue + playlist workflow")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    success, msg = playlist_service.delete_playlist(playlist_name)
    print(f"🗑️ {msg}")

    print(f"\n✅ Enhanced /add Command Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_enhanced_add_command())
