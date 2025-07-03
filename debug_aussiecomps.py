#!/usr/bin/env python3
"""
Debug script to understand AussieComps site structure
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_aussiecomps():
    """Debug AussieComps site structure"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        logger.info("Navigating to AussieComps...")
        await page.goto('https://www.aussiecomps.com/', timeout=30000)
        await page.wait_for_load_state('domcontentloaded')
        
        # Get page title
        title = await page.title()
        logger.info(f"Page title: {title}")
        
        # Check for various link patterns
        selectors_to_check = [
            'a[href*="/ps/"]',
            'a[href*="ps/"]',
            'a[href*="/index.php"]',
            'a[href*="id="]',
            'a:has-text("Win")',
            'a:has-text("win")',
            'a:has-text("Enter")',
            'a:has-text("Competition")',
            'a',  # All links
        ]
        
        for selector in selectors_to_check:
            try:
                links = await page.query_selector_all(selector)
                logger.info(f"Found {len(links)} links with selector: {selector}")
                
                # Show first 5 links
                for i, link in enumerate(links[:5]):
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    if href and text:
                        logger.info(f"  Link {i+1}: {text.strip()[:50]} -> {href}")
                        
            except Exception as e:
                logger.error(f"Error with selector {selector}: {e}")
        
        # Take a screenshot
        await page.screenshot(path='screenshots/aussiecomps_debug.png')
        logger.info("Screenshot saved: screenshots/aussiecomps_debug.png")
        
        # Check for forms
        forms = await page.query_selector_all('form')
        logger.info(f"Found {len(forms)} forms on page")
        
        # Wait for user input
        input("Press Enter to continue...")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(debug_aussiecomps())
