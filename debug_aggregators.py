#!/usr/bin/env python3
"""
Debug script to test each aggregator individually and understand why rejection logging 
isn't working for all aggregators.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.core.modular_scraper import CompetitionScraper
from src.utils.config import load_config

async def test_aggregator(url: str, name: str):
    """Test a single aggregator."""
    print(f"\n{'='*60}")
    print(f"Testing {name}: {url}")
    print(f"{'='*60}")
    
    try:
        config = load_config()
        scraper = CompetitionScraper(config)
        
        print(f"Starting discovery for {name}...")
        competitions = await scraper.discover_competitions_from_page(url, name)
        
        print(f"Found {len(competitions)} competitions from {name}")
        
        if competitions:
            print("Sample competitions:")
            for i, comp in enumerate(competitions[:3]):  # Show first 3
                print(f"  {i+1}. {comp.title} - {comp.url}")
        else:
            print("No competitions found")
            
    except Exception as e:
        print(f"Error testing {name}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"Finished testing {name}")

async def main():
    """Test all aggregators individually."""
    aggregators = [
        ("https://competitioncloud.com.au/", "Competition Cloud"),
        ("https://www.aussiecomps.com/", "Aussie Comps"),
        ("https://www.competitions.com.au/", "Competitions.com.au")
    ]
    
    for url, name in aggregators:
        await test_aggregator(url, name)
        
    print(f"\n{'='*60}")
    print("All aggregator tests completed")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
