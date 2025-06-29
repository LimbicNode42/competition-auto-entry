#!/usr/bin/env python3
"""
Test script for the competition auto-entry system.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all modules can be imported successfully."""
    try:
        from src.utils.logger import setup_logging
        from src.utils.config import AppConfig, PersonalInfo
        from src.core.competition import Competition, CompetitionStatus
        from src.core.tracker import CompetitionTracker
        from src.core.scraper import CompetitionScraper
        from src.core.form_detector import FormDetector
        from src.integrations.aggregators import AggregatorManager
        from src.integrations.social_media import SocialMediaManager
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_logger():
    """Test logger setup."""
    try:
        from src.utils.logger import setup_logging
        logger = setup_logging(log_level="INFO")
        logger.info("Test log message")
        print("✅ Logger setup successful!")
        return True
        
    except Exception as e:
        print(f"❌ Logger setup error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    try:
        from src.utils.config import PersonalInfo, SocialMediaCredentials, AppConfig
        
        # Test creating config objects
        personal_info = PersonalInfo(
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )
        
        social_media = SocialMediaCredentials()
        
        config = AppConfig(
            personal_info=personal_info,
            social_media=social_media
        )
        
        print("✅ Configuration models working!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_database():
    """Test database initialization."""
    try:
        from src.core.tracker import CompetitionTracker
        
        # Initialize with a test database
        tracker = CompetitionTracker("data/test_competitions.db")
        print("✅ Database initialization successful!")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Competition Auto-Entry System Setup")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Logger Tests", test_logger),
        ("Configuration Tests", test_config),
        ("Database Tests", test_database),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("1. Copy config/config.example.json to config/config.json")
        print("2. Fill in your personal information and credentials")
        print("3. Run: python main.py --help")
    else:
        print("❌ Some tests failed. Please check the setup.")
        sys.exit(1)

if __name__ == "__main__":
    main()
