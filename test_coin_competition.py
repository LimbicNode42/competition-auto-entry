#!/usr/bin/env python3
"""
Test the specific coin competition that was incorrectly rejected.
"""

import requests
from bs4 import BeautifulSoup
from src.utils.helpers import is_free_competition

def test_coin_competition():
    """Test the specific competition that was incorrectly rejected."""
    
    url = "https://www.competitions.com.au/win-collectors-coin-prizes/64531/"
    
    try:
        print(f"Testing competition: {url}")
        
        # Fetch the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch page. Status: {response.status_code}")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()
        
        print(f"Page text length: {len(page_text)}")
        print(f"First 500 chars:\n{page_text[:500]}")
        print("\n" + "="*80 + "\n")
        
        # Test the improved detection
        is_free, reason = is_free_competition(page_text, "")
        
        print(f"Is free competition: {is_free}")
        print(f"Reason: {reason}")
        
        # Show the category tags that are being detected
        category_tags = [
            "interactive", "recurring competition", "requires a codeword", 
            "requires a purchase", "requires registration", "simple entry", 
            "random winner", "survey compet"
        ]
        
        print(f"\nCategory tags detected:")
        for tag in category_tags:
            if tag in page_text.lower():
                print(f"  ✓ {tag}")
            else:
                print(f"  ✗ {tag}")
        
    except Exception as e:
        print(f"Error testing competition: {e}")

if __name__ == "__main__":
    test_coin_competition()
