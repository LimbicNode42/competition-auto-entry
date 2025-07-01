#!/usr/bin/env python3
"""
Interactive setup script for personal configuration
This script helps you safely configure your personal details for competition entry.
"""

import json
import sys
from pathlib import Path
from getpass import getpass

def load_current_config():
    """Load the current configuration"""
    config_path = Path("config/config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    else:
        print("❌ Config file not found. Please ensure config/config.json exists.")
        sys.exit(1)

def update_personal_info(config):
    """Interactively update personal information"""
    print("\n📝 Personal Information Setup")
    print("=" * 50)
    print("Please provide your personal details for competition entry.")
    print("This information will be stored locally and used to fill forms automatically.")
    print("Leave blank to keep current value.\n")
    
    personal_info = config.get("personal_info", {})
    
    fields = [
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("email", "Email Address"),
        ("phone", "Phone Number (with country code, e.g., +61-xxx-xxx-xxx)"),
        ("address_line1", "Address Line 1"),
        ("address_line2", "Address Line 2 (optional)"),
        ("city", "City"),
        ("state", "State/Province"),
        ("postal_code", "Postal/Zip Code"),
        ("country", "Country"),
        ("date_of_birth", "Date of Birth (YYYY-MM-DD)")
    ]
    
    for field, description in fields:
        current_value = personal_info.get(field, "")
        if current_value and field != "email":  # Always show email for verification
            prompt = f"{description} [{current_value}]: "
        else:
            prompt = f"{description}: "
        
        new_value = input(prompt).strip()
        if new_value:
            personal_info[field] = new_value
        elif not current_value:
            print(f"⚠️  Warning: {description} is required for most competitions")
    
    config["personal_info"] = personal_info
    return config

def update_preferences(config):
    """Update entry preferences"""
    print("\n⚙️  Entry Preferences")
    print("=" * 50)
    
    # Max daily entries
    current_max = config.get("max_daily_entries", 25)
    max_entries = input(f"Maximum daily entries [{current_max}]: ").strip()
    if max_entries:
        try:
            config["max_daily_entries"] = int(max_entries)
        except ValueError:
            print("Invalid number, keeping current value")
    
    # Filters
    filters = config.get("filters", {})
    
    print("\n🔍 Competition Filters")
    print("These help ensure you only enter appropriate competitions:")
    
    # Countries
    current_countries = filters.get("allowed_countries", ["AU", "NZ", "US", "UK", "CA"])
    print(f"Currently allowed countries: {', '.join(current_countries)}")
    new_countries = input("Allowed countries (comma-separated, e.g., AU,NZ,US): ").strip()
    if new_countries:
        filters["allowed_countries"] = [c.strip().upper() for c in new_countries.split(",")]
    
    config["filters"] = filters
    return config

def verify_config(config):
    """Show final configuration for verification"""
    print("\n✅ Configuration Summary")
    print("=" * 50)
    
    personal = config["personal_info"]
    print(f"Name: {personal.get('first_name', 'NOT SET')} {personal.get('last_name', 'NOT SET')}")
    print(f"Email: {personal.get('email', 'NOT SET')}")
    print(f"Phone: {personal.get('phone', 'NOT SET')}")
    print(f"Address: {personal.get('address_line1', 'NOT SET')}, {personal.get('city', 'NOT SET')}")
    print(f"Country: {personal.get('country', 'NOT SET')}")
    print(f"Date of Birth: {personal.get('date_of_birth', 'NOT SET')}")
    
    print(f"\nMax daily entries: {config.get('max_daily_entries', 25)}")
    print(f"Allowed countries: {', '.join(config.get('filters', {}).get('allowed_countries', []))}")
    
    print("\n⚠️  IMPORTANT REMINDERS:")
    print("• Only enter competitions you're eligible for")
    print("• This system respects website terms of service")
    print("• Your data is stored locally and encrypted")
    print("• You can modify config/config.json anytime")
    
    return input("\nSave this configuration? (y/N): ").lower().startswith('y')

def main():
    """Main setup function"""
    print("🏆 Competition Auto-Entry System - Personal Configuration Setup")
    print("=" * 70)
    
    # Load current config
    config = load_current_config()
    
    # Update personal info
    config = update_personal_info(config)
    
    # Update preferences
    config = update_preferences(config)
    
    # Verify and save
    if verify_config(config):
        # Create backup
        backup_path = Path("config/config.backup.json")
        if Path("config/config.json").exists():
            with open("config/config.json", 'r') as f:
                backup_config = json.load(f)
            with open(backup_path, 'w') as f:
                json.dump(backup_config, f, indent=2)
            print(f"✅ Backup saved to {backup_path}")
        
        # Save new config
        with open("config/config.json", 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Configuration saved successfully!")
        print("\n🚀 You're now ready to start entering competitions!")
        print("\nNext steps:")
        print("1. Run: python main.py --dry-run --max-entries 3")
        print("2. Review the output to ensure everything works")
        print("3. Run: python main.py --max-entries 5 (for real entries)")
        
    else:
        print("❌ Configuration not saved. Run this script again when ready.")

if __name__ == "__main__":
    main()
