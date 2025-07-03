#!/usr/bin/env python3
"""
Detailed analysis of AussieComps competition structure
"""

import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def deep_analyze_competition():
    """Deep analysis of competition structure"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Test with a specific competition
        test_url = "https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads"
        
        logger.info(f"Deep analyzing competition: {test_url}")
        
        await page.goto(test_url)
        await page.wait_for_load_state('domcontentloaded')
        
        # Take screenshot
        await page.screenshot(path="screenshots/deep_analysis.png")
        
        # Get all text content
        page_text = await page.text_content('body')
        logger.info(f"Page text content (first 500 chars): {page_text[:500]}")
        
        # Look for specific competition information
        competition_info = []
        
        # Look for text patterns that indicate actual competition entry
        patterns = [
            'enter',
            'competition',
            'giveaway',
            'win',
            'prize',
            'click here',
            'visit',
            'enter now',
            'join',
            'participate'
        ]
        
        for pattern in patterns:
            if pattern.lower() in page_text.lower():
                logger.info(f"Found pattern '{pattern}' in page text")
        
        # Look for the actual competition data
        # Check if there's a specific competition entry link
        potential_entry_link = None
        
        # Look for links that might contain the actual competition URL
        try:
            # Check the specific link we found
            entry_link = await page.query_selector('a[href*="ps/"]')
            if entry_link:
                href = await entry_link.get_attribute('href')
                text = await entry_link.text_content()
                logger.info(f"Found potential entry link: '{text}' -> {href}")
                
                # Make it absolute if needed
                if not href.startswith('http'):
                    href = f"https://www.aussiecomps.com/{href.lstrip('/')}"
                
                potential_entry_link = href
                
        except Exception as e:
            logger.error(f"Error finding entry link: {e}")
        
        # If we found a potential entry link, follow it
        if potential_entry_link:
            logger.info(f"Following potential entry link: {potential_entry_link}")
            
            entry_page = await context.new_page()
            
            try:
                await entry_page.goto(potential_entry_link)
                await entry_page.wait_for_load_state('domcontentloaded')
                
                # Take screenshot of entry page
                await entry_page.screenshot(path="screenshots/entry_page_analysis.png")
                
                # Get page title
                entry_title = await entry_page.title()
                logger.info(f"Entry page title: {entry_title}")
                
                # Check for forms
                forms = await entry_page.query_selector_all('form')
                logger.info(f"Found {len(forms)} forms on entry page")
                
                # Check for inputs
                inputs = await entry_page.query_selector_all('input, textarea, select')
                logger.info(f"Found {len(inputs)} input elements on entry page")
                
                # Look for external links (competition platforms)
                external_links = []
                all_links = await entry_page.query_selector_all('a')
                
                for link in all_links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        
                        if href and text and href.startswith('http'):
                            # Check if it's an external competition platform
                            if any(platform in href.lower() for platform in ['gleam.io', 'woobox', 'rafflecopter', 'kingsumo', 'contest.com']):
                                external_links.append({
                                    'href': href,
                                    'text': text.strip(),
                                    'platform': 'competition_platform'
                                })
                            elif 'aussiecomps.com' not in href:
                                external_links.append({
                                    'href': href,
                                    'text': text.strip(),
                                    'platform': 'external'
                                })
                    except:
                        pass
                
                if external_links:
                    logger.info(f"Found {len(external_links)} external links on entry page:")
                    for link in external_links:
                        logger.info(f"  {link['platform']}: '{link['text']}' -> {link['href']}")
                
                # Get page content
                entry_content = await entry_page.text_content('body')
                logger.info(f"Entry page content (first 500 chars): {entry_content[:500]}")
                
                await entry_page.close()
                
            except Exception as e:
                logger.error(f"Error analyzing entry page: {e}")
                await entry_page.close()
        
        # Also check if there are any iframe elements (competitions might be embedded)
        iframes = await page.query_selector_all('iframe')
        logger.info(f"Found {len(iframes)} iframe elements")
        
        for i, iframe in enumerate(iframes, 1):
            try:
                src = await iframe.get_attribute('src')
                if src:
                    logger.info(f"Iframe {i}: {src}")
            except:
                pass
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(deep_analyze_competition())
