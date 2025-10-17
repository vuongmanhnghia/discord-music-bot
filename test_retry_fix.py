#!/usr/bin/env python3
"""
Test script to verify RetryStrategy fix
Run this AFTER restarting the bot to confirm the fix is working
"""

import asyncio
import sys
from bot.services.retry_strategy import RetryStrategy
from bot.services.processing import YouTubeService
from bot.domain.entities.song import Song
from bot.domain.valueobjects.source_type import SourceType


async def test_retry_strategy():
    """Test RetryStrategy with correct parameters"""
    print("=" * 60)
    print("Testing RetryStrategy...")
    print("=" * 60)

    # Test 1: Create with new parameters
    try:
        strategy = RetryStrategy(
            max_attempts=3,
            base_delay=1.0,
            backoff_factor=2.0,
            timeout=30,
        )
        print("✅ RetryStrategy created with new parameters")
    except Exception as e:
        print(f"❌ Failed to create RetryStrategy: {e}")
        return False

    # Test 2: Test execute method
    async def test_op():
        return "success"

    try:
        result = await strategy.execute(test_op, "test operation")
        if result == "success":
            print("✅ RetryStrategy.execute() works correctly")
        else:
            print(f"❌ Unexpected result: {result}")
            return False
    except Exception as e:
        print(f"❌ execute() failed: {e}")
        return False

    return True


async def test_youtube_processing():
    """Test YouTube processing with playlist URL"""
    print("\n" + "=" * 60)
    print("Testing YouTube Processing...")
    print("=" * 60)

    service = YouTubeService()

    # Test with the exact URL that was failing
    test_url = "https://www.youtube.com/watch?v=wITADc8U2HQ&list=PLYflXW11sPy-5c3kXTgmdkyf9CtpofGby&index=2"

    song = Song(
        original_input=test_url,
        requested_by="test_script",
        guild_id=999,
        source_type=SourceType.YOUTUBE,
    )

    print(f"Processing: {test_url[:50]}...")

    try:
        result = await service.process(song)

        if result:
            print(f"✅ Processing successful!")
            print(f"   Song: {song.display_name}")
            print(f"   Has stream URL: {bool(song.stream_url)}")
            return True
        else:
            print(f"❌ Processing failed: {song.error_message}")
            return False

    except Exception as e:
        print(f"❌ Exception during processing: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    print("\n🔍 Verifying RetryStrategy Fix\n")

    # Run tests
    test1_ok = await test_retry_strategy()
    test2_ok = await test_youtube_processing()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"RetryStrategy test: {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"YouTube processing test: {'✅ PASS' if test2_ok else '❌ FAIL'}")

    if test1_ok and test2_ok:
        print("\n🎉 All tests PASSED! Bot should work correctly now.")
        print("   You can safely use /use playlist command.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests FAILED! Please restart the bot and try again.")
        print("   Steps:")
        print("   1. Stop the bot (Ctrl+C)")
        print("   2. Run: python3 run_bot.py")
        print("   3. Test again with /use playlist")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
