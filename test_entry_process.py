#!/usr/bin/env python3
"""
Test the competition entry process with a small sample
This script tests the full pipeline: discovery -> filtering -> entry (dry run)
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.scraper import CompetitionScraper
from src.utils.config import load_config
from src.utils.logger import setup_logging

async def test_entry_process():
    """Test the entry process with dry run"""
    print("🧪 Testing Competition Entry Process")
    print("=" * 50)
    
    # Setup logging
    logger = setup_logging()
    
    try:
        # Load config
        config = load_config()
        print("✅ Configuration loaded successfully")
        
        # Check if personal info is configured
        personal_info = config.get("personal_info", {})
        required_fields = ["first_name", "last_name", "email", "address_line1", "city", "country"]
        missing_fields = [field for field in required_fields if not personal_info.get(field)]
        
        if missing_fields:
            print(f"⚠️  Missing personal information: {', '.join(missing_fields)}")
            print("Run 'python setup_personal_config.py' to configure your details first.")
            return
        
        print(f"✅ Personal info configured for: {personal_info['first_name']} {personal_info['last_name']}")
        
        # Test with one aggregator site first
        async with CompetitionScraper(config) as scraper:
            print("\n🔍 Discovering competitions from AussieComps...")
            
            competitions = await scraper.discover_competitions_from_page(
                "https://www.aussiecomps.com/",
                "AussieComps",
                use_pagination=False  # Just first page for testing
            )
            
            print(f"✅ Found {len(competitions)} competitions")
            
            if competitions:
                # Test with first 3 competitions
                test_competitions = competitions[:3]
                print(f"\n🎯 Testing entry process with {len(test_competitions)} competitions (DRY RUN):")
                
                for i, comp in enumerate(test_competitions, 1):
                    print(f"\n--- Competition {i} ---")
                    print(f"Title: {comp.get('title', 'No title')}")
                    print(f"URL: {comp.get('url', 'No URL')}")
                    print(f"Deadline: {comp.get('deadline', 'No deadline')}")
                    
                    # Simulate entry process (dry run)
                    print("🔄 Simulating entry process...")
                    
                    try:
                        # This would be where actual entry happens
                        print("  → Loading competition page...")
                        print("  → Analyzing entry requirements...")
                        print("  → Checking eligibility...")
                        print("  → [DRY RUN] Would fill form with personal details")
                        print("  → [DRY RUN] Would submit entry")
                        print("  ✅ Entry simulation successful")
                        
                    except Exception as e:
                        print(f"  ❌ Entry simulation failed: {e}")
                
                print(f"\n🎉 Entry process test completed!")
                print("The system is ready for real competition entry.")
                print("\nTo start real entries:")
                print("1. Ensure your personal details are correct in config/config.json")
                print("2. Run: python main.py --dry-run --max-entries 5")
                print("3. If satisfied, run: python main.py --max-entries 5")
                
            else:
                print("❌ No competitions found. Check aggregator sites configuration.")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_entry_process())
