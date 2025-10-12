#!/usr/bin/env python3
"""
Quick validation script for refactored code
Tests imports and basic functionality
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        # Core modules
        from bot.config import config
        from bot.domain.entities.song import Song
        from bot.domain.entities.queue import QueueManager
        from bot.services.audio_service import audio_service
        from bot.services.playback import playback_service
        
        # Utility modules
        from bot.utils.bot_helpers import VoiceStateHelper, ErrorEmbedFactory
        from bot.utils.playlist_processors import PlaylistProcessor, PlaylistResultFactory
        from bot.utils.maintenance import CacheManager, MaintenanceScheduler
        
        # Commands
        from bot.commands import CommandRegistry
        
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration"""
    print("\n🧪 Testing configuration...")
    
    try:
        from bot.config import config
        from bot.config.config import Config
        
        # Test that creating new instances returns the same singleton
        config2 = Config()
        config3 = Config()
        
        # These should all be the same instance
        assert config2 is config3, "Multiple Config() calls should return same instance"
        assert config2 is Config._instance, "Config() should return the singleton instance"
        
        # Test that config has required attributes
        assert hasattr(config, 'BOT_NAME'), "Config should have BOT_NAME"
        assert hasattr(config, 'COMMAND_PREFIX'), "Config should have COMMAND_PREFIX"
        
        print(f"✅ Config loaded: {config.BOT_NAME}")
        print(f"✅ Singleton pattern working (config2 is config3: {config2 is config3})")
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_entities():
    """Test domain entities"""
    print("\n🧪 Testing entities...")
    
    try:
        from bot.domain.entities.song import Song
        from bot.domain.entities.queue import QueueManager
        from bot.domain.valueobjects.source_type import SourceType
        
        # Test Song creation
        song = Song(
            original_input="test",
            source_type=SourceType.YOUTUBE,  # Fixed: Use YOUTUBE instead of YOUTUBE_URL
            requested_by="test_user"
        )
        assert song.display_name == "test"
        print("✅ Song entity works")
        
        # Test Queue
        queue = QueueManager(guild_id=123)
        assert queue.queue_size == 0
        print("✅ QueueManager works")
        
        return True
    except Exception as e:
        print(f"❌ Entity error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_utilities():
    """Test utility modules"""
    print("\n🧪 Testing utilities...")
    
    try:
        from bot.utils.bot_helpers import ErrorEmbedFactory
        
        # Test error embed creation
        embed = ErrorEmbedFactory.create_error_embed("Test", "Description")
        assert embed.title == "❌ Test"
        print("✅ ErrorEmbedFactory works")
        
        return True
    except Exception as e:
        print(f"❌ Utility error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_version():
    """Test version information"""
    print("\n🧪 Testing version info...")
    
    try:
        from bot.__version__ import __version__, FEATURES
        
        print(f"✅ Version: {__version__}")
        print(f"✅ Features enabled: {sum(FEATURES.values())}/{len(FEATURES)}")
        return True
    except Exception as e:
        print(f"❌ Version error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 Discord Music Bot - Validation Tests")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Config", test_config),
        ("Entities", test_entities),
        ("Utilities", test_utilities),
        ("Version", test_version),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("=" * 60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Bot is ready to run.")
        return 0
    else:
        print("⚠️  Some tests failed. Please fix before running bot.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
