#!/usr/bin/env python3
"""
Debug script to analyze individual competition pages
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_competition_pages():
    """Debug individual competition pages to understand their structure"""
    
    # Test with a few different competition URLs
    test_urls = [
        "https://www.aussiecomps.com/index.php?id=24729&cat_id=0&p=&search=#onads",  # Red Poppy Coins
        "https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads",  # Cubot P90 Smartphones  
        "https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads",  # PERGOLUX Pergola
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        for i, url in enumerate(test_urls):
            logger.info(f"\n{'='*60}")
            logger.info(f"Analyzing competition {i+1}: {url}")
            logger.info(f"{'='*60}")
            
            page = await context.new_page()
            
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                
                # Get page title
                title = await page.title()
                logger.info(f"Page title: {title}")
                
                # Look for all ps/ links
                ps_links = await page.query_selector_all('a[href*="ps/"]')
                logger.info(f"Found {len(ps_links)} ps/ links")
                
                for j, link in enumerate(ps_links):
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    link_id = await link.get_attribute('id')
                    link_class = await link.get_attribute('class')
                    
                    logger.info(f"  Link {j+1}: {text[:50] if text else 'No text'} -> {href}")
                    if link_id:
                        logger.info(f"    ID: {link_id}")
                    if link_class:
                        logger.info(f"    Class: {link_class}")
                
                # Look for entry buttons or forms
                entry_buttons = await page.query_selector_all('input[type="submit"], button[type="submit"], button:has-text("Enter"), a:has-text("Enter")')
                logger.info(f"Found {len(entry_buttons)} potential entry buttons")
                
                for j, button in enumerate(entry_buttons):
                    text = await button.text_content()
                    button_type = await button.get_attribute('type')
                    href = await button.get_attribute('href')
                    logger.info(f"  Button {j+1}: {text[:50] if text else 'No text'} (type: {button_type}, href: {href})")
                
                # Look for forms
                forms = await page.query_selector_all('form')
                logger.info(f"Found {len(forms)} forms")
                
                for j, form in enumerate(forms):
                    action = await form.get_attribute('action')
                    method = await form.get_attribute('method')
                    inputs = await form.query_selector_all('input, textarea, select')
                    logger.info(f"  Form {j+1}: action={action}, method={method}, inputs={len(inputs)}")
                
                # Look for competition-specific entry links
                competition_links = await page.query_selector_all('a[href*="id="]')
                logger.info(f"Found {len(competition_links)} competition-specific links")
                
                unique_links = set()
                for link in competition_links:
                    href = await link.get_attribute('href')
                    if href and 'id=' in href:
                        unique_links.add(href)
                
                logger.info(f"Unique competition URLs: {len(unique_links)}")
                for link in list(unique_links)[:5]:  # Show first 5
                    logger.info(f"  {link}")
                
                # Take screenshot
                await page.screenshot(path=f'screenshots/competition_debug_{i+1}.png')
                logger.info(f"Screenshot saved: screenshots/competition_debug_{i+1}.png")
                
            except Exception as e:
                logger.error(f"Error analyzing {url}: {e}")
            
            finally:
                await page.close()
            
            # Wait a bit between pages
            await asyncio.sleep(2)
        
        input("Press Enter to continue...")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(debug_competition_pages())
