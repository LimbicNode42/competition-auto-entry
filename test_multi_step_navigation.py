#!/usr/bin/env python3
"""
Test script to verify multi-step navigation through ps/ links
and intermediate pages before reaching the actual competition form.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_competition_system import AdaptiveCompetitionEntry


async def test_multi_step_navigation():
    """Test the system's ability to handle multi-step navigation"""
    system = AdaptiveCompetitionEntry()
    
    # Test with a specific competition that requires multi-step navigation
    test_url = "https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads"
    
    print(f"Testing multi-step navigation for: {test_url}")
    print("-" * 80)
    
    try:
        # Run the system with detailed logging
        results = await system.process_competition_adaptively(test_url, "Test Competition", max_depth=10)
        
        print("\n" + "="*80)
        print("RESULTS:")
        print(f"Success: {results}")
        print("="*80)
                
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    await system.close()


async def test_specific_ps_link():
    """Test direct navigation to a ps/ link to see what happens"""
    system = AdaptiveCompetitionEntry()
    
    # Test a specific ps/ link directly
    ps_url = "https://www.aussiecomps.com/ps/15600"
    
    print(f"Testing direct ps/ link: {ps_url}")
    print("-" * 80)
    
    try:
        # Create a browser context
        await system.initialize()
        
        page = await system.browser.new_page()
        await page.goto(ps_url)
        
        print(f"Navigated to: {page.url}")
        
        # Take a screenshot
        screenshot_path = f"screenshots/ps_link_test_{int(asyncio.get_event_loop().time())}.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Check if this is a redirect page or entry page
        forms = await page.query_selector_all('form')
        if forms:
            print(f"Found {len(forms)} forms on this page")
            for i, form in enumerate(forms):
                action = await form.get_attribute('action')
                method = await form.get_attribute('method')
                print(f"  Form {i+1}: action={action}, method={method}")
        else:
            print("No forms found on this page")
            
        # Check for redirect indicators
        redirects = await page.query_selector_all('a')
        print(f"Found {len(redirects)} links on this page")
        
        # Look for external competition platform links
        external_links = []
        for link in redirects:
            href = await link.get_attribute('href')
            if href and any(platform in href for platform in ['gleam.io', 'woobox.com', 'rafflecopter.com']):
                external_links.append(href)
                
        if external_links:
            print(f"Found {len(external_links)} external competition platform links:")
            for link in external_links:
                print(f"  - {link}")
        
        await page.close()
        
    except Exception as e:
        print(f"Error during ps/ link test: {e}")
        import traceback
        traceback.print_exc()
    
    await system.close()


async def main():
    """Run all tests"""
    print("Multi-Step Navigation Test Suite")
    print("=" * 80)
    
    # Test 1: Multi-step navigation
    print("\n1. Testing multi-step navigation...")
    await test_multi_step_navigation()
    
    # Test 2: Direct ps/ link test
    print("\n2. Testing direct ps/ link...")
    await test_specific_ps_link()


if __name__ == "__main__":
    asyncio.run(main())
