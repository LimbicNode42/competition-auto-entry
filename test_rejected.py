#!/usr/bin/env python3
"""
Test specific rejected competitions to understand the detection logic.
"""

import sys
from pathlib import Path
import asyncio
import aiohttp
from bs4 import BeautifulSoup

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.helpers import is_free_competition

async def test_rejected_competition(url: str):
    """Test a specific rejected competition."""
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
                is_free, detection_reason = is_free_competition(page_text.lower(), "")
                print(f"Is free competition: {is_free}")
                print(f"Detection reason: {detection_reason}")
                
                # Look for the specific phrases that triggered rejection
                page_lower = page_text.lower()
                
                # Check for "must purchase" context
                if "must purchase" in page_lower:
                    pos = page_lower.find("must purchase")
                    context = page_text[max(0, pos-100):pos+200]
                    print(f"\n'Must purchase' context:")
                    print(f"...{context}...")
                
                # Check for "purchase" in general
                if "purchase" in page_lower:
                    positions = []
                    start = 0
                    while True:
                        pos = page_lower.find("purchase", start)
                        if pos == -1:
                            break
                        positions.append(pos)
                        start = pos + 1
                    
                    print(f"\nFound 'purchase' {len(positions)} times:")
                    for i, pos in enumerate(positions[:3]):  # Show first 3
                        context = page_text[max(0, pos-50):pos+100]
                        print(f"  {i+1}. ...{context}...")
                
                # Check for free indicators
                free_phrases = [
                    'no purchase necessary', 'no purchase required', 'free to enter',
                    'free entry', 'no entry fee', 'completely free'
                ]
                
                print(f"\nFree indicators:")
                for phrase in free_phrases:
                    if phrase in page_lower:
                        pos = page_lower.find(phrase)
                        context = page_text[max(0, pos-50):pos+100]
                        print(f"  ✓ '{phrase}': ...{context}...")
                
        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Test specific rejected competitions."""
    
    # Test competitions from the rejection log
    test_urls = [
        "https://www.competitions.com.au/win-ben-jerrys-freezers/64533/",  # Rejected for "must purchase"
        "https://www.competitions.com.au/win-2-nights-accommodation-brisbane/64527/",  # Rejected for "purchase" in entry context
    ]
    
    for url in test_urls:
        await test_rejected_competition(url)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
