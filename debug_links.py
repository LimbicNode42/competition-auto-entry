#!/usr/bin/env python3
"""
Debug script to test link discovery from aggregator sites.
"""

import asyncio
import sys
from pathlib import Path
import aiohttp
from bs4 import BeautifulSoup

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_logging
from src.utils.helpers import normalize_url, is_valid_url

logger = setup_logging()

async def debug_aggregator_site(url: str):
    """Debug what links are found on an aggregator site."""
    print(f"\n=== Debugging {url} ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"HTTP {response.status} - {url}")
                    return
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                print(f"Page title: {soup.title.get_text() if soup.title else 'No title'}")
                print(f"Page length: {len(content)} characters")
                
                # Test different selectors
                selectors_to_test = [
                    'a',  # All links
                    'a[href*="competition"]',
                    'a[href*="contest"]', 
                    'a[href*="comp"]',
                    'a[href*="win"]',
                    '.competition-link a',
                    '.contest-link a',
                    '.comp-item a',
                    '.competition-card a'
                ]
                
                for selector in selectors_to_test:
                    links = soup.select(selector)
                    print(f"{selector}: {len(links)} links found")
                    
                    if selector == 'a' and len(links) > 20:
                        # For all links, show just a sample
                        print("  Sample links:")
                        for i, link in enumerate(links[:10]):
                            href = link.get('href', '')
                            text = link.get_text().strip()[:50]
                            print(f"    {i+1}. {href} - '{text}'")
                    elif len(links) > 0 and len(links) <= 20:
                        print("  Found links:")
                        for i, link in enumerate(links):
                            href = link.get('href', '')
                            text = link.get_text().strip()[:50]
                            print(f"    {i+1}. {href} - '{text}'")
                
                # Look for competition-related words in the page
                page_text = soup.get_text().lower()
                comp_words = ['competition', 'contest', 'giveaway', 'sweepstakes', 'prize', 'win']
                print(f"\nContent analysis:")
                for word in comp_words:
                    count = page_text.count(word)
                    print(f"  '{word}': {count} occurrences")
                
        except Exception as e:
            print(f"Error fetching {url}: {e}")

async def main():
    """Main debug function."""
    
    # Test aggregator sites
    test_urls = [
        "https://competitions.com.au/",
        "https://competitioncloud.com.au/",
        "https://www.aussiecomps.com/"
    ]
    
    for url in test_urls:
        await debug_aggregator_site(url)
        await asyncio.sleep(2)  # Be respectful

if __name__ == "__main__":
    asyncio.run(main())
