#!/usr/bin/env python3
"""
Setup script for the Competition Auto-Entry System.
Helps users get started quickly.
"""

import os
import shutil
import json
from pathlib import Path

def setup_config():
    """Setup configuration file from example."""
    config_path = Path("config/config.json")
    example_path = Path("config/config.example.json")
    
    if config_path.exists():
        print("✅ Configuration file already exists")
        return True
    
    if not example_path.exists():
        print("❌ Example configuration file not found")
        return False
    
    try:
        shutil.copy(example_path, config_path)
        print("✅ Created config/config.json from example")
        print("📝 Please edit config/config.json with your personal information")
        return True
    except Exception as e:
        print(f"❌ Error creating config file: {e}")
        return False

def check_directories():
    """Ensure required directories exist."""
    directories = ["data", "logs", ".vscode"]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("🎉 Competition Auto-Entry System Setup Complete!")
    print("="*60)
    print("\n📋 Next Steps:")
    print("1. Edit config/config.json with your personal information")
    print("2. Add your social media credentials (optional)")
    print("3. Review aggregator_sites.json for competition sources")
    print("4. Run the system:")
    print("   - Test run: python main.py --dry-run --verbose")
    print("   - Real run: python main.py")
    print("   - Help: python main.py --help")
    
    print("\n🛡️ Safety Features:")
    print("- Only enters confirmed free competitions")
    print("- Rate limiting to avoid being blocked")
    print("- Comprehensive logging and error handling")
    print("- Database tracking of all activities")
    
    print("\n⚠️ Important:")
    print("- Always verify competition legitimacy")
    print("- Respect website terms of service")
    print("- Start with --dry-run to test first")
    print("- Monitor logs for any issues")
    
    print("\n📚 Example Usage:")
    print("python example.py          # Run example demo")
    print("python test_setup.py       # Test system setup")
    print("python main.py --dry-run   # Test without entering")
    print("python main.py -m 5        # Enter max 5 competitions")

def main():
    """Main setup function."""
    print("🔧 Setting up Competition Auto-Entry System...")
    print("-" * 50)
    
    # Check and create directories
    check_directories()
    
    # Setup configuration
    setup_config()
    
    # Print next steps
    print_next_steps()

if __name__ == "__main__":
    main()
