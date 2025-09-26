#!/usr/bin/env python3
"""
Test script for the new clean architecture music bot
Tests the complete flow without Discord integration
"""

import asyncio
import sys
from pathlib import Path

# Test imports
try:
    from bot.domain.models import InputAnalyzer, Song, SourceType, SongStatus
    from bot.services.processing import SongProcessingService
    from bot.services.playback import playback_service
    from bot.config import config
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


async def test_system_requirements():
    """Test system requirements"""
    print("\\n🔧 Testing System Requirements...")
    
    # Test yt-dlp availability
    import subprocess
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ yt-dlp found: {result.stdout.strip()}")
        else:
            print("❌ yt-dlp not working properly")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ yt-dlp not found in PATH")
    
    # Test ffmpeg availability (for Discord audio)
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\\n')[0]
            print(f"✅ ffmpeg found: {version_line}")
        else:
            print("❌ ffmpeg not working properly")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️ ffmpeg not found (required for Discord audio)")


async def test_input_analysis():
    """Test input analysis and song creation"""
    print("\\n🔍 Testing Input Analysis...")
    
    test_inputs = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ", 
        "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh",
        "https://soundcloud.com/test/track",
        "never gonna give you up",  # Search query
        "Rick Astley Never Gonna Give You Up",
    ]
    
    for user_input in test_inputs:
        song = InputAnalyzer.create_song(
            user_input=user_input,
            requested_by="TestUser",
            guild_id=12345
        )
        
        print(f"  Input: {user_input}")
        print(f"    Source Type: {song.source_type.value}")
        print(f"    Status: {song.status.value}")
        print(f"    Display Name: {song.display_name}")
        print()


async def test_song_processing():
    """Test song processing service"""
    print("\\n🎵 Testing Song Processing...")
    
    processing_service = SongProcessingService()
    
    # Test different types of inputs
    test_cases = [
        ("YouTube URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("Search Query", "Rick Astley Never Gonna Give You Up"),
        ("Spotify URL", "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"),
    ]
    
    for test_name, user_input in test_cases:
        print(f"\\n  Testing {test_name}: {user_input}")
        
        try:
            # Create song
            song = InputAnalyzer.create_song(
                user_input=user_input,
                requested_by="TestUser",
                guild_id=12345
            )
            
            print(f"    Created song: {song.source_type.value}")
            
            # Process song (with timeout to avoid hanging)
            try:
                success = await asyncio.wait_for(
                    processing_service.process_song(song), 
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print("    ⏰ Processing timed out (30s)")
                continue
            
            if success and song.is_ready:
                print("    ✅ Processing successful!")
                print(f"    Title: {song.metadata.title}")
                print(f"    Artist: {song.metadata.artist}")
                print(f"    Duration: {song.metadata.duration_formatted}")
                print(f"    Has Stream URL: {'Yes' if song.stream_url else 'No'}")
            elif success:
                print("    ⚠️ Processing completed but song not ready")
                print(f"    Status: {song.status.value}")
                if song.error_message:
                    print(f"    Error: {song.error_message}")
            else:
                print("    ❌ Processing failed")
                print(f"    Status: {song.status.value}")
                if song.error_message:
                    print(f"    Error: {song.error_message}")
                    
        except Exception as e:
            print(f"    ❌ Exception: {e}")


async def test_playback_flow():
    """Test complete playback flow"""
    print("\\n🎧 Testing Complete Playback Flow...")
    
    # Test the main flow without Discord
    test_guild_id = 12345
    test_user = "TestUser"
    
    test_queries = [
        "Rick Astley Never Gonna Give You Up",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        # Note: Spotify will fail without proper connection, but that's expected
    ]
    
    for query in test_queries:
        print(f"\\n  Testing playback request: {query}")
        
        try:
            # This is the main flow that would be called by Discord command
            success, message, song = await playback_service.play_request(
                user_input=query,
                guild_id=test_guild_id,
                requested_by=test_user,
                auto_play=False  # Don't auto-play in tests
            )
            
            if success and song:
                print("    ✅ Play request successful")
                print(f"    Message: {message}")
                print(f"    Song: {song.display_name}")
                print(f"    Status: {song.status.value}")
                print(f"    Source: {song.source_type.value}")
                
                # Wait a moment for processing
                await asyncio.sleep(3)
                
                # Check final status
                print(f"    Final Status: {song.status.value}")
                if song.metadata:
                    print(f"    Final Metadata: {song.metadata.display_name}")
                if song.error_message:
                    print(f"    Error: {song.error_message}")
                    
            else:
                print("    ❌ Play request failed")
                print(f"    Message: {message}")
                
        except Exception as e:
            print(f"    ❌ Exception in playback flow: {e}")
    
    # Test queue status
    print("\\n  Testing queue status...")
    try:
        status = await playback_service.get_queue_status(test_guild_id)
        if status:
            print("    ✅ Queue status retrieved")
            print(f"    Current song: {status['current_song'].display_name if status['current_song'] else 'None'}")
            print(f"    Queue position: {status['position']}")
            print(f"    Upcoming songs: {len(status['upcoming_songs'])}")
        else:
            print("    ⚠️ No queue status available")
    except Exception as e:
        print(f"    ❌ Queue status error: {e}")


async def run_all_tests():
    """Run all tests"""
    print("🚀 Starting Clean Architecture Music Bot Tests")
    print("=" * 50)
    
    await test_system_requirements()
    await test_input_analysis()
    await test_song_processing()
    await test_playback_flow()
    
    print("\\n" + "=" * 50)
    print("✅ All tests completed!")
    print("\\nIf you see any ❌ errors above, please address them before running the bot.")
    print("\\n🎵 The bot implements the following flow:")
    print("1. Input Analysis (URL/search detection)")
    print("2. Song Object Creation")
    print("3. Metadata Extraction (Spotify API / yt-dlp)")
    print("4. Queue Management")
    print("5. Playback Orchestration")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\\n🛑 Tests cancelled by user")
    except Exception as e:
        print(f"\\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
