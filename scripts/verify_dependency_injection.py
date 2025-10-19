#!/usr/bin/env python3
"""
Comprehensive Dependency Injection Verification
Checks that all services use proper dependency injection patterns
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


def check_file(file_path: Path, patterns: List[Tuple[str, str]]) -> List[dict]:
    """Check file for anti-patterns"""
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

                    # Skip TYPE_CHECKING imports and lazy imports (acceptable)
                    if (
                        "TYPE_CHECKING" in line_content
                        or "if playback_service is None" in line_content
                        or "if audio_service is None" in line_content
                    ):
                        continue

                    findings.append(
                        {
                            "pattern": pattern_name,
                            "line": line_num,
                            "content": line_content,
                            "file": str(file_path),
                        }
                    )

        return findings
    except Exception as e:
        print(f"⚠️ Error reading {file_path}: {e}")
        return []


def scan_directory(
    directory: str, patterns: List[Tuple[str, str]], exclude_dirs: set = None
):
    """Scan directory for anti-patterns"""
    if exclude_dirs is None:
        exclude_dirs = {
            "__pycache__",
            "venv",
            ".git",
            "node_modules",
            "scripts",
            "tests",
            "cache",
            "data",
        }

    all_findings = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                findings = check_file(file_path, patterns)
                all_findings.extend(findings)

    return all_findings


def check_handler_type_hints():
    """Check that all command handlers have proper type hints"""
    handler_files = [
        "bot/commands/basic_commands.py",
        "bot/commands/playback_commands.py",
        "bot/commands/queue_commands.py",
        "bot/commands/playlist_commands.py",
        "bot/commands/advanced_commands.py",
    ]

    issues = []

    for file_path in handler_files:
        path = Path(file_path)
        if not path.exists():
            continue

        with open(path, "r") as f:
            content = f.read()

        # Check for MusicBot type hint in __init__
        if (
            "def __init__(self, bot):" in content
            and 'def __init__(self, bot: "MusicBot")' not in content
        ):
            issues.append(f"{file_path}: Missing MusicBot type hint in __init__")

        # Check for TYPE_CHECKING import
        if "TYPE_CHECKING" not in content:
            issues.append(f"{file_path}: Missing TYPE_CHECKING import")

    return issues


def check_base_handler():
    """Check BaseCommandHandler has audio_service"""
    path = Path("bot/commands/__init__.py")
    if not path.exists():
        return ["BaseCommandHandler file not found"]

    with open(path, "r") as f:
        content = f.read()

    issues = []

    if "self.audio_service = bot.audio_service" not in content:
        issues.append("BaseCommandHandler: Missing self.audio_service initialization")

    if "from ..services import audio_service" in content:
        issues.append("BaseCommandHandler: Still has global audio_service import")

    return issues


print("🔍 Comprehensive Dependency Injection Audit\n")
print("=" * 70)

# Anti-patterns to detect
anti_patterns = [
    (
        "Global service import (command)",
        r"from\s+\.\.services.*import\s+(audio_service|playback_service|playlist_service)\s*$",
    ),
    (
        "Global singleton usage",
        r"(audio_service|playback_service|playlist_service)\s*=\s*\w+Service\(\)",
    ),
]

print("\n📊 Scanning for anti-patterns...\n")

# Scan bot directory (exclude utils which may have lazy imports)
findings = scan_directory("bot/commands", anti_patterns)

# Check utilities separately (they're allowed lazy imports)
util_patterns = [
    (
        "Potential issue",
        r"from\s+\.\.services.*import\s+(audio_service|playback_service|playlist_service)\s*$",
    ),
]
util_findings = scan_directory("bot/utils", util_patterns)

if not findings:
    print("✅ Commands: No anti-patterns found in command handlers!")
else:
    print(f"❌ Found {len(findings)} anti-pattern(s) in commands:\n")
    for finding in findings:
        print(f"  {finding['file']}:{finding['line']}")
        print(f"    Pattern: {finding['pattern']}")
        print(f"    Code: {finding['content']}\n")

if util_findings:
    print(f"\n⚠️  Found {len(util_findings)} global import(s) in utilities:")
    print("   (These are acceptable if they use lazy imports)\n")
    for finding in util_findings:
        print(f"  {finding['file']}:{finding['line']}")
        print(f"    Code: {finding['content']}\n")

print("\n" + "=" * 70)
print("✅ Type Hints Check:\n")

type_issues = check_handler_type_hints()
if not type_issues:
    print("✅ All command handlers have proper MusicBot type hints")
else:
    print("❌ Type hint issues:")
    for issue in type_issues:
        print(f"  - {issue}")

print("\n" + "=" * 70)
print("✅ BaseCommandHandler Check:\n")

base_issues = check_base_handler()
if not base_issues:
    print("✅ BaseCommandHandler properly configured")
else:
    print("❌ BaseCommandHandler issues:")
    for issue in base_issues:
        print(f"  - {issue}")

print("\n" + "=" * 70)
print("📊 Summary:\n")

total_command_issues = len(findings) + len(type_issues) + len(base_issues)

if total_command_issues == 0:
    print("✅ All command handlers use proper dependency injection!")
    print("✅ All type hints in place")
    print("✅ BaseCommandHandler configured correctly")
    print("✅ No global service singletons in commands")
    print("\n🎉 Dependency injection implementation is PERFECT!")
else:
    print(f"⚠️  Found {total_command_issues} issue(s) in commands that need attention")
    print(f"ℹ️  Utilities have {len(util_findings)} lazy imports (acceptable)")

print("\n" + "=" * 70)
print("Pattern Guide:")
print("=" * 70)
print("✅ GOOD:")
print("   class Handler(BaseCommandHandler):")
print("       def __init__(self, bot: 'MusicBot'):")
print("           super().__init__(bot)")
print("           self.audio_service = bot.audio_service")
print()
print("❌ BAD:")
print("   from ..services import audio_service  # Global import")
print("   audio_service.get_queue_manager()     # Using global")
print()
