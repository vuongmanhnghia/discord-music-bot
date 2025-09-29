#!/usr/bin/env python3
"""
Simple syntax check for InteractionManager integration
"""

import ast
import os


def check_integration():
    """Check that InteractionManager is properly integrated"""

    print("🔍 Checking InteractionManager Integration...")

    music_bot_path = (
        "/home/nagih/Workspaces/noob/bot/discord-music-bot/bot/music_bot.py"
    )

    if not os.path.exists(music_bot_path):
        print("❌ music_bot.py not found")
        return False

    with open(music_bot_path, "r") as f:
        content = f.read()

    # Check imports
    checks = [
        (
            "InteractionManager import",
            "from .utils.interaction_manager import InteractionManager",
        ),
        ("InteractionManager init", "self.interaction_manager = InteractionManager()"),
        (
            "handle_long_operation usage",
            "await self.interaction_manager.handle_long_operation",
        ),
        (
            "Helper method _process_playlist_videos",
            "async def _process_playlist_videos",
        ),
        (
            "Helper method _process_add_playlist_videos",
            "async def _process_add_playlist_videos",
        ),
        (
            "Helper method _create_use_playlist_result",
            "def _create_use_playlist_result",
        ),
    ]

    results = []
    for check_name, check_text in checks:
        if check_text in content:
            print(f"✅ {check_name}")
            results.append(True)
        else:
            print(f"❌ {check_name}")
            results.append(False)

    # Check syntax
    try:
        ast.parse(content)
        print("✅ Python syntax valid")
        syntax_ok = True
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        syntax_ok = False

    all_checks_passed = all(results) and syntax_ok

    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✅ InteractionManager integration looks good!")
        print("🎯 Critical commands should now have timeout protection:")
        print("   • /play - YouTube playlist processing")
        print("   • /add - Adding playlists to active playlist")
        print("   • /use - Loading playlists to queue")
    else:
        print("❌ Integration issues detected")
    print("=" * 50)

    return all_checks_passed


if __name__ == "__main__":
    check_integration()
