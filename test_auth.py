#!/usr/bin/env python3
"""
Test script to manually check authentication and page content.
"""

import sys
from pathlib import Path
import time

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config import load_config
from src.core.scraper import CompetitionScraper
import asyncio

async def test_auth_sites():
    """Test authentication for the competition sites."""
    
    config = load_config('config/config.json')
    
    async with CompetitionScraper(config) as scraper:
        # Test CompetitionCloud (should work now)
        print("=== Testing CompetitionCloud.com.au ===")
        url = "https://competitioncloud.com.au/"
        
        auth_success = await scraper._ensure_authenticated(url)
        print(f"Authentication success: {auth_success}")
        
        if auth_success and scraper.driver:
            print("Page title:", scraper.driver.title)
            print("Current URL:", scraper.driver.current_url)
            
            # Look for competition indicators
            page_source = scraper.driver.page_source
            competition_words = ['competition', 'contest', 'giveaway', 'prize', 'win']
            
            print("\nContent analysis:")
            for word in competition_words:
                count = page_source.lower().count(word)
                print(f"  '{word}': {count} occurrences")
            
            # Look for links that might be competitions
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try different selectors
            selectors_to_try = [
                'a[href*="comp"]',
                'a[href*="competition"]', 
                'a[href*="entry"]',
                'a[href*="enter"]',
                '.competition',
                '.contest',
                '.entry'
            ]
            
            print("\nLink analysis:")
            for selector in selectors_to_try:
                links = soup.select(selector)
                print(f"  {selector}: {len(links)} elements")
                if links:
                    for i, link in enumerate(links[:3]):  # Show first 3
                        href = link.get('href', '')
                        text = link.get_text().strip()[:50]
                        print(f"    {i+1}. {href} - '{text}'")
            
            # Wait a bit for any dynamic content to load
            print("\nWaiting 10 seconds for dynamic content...")
            time.sleep(10)
            
            # Check again after wait
            updated_source = scraper.driver.page_source
            if len(updated_source) != len(page_source):
                print(f"Page content changed: {len(page_source)} -> {len(updated_source)} characters")
            else:
                print("No dynamic content detected")
        
        print("\n" + "="*50)
        
        # Test Competitions.com.au
        print("\n=== Testing Competitions.com.au ===")
        url2 = "https://www.competitions.com.au/"
        
        auth_success2 = await scraper._ensure_authenticated(url2)
        print(f"Authentication success: {auth_success2}")
        
        if scraper.driver:
            print("Page title:", scraper.driver.title)
            print("Current URL:", scraper.driver.current_url)
            
            # Check if we can see any login-related elements
            page_source = scraper.driver.page_source
            login_indicators = ['login', 'sign in', 'google', 'oauth', 'register']
            
            print("\nLogin indicators:")
            for indicator in login_indicators:
                count = page_source.lower().count(indicator)
                print(f"  '{indicator}': {count} occurrences")

if __name__ == "__main__":
    asyncio.run(test_auth_sites())
