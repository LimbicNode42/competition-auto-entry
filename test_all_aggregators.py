#!/usr/bin/env python3
"""
Test all aggregator sites to ensure they're working properly
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.scraper import CompetitionScraper
from src.utils.config import load_config

async def test_all_aggregators():
    """Test all aggregator sites"""
    print("Testing all aggregator sites...")
    
    try:
        # Initialize config and scraper
        config = load_config()
        
        # Test sites
        test_sites = [
            ("AussieComps", "https://www.aussiecomps.com/"),
            ("Competitions.com.au", "https://competitions.com.au/"),
            ("Competition Cloud", "https://competitioncloud.com.au/")
        ]
        
        # Use async context manager
        async with CompetitionScraper(config) as scraper:
            
            total_competitions = 0
            
            for site_name, site_url in test_sites:
                print(f"\n{'='*60}")
                print(f"Testing {site_name}: {site_url}")
                print(f"{'='*60}")
                
                try:
                    competitions = await scraper.discover_competitions_from_page(
                        site_url, 
                        site_name,
                        use_pagination=True
                    )
                    
                    print(f"✅ {site_name}: Found {len(competitions)} competitions")
                    
                    # Show first 3 competitions as examples
                    if competitions:
                        print(f"\nSample competitions from {site_name}:")
                        for i, comp in enumerate(competitions[:3], 1):
                            print(f"  {i}. {comp.title}")
                            print(f"     URL: {comp.url}")
                            if comp.deadline:
                                print(f"     Deadline: {comp.deadline}")
                            print()
                    
                    total_competitions += len(competitions)
                    
                except Exception as e:
                    print(f"❌ {site_name}: Error - {e}")
                    continue
            
            print(f"\n{'='*60}")
            print(f"SUMMARY")
            print(f"{'='*60}")
            print(f"Total competitions found across all sites: {total_competitions}")
            
            if total_competitions > 50:
                print("✅ Excellent! System is finding plenty of competitions.")
                print("💡 Ready to proceed with configuration and entry testing.")
            elif total_competitions > 20:
                print("✅ Good! System is working well.")
                print("💡 You can proceed with setup.")
            else:
                print("⚠️  Limited competitions found. May need further optimization.")
        
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all_aggregators())
