#!/usr/bin/env python3
"""
Test multiple competitions that were incorrectly rejected.
"""

import requests
from bs4 import BeautifulSoup
from src.utils.helpers import is_free_competition

def test_multiple_competitions():
    """Test multiple competitions that were incorrectly rejected."""
    
    test_urls = [
        "https://www.competitions.com.au/win-collectors-coin-prizes/64531/",
        "https://www.competitions.com.au/win-2-tickets-hunter-valley-wine-beer-festival/64528/",
        "https://www.competitions.com.au/win-wild-daisy-collective-surprise-pack/64529/"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Testing: {url}")
        print('='*80)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch page. Status: {response.status_code}")
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            # Extract title
            title_elem = soup.find('title')
            title = title_elem.get_text().strip() if title_elem else "Unknown"
            
            print(f"Title: {title}")
            
            # Test the improved detection
            is_free, reason = is_free_competition(page_text, "")
            
            print(f"Is free competition: {is_free}")
            print(f"Reason: {reason}")
            
            # Count category tags
            category_tags = [
                "interactive", "recurring competition", "requires a codeword", 
                "requires a purchase", "requires registration", "simple entry", 
                "random winner", "survey compet"
            ]
            
            tag_count = sum(1 for tag in category_tags if tag in page_text.lower())
            print(f"Category tags found: {tag_count}/8")
            
        except Exception as e:
            print(f"Error testing competition: {e}")

if __name__ == "__main__":
    test_multiple_competitions()
