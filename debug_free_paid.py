#!/usr/bin/env python3
"""
Debug script to test free/paid detection logic on actual competition text.
"""

import sys
from pathlib import Path
import asyncio
import aiohttp
from bs4 import BeautifulSoup

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.helpers import is_free_competition

async def test_competition_url(url: str):
    """Test the free/paid detection on a specific competition URL."""
    print(f"\n=== Testing {url} ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"HTTP {response.status}")
                    return
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                title = soup.title.get_text() if soup.title else "No title"
                print(f"Title: {title}")
                
                # Get page text for analysis
                page_text = soup.get_text()
                print(f"Page length: {len(page_text)} characters")
                
                # Test the detection function
                is_free = is_free_competition(page_text.lower(), "")
                print(f"Is free competition: {is_free}")
                
                # Check for specific indicators
                page_lower = page_text.lower()
                
                paid_indicators = [
                    'entry fee', 'purchase required', 'subscription required',
                    'lottery', 'lotto', 'powerball', 'mega millions',
                    'syndicate', 'ticket required', 'buy ticket'
                ]
                
                free_indicators = [
                    'no purchase necessary', 'no purchase required', 'free to enter',
                    'free entry', 'no entry fee', 'completely free'
                ]
                
                print("\nPaid indicators found:")
                for indicator in paid_indicators:
                    if indicator in page_lower:
                        print(f"  ✓ '{indicator}'")
                        # Show context
                        pos = page_lower.find(indicator)
                        context = page_text[max(0, pos-50):pos+50]
                        print(f"    Context: ...{context}...")
                
                print("\nFree indicators found:")
                for indicator in free_indicators:
                    if indicator in page_lower:
                        print(f"  ✓ '{indicator}'")
                        pos = page_lower.find(indicator)
                        context = page_text[max(0, pos-50):pos+50]
                        print(f"    Context: ...{context}...")
                
                # Check for currency mentions
                currencies = ['$', '£', '€', 'aud', 'usd']
                print("\nCurrency mentions:")
                for currency in currencies:
                    count = page_lower.count(currency)
                    if count > 0:
                        print(f"  '{currency}': {count} occurrences")
                
        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Test specific competition URLs."""
    
    # Test some of the competitions that were marked as requiring payment
    test_urls = [
        "https://www.aussiecomps.com/ps/15455",  # This one was accepted
        "https://www.competitions.com.au/exit/win-5k-cash/60517/",  # This one was accepted
    ]
    
    # Get some of the rejected ones from the log output
    rejected_examples = [
        "https://www.competitions.com.au/exit/win-1000-a-day-for-20-years/50779/",
        "https://www.competitions.com.au/exit/win-a-share-of-usa-jackpot/50780/",
    ]
    
    print("=== TESTING ACCEPTED COMPETITIONS ===")
    for url in test_urls:
        await test_competition_url(url)
        await asyncio.sleep(2)
    
    print("\n\n=== TESTING REJECTED COMPETITIONS ===")
    for url in rejected_examples:
        await test_competition_url(url)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
