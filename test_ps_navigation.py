#!/usr/bin/env python3
"""
Test script to analyze what happens after clicking ps/ links
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ps_link_navigation():
    """Test what happens when we navigate to ps/ links"""
    
    # Test URLs from recent decision trees
    test_ps_links = [
        "https://www.aussiecomps.com/ps/15600",  # PERGOLUX Pergola
        "https://www.aussiecomps.com/ps/15630",  # Cubot P90 Smartphones
        "https://www.aussiecomps.com/ps/15595",  # Generic link
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        for i, ps_url in enumerate(test_ps_links):
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing ps/ link {i+1}: {ps_url}")
            logger.info(f"{'='*60}")
            
            page = await context.new_page()
            
            try:
                await page.goto(ps_url, timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                
                # Get page info
                title = await page.title()
                url = page.url
                logger.info(f"Final URL: {url}")
                logger.info(f"Page title: {title}")
                
                # Check for forms
                forms = await page.query_selector_all('form')
                logger.info(f"Found {len(forms)} forms")
                
                # Check for input fields
                inputs = await page.query_selector_all('input, textarea, select')
                logger.info(f"Found {len(inputs)} input fields")
                
                # Check for buttons
                buttons = await page.query_selector_all('button, input[type="submit"]')
                logger.info(f"Found {len(buttons)} buttons")
                
                # Check for entry-related links
                entry_links = await page.query_selector_all('a')
                relevant_links = []
                for link in entry_links:
                    text = await link.text_content()
                    href = await link.get_attribute('href')
                    if text and any(keyword in text.lower() for keyword in ['enter', 'click', 'visit', 'go to', 'website', 'site']):
                        relevant_links.append((text.strip(), href))
                
                logger.info(f"Found {len(relevant_links)} potentially relevant entry links:")
                for text, href in relevant_links[:5]:  # Show first 5
                    logger.info(f"  '{text}' -> {href}")
                
                # Check for redirects or external links
                external_links = await page.query_selector_all('a[href^="http"]')
                logger.info(f"Found {len(external_links)} external links")
                
                # Take screenshot
                await page.screenshot(path=f'screenshots/ps_link_test_{i+1}.png')
                logger.info(f"Screenshot saved: screenshots/ps_link_test_{i+1}.png")
                
                # Check for success indicators
                page_text = await page.text_content('body')
                success_indicators = ['thank you', 'thanks', 'entered', 'success', 'confirmed', 'complete']
                found_indicators = [indicator for indicator in success_indicators if indicator in page_text.lower()]
                if found_indicators:
                    logger.info(f"Success indicators found: {found_indicators}")
                else:
                    logger.info("No success indicators found - likely needs additional navigation")
                
            except Exception as e:
                logger.error(f"Error testing {ps_url}: {e}")
            
            finally:
                await page.close()
            
            # Wait between tests
            await asyncio.sleep(2)
        
        input("Press Enter to continue...")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_ps_link_navigation())
