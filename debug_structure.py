#!/usr/bin/env python3
"""
Debug script to manually browse competition sites and understand their structure.
"""

import asyncio
import sys
from pathlib import Path
import aiohttp
from bs4 import BeautifulSoup

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_logging

logger = setup_logging()

async def inspect_site_structure(url: str):
    """Inspect the actual structure of a competition site."""
    print(f"\n=== Detailed Analysis of {url} ===")
    
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
                
                # Look for patterns that might contain competition URLs
                patterns_to_check = [
                    # Direct URL patterns
                    'a[href*="/entry/"]',
                    'a[href*="/enter/"]', 
                    'a[href*="/competition/"]',
                    'a[href*="/comp/"]',
                    'a[href*="/c/"]',
                    'a[href*="/prize/"]',
                    'a[href*="/win/"]',
                    'a[href*="/giveaway/"]',
                    # Class-based selectors
                    'a.comp-link',
                    'a.competition-link',
                    'a.entry-link',
                    'a.prize-link',
                    # Container-based selectors
                    '.competition a',
                    '.comp-listing a',
                    '.prize-item a',
                    '.contest-item a',
                    # Generic but targeted
                    'a[title*="Enter"]',
                    'a[title*="Win"]',
                    'a[title*="Competition"]'
                ]
                
                for pattern in patterns_to_check:
                    links = soup.select(pattern)
                    if links:
                        print(f"\n{pattern}: {len(links)} matches")
                        for i, link in enumerate(links[:5]):  # Show first 5
                            href = link.get('href', '')
                            title = link.get('title', '')
                            text = link.get_text().strip()[:60]
                            print(f"  {i+1}. {href}")
                            if title:
                                print(f"      Title: {title}")
                            if text:
                                print(f"      Text: {text}")
                
                # Look for JavaScript-loaded content indicators
                scripts = soup.find_all('script')
                js_indicators = []
                for script in scripts:
                    if script.string:
                        script_text = script.string.lower()
                        if any(word in script_text for word in ['competition', 'contest', 'ajax', 'fetch', 'api']):
                            js_indicators.append("Found JS with competition-related keywords")
                            break
                
                if js_indicators:
                    print(f"\nJavaScript Analysis:")
                    for indicator in js_indicators:
                        print(f"  - {indicator}")
                
                # Look for data attributes that might contain URLs
                elements_with_data = soup.find_all(attrs={"data-url": True})
                elements_with_data.extend(soup.find_all(attrs={"data-link": True}))
                elements_with_data.extend(soup.find_all(attrs={"data-href": True}))
                
                if elements_with_data:
                    print(f"\nElements with data URLs: {len(elements_with_data)}")
                    for i, elem in enumerate(elements_with_data[:5]):
                        for attr in ['data-url', 'data-link', 'data-href']:
                            if elem.get(attr):
                                print(f"  {i+1}. {attr}: {elem[attr]}")
                
        except Exception as e:
            print(f"Error inspecting {url}: {e}")

async def main():
    """Main inspection function."""
    
    # Test specific sites 
    test_urls = [
        "https://competitions.com.au/",
        "https://www.aussiecomps.com/",
    ]
    
    for url in test_urls:
        await inspect_site_structure(url)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
