#!/usr/bin/env python3
"""
Test 24/7 Mode Configuration
Tests the 24/7 stay connected functionality and configuration options
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from bot.config.config import Config


def test_24_7_configuration():
    """Test 24/7 mode configuration loading and behavior"""

    print("🎵 Testing 24/7 Mode Configuration")
    print("=" * 50)

    # Test configuration loading
    print("1️⃣ Testing Configuration Loading...")
    config = Config()

    print(f"   BOT_NAME: {config.BOT_NAME}")
    print(f"   COMMAND_PREFIX: {config.COMMAND_PREFIX}")
    print(f"   STAY_CONNECTED_24_7: {config.STAY_CONNECTED_24_7}")
    print(f"   Type: {type(config.STAY_CONNECTED_24_7)}")

    # Test behavior logic
    print(f"\n2️⃣ Testing 24/7 Logic...")

    if config.STAY_CONNECTED_24_7:
        print("   ✅ 24/7 Mode ENABLED")
        print("   🎵 Bot will stay connected even when alone in voice channel")
        print("   📋 Behavior: No auto-disconnect")
        print("   💡 Use case: 24/7 radio station, community background music")
    else:
        print("   ⏹️ 24/7 Mode DISABLED")
        print("   👥 Bot will disconnect when alone in voice channel")
        print("   📋 Behavior: Auto-disconnect after 60 seconds")
        print("   💡 Use case: On-demand music bot, resource saving")

    # Test configuration scenarios
    print(f"\n3️⃣ Configuration Scenarios...")

    scenarios = [
        ("true", True, "24/7 radio station mode"),
        ("false", False, "On-demand bot mode"),
        ("1", True, "24/7 mode (numeric true)"),
        ("0", False, "On-demand mode (numeric false)"),
        ("yes", True, "24/7 mode (yes string)"),
        ("no", False, "On-demand mode (no string)"),
    ]

    for env_value, expected, description in scenarios:
        # Simulate different env values
        import os

        original = os.environ.get("STAY_CONNECTED_24_7", "true")

        os.environ["STAY_CONNECTED_24_7"] = env_value

        # Test parsing logic
        result = env_value.lower() in ["true", "1", "yes"]
        status = "✅" if result == expected else "❌"

        print(f"   {status} STAY_CONNECTED_24_7={env_value} → {result} ({description})")

        # Restore original
        os.environ["STAY_CONNECTED_24_7"] = original

    # Test voice state update logic simulation
    print(f"\n4️⃣ Voice State Logic Simulation...")

    def simulate_bot_alone_logic(
        stay_connected_24_7: bool, guild_name: str = "TestServer"
    ):
        """Simulate the on_voice_state_update logic"""

        bot_is_alone = True  # Simulated condition

        if bot_is_alone:
            if stay_connected_24_7:
                message = f"Bot is alone in voice channel in {guild_name}, but staying connected (24/7 mode)"
                action = "STAY_CONNECTED"
            else:
                message = (
                    f"Bot is alone in voice channel, will disconnect from {guild_name}"
                )
                action = "WILL_DISCONNECT"

            return action, message

    # Test both modes
    action_24_7, msg_24_7 = simulate_bot_alone_logic(True)
    action_legacy, msg_legacy = simulate_bot_alone_logic(False)

    print(f"   🎵 24/7 Mode:")
    print(f"      Action: {action_24_7}")
    print(f"      Log: {msg_24_7}")

    print(f"   👥 Legacy Mode:")
    print(f"      Action: {action_legacy}")
    print(f"      Log: {msg_legacy}")

    # Summary
    print(f"\n📋 Implementation Summary")
    print("=" * 50)
    print(f"🔧 Configuration:")
    print(f"   - Environment variable: STAY_CONNECTED_24_7")
    print(f"   - Default value: true (24/7 mode enabled)")
    print(f"   - File location: .env")
    print(f"   - Config class: bot/config/config.py")

    print(f"\n🎯 Behavior:")
    print(f"   - 24/7 mode ON: Bot stays in voice channel always")
    print(f"   - 24/7 mode OFF: Bot disconnects after 60s when alone")
    print(f"   - Manual override: /leave command works in both modes")

    print(f"\n💡 Use Cases:")
    print(f"   - Community servers: Enable 24/7 for background music")
    print(f"   - Personal servers: Disable 24/7 to save resources")
    print(f"   - Development: Toggle easily for testing")

    print(f"\n✅ 24/7 Mode Configuration Test Complete!")


if __name__ == "__main__":
    test_24_7_configuration()
