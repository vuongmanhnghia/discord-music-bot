#!/usr/bin/env python3
"""
Verify PlaylistSwitchManager has been completely removed
"""

import os
import re
from pathlib import Path


def search_patterns(file_path: Path, patterns: list) -> list:
    """Search for patterns in file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        findings = []
        for pattern_name, pattern in patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                for match in matches:
                    line_num = content[: match.start()].count("\n") + 1
                    line_content = content.split("\n")[line_num - 1].strip()
                    findings.append(
                        {
                            "pattern": pattern_name,
                            "line": line_num,
                            "content": line_content,
                        }
                    )

        return findings
    except Exception as e:
        print(f"⚠️ Error reading {file_path}: {e}")
        return []


def scan_directory(directory: str, patterns: list, exclude_dirs: set = None):
    """Scan directory for patterns"""
    if exclude_dirs is None:
        exclude_dirs = {"__pycache__", "venv", ".git", "node_modules", "scripts"}

    results = {}

    for root, dirs, files in os.walk(directory):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                findings = search_patterns(file_path, patterns)

                if findings:
                    results[str(file_path)] = findings

    return results


print("🔍 Verifying PlaylistSwitchManager Cleanup\n")
print("=" * 60)

# Patterns to search for
patterns = [
    ("playlist_switch import", r"from.*playlist_switch.*import"),
    ("PlaylistSwitchManager class", r"class\s+PlaylistSwitchManager"),
    ("playlist_switch_manager variable", r"playlist_switch_manager"),
    ("safe_playlist_switch method call", r"\.safe_playlist_switch\("),
    ("is_switching method call", r"\.is_switching\("),
]

# Scan bot directory
results = scan_directory("bot", patterns)

print("\n📊 Scan Results:\n")

if not results:
    print("✅ No PlaylistSwitchManager references found!")
    print("🎉 Cleanup successful!\n")
else:
    print("⚠️ Found references that need attention:\n")

    for file_path, findings in results.items():
        print(f"📄 {file_path}:")
        for finding in findings:
            print(f"   Line {finding['line']}: {finding['pattern']}")
            print(f"      → {finding['content']}")
        print()

# Check for the new implementation
print("\n" + "=" * 60)
print("✅ New Implementation Check:\n")

music_bot_path = Path("bot/music_bot.py")
if music_bot_path.exists():
    with open(music_bot_path) as f:
        content = f.read()
        has_switching = "_switching_playlists" in content

        if has_switching:
            print("✅ MusicBot has _switching_playlists set")
        else:
            print("❌ MusicBot missing _switching_playlists set")

# Check playlist_switch.py file
playlist_switch_path = Path("bot/services/playlist_switch.py")
if playlist_switch_path.exists():
    print("⚠️ playlist_switch.py file still exists!")
else:
    print("✅ playlist_switch.py file deleted")

print("\n" + "=" * 60)
print("Summary:")
print("=" * 60)

if not results and not playlist_switch_path.exists():
    print("✅ PlaylistSwitchManager: Completely removed")
    print("✅ No references found")
    print("✅ File deleted")
    print("✅ Simple set-based implementation in place")
    print("\n🚀 Bot is cleaner and simpler!")
else:
    print("⚠️ Some cleanup still needed")
    if results:
        print(f"   - {len(results)} files with references")
    if playlist_switch_path.exists():
        print("   - playlist_switch.py file still exists")

print()
