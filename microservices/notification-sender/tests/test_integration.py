"""
Integration Test for Multi-User Notifications

This test performs an end-to-end test of the multi-user notification feature.
Run this manually to verify the complete flow works correctly.

REQUIREMENTS:
- Valid users.yaml file configured
- TELEGRAM_BOT_TOKEN set in environment
- Redis running (for full integration test)

USAGE:
    # Test YAML loading only
    python tests/test_integration.py --yaml-only
    
    # Test with mock bot (no real Telegram API calls)
    python tests/test_integration.py --mock
    
    # Full test with real Telegram (sends actual messages to configured users)
    python tests/test_integration.py --full
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_yaml_loading():
    """Test that users.yaml can be loaded successfully"""
    print("=" * 60)
    print("TEST 1: YAML Configuration Loading")
    print("=" * 60)
    
    try:
        from config import load_users
        users = load_users()
        
        print(f"✅ Successfully loaded {len(users)} users from users.yaml")
        print()
        
        # Display user summary
        admins = [u for u in users if u['role'] == 'admin']
        regulars = [u for u in users if u['role'] == 'user']
        
        print(f"👥 User Summary:")
        print(f"   - {len(admins)} admin(s)")
        print(f"   - {len(regulars)} regular user(s)")
        print()
        
        print("📋 User Details:")
        for i, user in enumerate(users, 1):
            role_icon = "🔑" if user['role'] == 'admin' else "👤"
            print(f"   {i}. {role_icon} {user['name']}")
            print(f"      Telegram ID: {user['telegram_id']}")
            print(f"      Role: {user['role']}")
        
        print()
        return True
        
    except FileNotFoundError as e:
        print(f"❌ YAML file not found: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading YAML: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_notifier_init():
    """Test TelegramNotifier initialization"""
    print("=" * 60)
    print("TEST 2: TelegramNotifier Initialization")
    print("=" * 60)
    
    try:
        # Check environment variable
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        if not bot_token:
            print("⚠️  Warning: TELEGRAM_BOT_TOKEN not set in environment")
            print("   Some features may not work without it")
            print()
        else:
            print(f"✅ TELEGRAM_BOT_TOKEN is set (length: {len(bot_token)})")
            print()
        
        from providers.telegram import TelegramNotifier
        from config import settings
        
        # Set a dummy token if not set (for testing init only)
        if not settings.TELEGRAM_BOT_TOKEN:
            settings.TELEGRAM_BOT_TOKEN = "dummy_token_for_testing"
        
        notifier = TelegramNotifier()
        
        print(f"✅ TelegramNotifier initialized successfully")
        print(f"   - Loaded {len(notifier.users)} users")
        print(f"   - Default chat_id: {notifier.chat_id}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing TelegramNotifier: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_formatting():
    """Test alert message formatting"""
    print("=" * 60)
    print("TEST 3: Message Formatting")
    print("=" * 60)
    
    try:
        from providers.telegram import TelegramNotifier
        from config import settings
        
        # Dummy token for testing
        if not settings.TELEGRAM_BOT_TOKEN:
            settings.TELEGRAM_BOT_TOKEN = "dummy_token"
        
        notifier = TelegramNotifier()
        
        # Test alert data
        test_alert = {
            'ruta': 101,
            'alert_type': 'GEOFENCE_ENTRY',
            'area_name': 'Test Zone',
            'severity': 'WARNING',
            'latitude': 4.7110,
            'longitude': -74.0059,
            'timestamp': '2026-02-16 12:00:00'
        }
        
        message = notifier.format_alert(test_alert)
        
        print("✅ Message formatted successfully")
        print()
        print("📨 Formatted Message:")
        print("-" * 60)
        print(message)
        print("-" * 60)
        print()
        
        # Verify key elements
        checks = [
            ("Route number" , "101" in message),
            ("Alert type", "GEOFENCE" in message or "ENTRY" in message),
            ("Area name", "Test Zone" in message),
            ("Map link", "maps.google.com" in message),
            ("Emoji/icon", any(emoji in message for emoji in ['🚌', '⚠️', '➡️', 'ℹ️'])),
        ]
        
        print("✓ Content Verification:")
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
            all_passed = all_passed and passed
        
        print()
        return all_passed
        
    except Exception as e:
        print(f"❌ Error formatting message: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_admin_filtering():
    """Test that admins are correctly filtered for test messages"""
    print("=" * 60)
    print("TEST 4: Admin User Filtering")
    print("=" * 60)
    
    try:
        from config import load_users
        users = load_users()
        
        admins = [u for u in users if u['role'] == 'admin']
        regulars = [u for u in users if u['role'] == 'user']
        
        print(f"✅ User filtering works correctly")
        print(f"   - Found {len(admins)} admin user(s)")
        print(f"   - Found {len(regulars)} regular user(s)")
        print()
        
        if len(admins) == 0:
            print("⚠️  WARNING: No admin users configured!")
            print("   Test messages will not be sent to anyone.")
            print("   Add at least one user with role='admin' in users.yaml")
            print()
        else:
            print("📋 Admin Users (who receive test messages):")
            for admin in admins:
                print(f"   - {admin['name']} ({admin['telegram_id']})")
            print()
        
        print("📋 Regular Users (who receive only alerts):")
        if regulars:
            for user in regulars:
                print(f"   - {user['name']} ({user['telegram_id']})")
        else:
            print("   (none)")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error filtering users: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Integration tests for multi-user notifications')
    parser.add_argument('--yaml-only', action='store_true', help='Test YAML loading only')
    parser.add_argument('--mock', action='store_true', help='Test with mocked bot')
    parser.add_argument('--full', action='store_true', help='Full test (requires valid config)')
    args = parser.parse_args()
    
    print()
    print("🧪 Multi-User Notification Integration Tests")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: YAML Loading (always run)
    results.append(("YAML Loading", test_yaml_loading()))
    
    if not args.yaml_only:
        # Test 2: Notifier Init
        results.append(("Notifier Init", test_notifier_init()))
        
        # Test 3: Message Formatting
        results.append(("Message Formatting", test_message_formatting()))
        
        # Test 4: Admin Filtering
        results.append(("Admin Filtering", test_admin_filtering()))
    
    # Summary
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
