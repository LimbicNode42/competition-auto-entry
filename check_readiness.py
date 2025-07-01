#!/usr/bin/env python3
"""
System Readiness Check
Comprehensive verification that the competition entry system is ready for real use.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import load_config
from src.utils.logger import setup_logging
from src.core.scraper import CompetitionScraper

def check_configuration():
    """Check configuration completeness"""
    print("🔧 Configuration Check")
    print("-" * 30)
    
    issues = []
    warnings = []
    
    try:
        config = load_config()
        print("✅ Configuration file loaded successfully")
        
        # Check personal info
        personal_info = config.personal_info
        required_fields = {
            "first_name": "First Name",
            "last_name": "Last Name", 
            "email": "Email Address",
            "phone": "Phone Number",
            "address_line1": "Address Line 1",
            "city": "City",
            "state": "State/Province",
            "postal_code": "Postal Code",
            "country": "Country",
            "date_of_birth": "Date of Birth"
        }
        
        missing_fields = []
        placeholder_fields = []
        
        for field, description in required_fields.items():
            value = getattr(personal_info, field, "").strip()
            if not value:
                missing_fields.append(description)
            elif value in ["John", "Doe", "john.doe@example.com", "123 Main Street", "New York"]:
                placeholder_fields.append(description)
        
        if missing_fields:
            issues.append(f"Missing personal information: {', '.join(missing_fields)}")
        
        if placeholder_fields:
            warnings.append(f"Placeholder values detected: {', '.join(placeholder_fields)}")
        
        if not missing_fields and not placeholder_fields:
            print("✅ Personal information complete and looks real")
        
        # Check Google auth
        google_auth = config.google_auth
        if google_auth.email and "@" in google_auth.email:
            print("✅ Google authentication configured")
        else:
            issues.append("Google authentication not properly configured")
        
        # Check aggregator sites
        aggregator_file = Path("config/aggregator_sites.json")
        if aggregator_file.exists():
            with open(aggregator_file, 'r') as f:
                sites = json.load(f)
                enabled_sites = [site for site in sites if site.get("enabled", True)]
                print(f"✅ {len(enabled_sites)} aggregator sites configured")
        else:
            issues.append("Aggregator sites configuration missing")
        
        # Check filters
        filters = config.filters
        if filters.allowed_countries:
            print(f"✅ Country filters configured: {', '.join(filters.allowed_countries)}")
        else:
            warnings.append("No country filters set - may enter ineligible competitions")
        
        # Check max entries
        max_entries = config.max_daily_entries
        if max_entries > 0:
            print(f"✅ Daily entry limit: {max_entries}")
        else:
            warnings.append("No daily entry limit set")
        
    except Exception as e:
        issues.append(f"Configuration error: {e}")
    
    return issues, warnings

def check_dependencies():
    """Check required dependencies"""
    print("\n📦 Dependencies Check")
    print("-" * 30)
    
    issues = []
    
    try:
        # Check key imports
        import playwright
        print("✅ Playwright available")
    except ImportError:
        issues.append("Playwright not installed")
    
    try:
        import selenium
        print("✅ Selenium available")
    except ImportError:
        issues.append("Selenium not installed")
    
    try:
        import requests
        print("✅ Requests available")
    except ImportError:
        issues.append("Requests not installed")
    
    try:
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup available")
    except ImportError:
        issues.append("BeautifulSoup not installed")
    
    return issues

async def check_aggregator_connectivity():
    """Check connectivity to aggregator sites"""
    print("\n🌐 Aggregator Connectivity Check")
    print("-" * 30)
    
    issues = []
    
    try:
        config = load_config()
        
        # Test sites from previous successful tests
        test_sites = [
            ("Competition Cloud", "https://competitioncloud.com.au/"),
            ("AussieComps", "https://www.aussiecomps.com/"),
            ("Competitions.com.au", "https://competitions.com.au/")
        ]
        
        async with CompetitionScraper(config) as scraper:
            for site_name, site_url in test_sites:
                try:
                    competitions = await scraper.discover_competitions_from_page(
                        site_url, 
                        site_name,
                        use_pagination=False  # Just test connectivity
                    )
                    if competitions:
                        print(f"✅ {site_name}: Found {len(competitions)} competitions")
                    else:
                        issues.append(f"{site_name}: No competitions found (may indicate scraping issues)")
                        
                except Exception as e:
                    issues.append(f"{site_name}: Connection failed - {e}")
    
    except Exception as e:
        issues.append(f"Scraper initialization failed: {e}")
    
    return issues

def check_database():
    """Check database setup"""
    print("\n🗄️  Database Check")
    print("-" * 30)
    
    issues = []
    
    try:
        config = load_config()
        db_path = Path(config.database_path)
        
        # Create data directory if it doesn't exist
        db_path.parent.mkdir(exist_ok=True)
        
        # Test database connection
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.close()
        
        print(f"✅ Database accessible at: {db_path}")
        
    except Exception as e:
        issues.append(f"Database error: {e}")
    
    return issues

def generate_readiness_report(all_issues, all_warnings):
    """Generate final readiness report"""
    print("\n" + "="*60)
    print("🏆 SYSTEM READINESS REPORT")
    print("="*60)
    
    if not all_issues and not all_warnings:
        print("🎉 SYSTEM FULLY READY FOR COMPETITION ENTRY! 🎉")
        print("\nYou can now:")
        print("1. Run test entries: python main.py --dry-run --max-entries 3")
        print("2. Start real entries: python main.py --max-entries 5")
        print("3. Monitor entries in the database")
        return True
        
    elif not all_issues:
        print("⚠️  SYSTEM MOSTLY READY - Minor warnings")
        print("\nWarnings to address:")
        for warning in all_warnings:
            print(f"  • {warning}")
        print("\nYou can proceed but consider addressing warnings first:")
        print("1. Run test entries: python main.py --dry-run --max-entries 3")
        print("2. If satisfied, run: python main.py --max-entries 5")
        return True
        
    else:
        print("❌ SYSTEM NOT READY - Issues must be resolved")
        print("\nCritical issues:")
        for issue in all_issues:
            print(f"  • {issue}")
        
        if all_warnings:
            print("\nAdditional warnings:")
            for warning in all_warnings:
                print(f"  • {warning}")
        
        print("\nNext steps:")
        if any("personal information" in issue.lower() for issue in all_issues):
            print("1. Run: python setup_personal_config.py")
        print("2. Fix the issues listed above")
        print("3. Run this script again to verify")
        return False

async def main():
    """Main readiness check function"""
    print("🔍 Competition Auto-Entry System - Readiness Check")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_issues = []
    all_warnings = []
    
    # Run all checks
    issues, warnings = check_configuration()
    all_issues.extend(issues)
    all_warnings.extend(warnings)
    
    issues = check_dependencies()
    all_issues.extend(issues)
    
    issues = await check_aggregator_connectivity()
    all_issues.extend(issues)
    
    issues = check_database()
    all_issues.extend(issues)
    
    # Generate final report
    ready = generate_readiness_report(all_issues, all_warnings)
    
    return ready

if __name__ == "__main__":
    asyncio.run(main())
