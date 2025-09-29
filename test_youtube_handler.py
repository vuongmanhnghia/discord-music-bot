#!/usr/bin/env python3
"""
Test script để kiểm tra logic mới của YouTube playlist handler
"""

import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from utils.youtube_playlist_handler import YouTubePlaylistHandler


def test_url_detection():
    """Test URL detection logic"""
    test_cases = [
        # Single video URLs (should NOT be treated as playlist)
        (
            "https://www.youtube.com/watch?v=qbX-TP_MtcQ&list=RDqbX-TP_MtcQ&start_radio=1",
            False,
            True,
        ),
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmRdnEQy1Z-8j5M5C",
            False,
            True,
        ),
        ("https://youtu.be/dQw4w9WgXcQ?list=PLrAXtmRdnEQy1Z", False, True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False, False),
        ("https://youtu.be/dQw4w9WgXcQ", False, False),
        # Playlist URLs (should be treated as playlist)
        (
            "https://www.youtube.com/playlist?list=RDqbX-TP_MtcQ&start_radio=1",
            True,
            False,
        ),
        ("https://www.youtube.com/playlist?list=PLrAXtmRdnEQy1Z-8j5M5C", True, False),
        ("https://music.youtube.com/playlist?list=PLrAXtmRdnEQy1Z", True, False),
        # Search queries (should NOT be treated as playlist)
        ("never gonna give you up", False, False),
        ("Rick Astley", False, False),
    ]

    print("🧪 Testing URL Detection Logic")
    print("=" * 60)

    all_passed = True

    for url, expected_is_playlist, expected_is_single_with_playlist in test_cases:
        is_playlist = YouTubePlaylistHandler.is_playlist_url(url)
        is_single = YouTubePlaylistHandler.is_single_video_with_playlist(url)

        playlist_ok = is_playlist == expected_is_playlist
        single_ok = is_single == expected_is_single_with_playlist

        status = "✅" if (playlist_ok and single_ok) else "❌"
        if not (playlist_ok and single_ok):
            all_passed = False

        print(f"{status} {url[:50]}{'...' if len(url) > 50 else ''}")
        print(
            f"   📋 Playlist: {is_playlist} (expected: {expected_is_playlist}) {'✅' if playlist_ok else '❌'}"
        )
        print(
            f"   🎵 Single+List: {is_single} (expected: {expected_is_single_with_playlist}) {'✅' if single_ok else '❌'}"
        )
        print()

    print("=" * 60)
    if all_passed:
        print("🎉 All tests PASSED!")
        return True
    else:
        print("💥 Some tests FAILED!")
        return False


if __name__ == "__main__":
    success = test_url_detection()

    if success:
        print("\n✅ Logic updated successfully!")
        print("\n📝 Summary of changes:")
        print("• Single video URLs with playlist parameter → treated as SINGLE video")
        print("• Explicit playlist URLs → treated as FULL PLAYLIST")
        print("\n🔧 Updated behavior:")
        print("• /play https://youtube.com/watch?v=xyz&list=abc → plays only 1 song")
        print("• /play https://youtube.com/playlist?list=abc → plays entire playlist")
        print("• /add https://youtube.com/watch?v=xyz&list=abc → adds only 1 song")
        print("• /add https://youtube.com/playlist?list=abc → adds entire playlist")
    else:
        print("\n❌ Tests failed! Please check the implementation.")
        sys.exit(1)
