#!/usr/bin/env python3
"""
Quick test to analyze AussieComps competition pages and find actual entry links
"""

import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def analyze_competition_page():
    """Analyze a specific competition page to understand the structure"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Test with a specific competition
        test_url = "https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads"
        
        logger.info(f"Analyzing competition page: {test_url}")
        
        await page.goto(test_url)
        await page.wait_for_load_state('domcontentloaded')
        
        # Take screenshot
        await page.screenshot(path="screenshots/analysis.png")
        
        # Get page title
        title = await page.title()
        logger.info(f"Page title: {title}")
        
        # Find all links
        all_links = await page.query_selector_all('a')
        
        logger.info(f"Found {len(all_links)} links on the page")
        
        relevant_links = []
        
        for link in all_links:
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href and text:
                    text = text.strip()
                    if text and len(text) > 0:
                        relevant_links.append({
                            'href': href,
                            'text': text
                        })
            except:
                pass
        
        logger.info(f"Found {len(relevant_links)} relevant links:")
        
        for i, link in enumerate(relevant_links, 1):
            logger.info(f"  {i}. '{link['text']}' -> {link['href']}")
        
        # Look for specific patterns
        entry_patterns = ['enter', 'join', 'participate', 'click', 'visit', 'go to', 'competition']
        
        logger.info("\nLooking for entry-related links:")
        
        for link in relevant_links:
            for pattern in entry_patterns:
                if pattern.lower() in link['text'].lower():
                    logger.info(f"  MATCH: '{link['text']}' -> {link['href']}")
                    break
        
        # Look for external domains
        logger.info("\nLooking for external links:")
        
        for link in relevant_links:
            if link['href'].startswith('http') and 'aussiecomps.com' not in link['href']:
                logger.info(f"  EXTERNAL: '{link['text']}' -> {link['href']}")
        
        # Look for the actual competition content
        logger.info("\nLooking for competition content:")
        
        # Find the main content area
        content_selectors = [
            '.content',
            '.main-content',
            '.competition-content',
            '#content',
            'main',
            'article'
        ]
        
        for selector in content_selectors:
            try:
                content = await page.query_selector(selector)
                if content:
                    content_text = await content.text_content()
                    logger.info(f"Found content with selector '{selector}': {content_text[:200]}...")
                    break
            except:
                pass
        
        # Look for forms
        forms = await page.query_selector_all('form')
        logger.info(f"\nFound {len(forms)} forms on the page")
        
        for i, form in enumerate(forms, 1):
            try:
                form_html = await form.evaluate('el => el.outerHTML')
                logger.info(f"Form {i}: {form_html[:200]}...")
            except:
                pass
        
        # Look for inputs
        inputs = await page.query_selector_all('input, textarea, select')
        logger.info(f"\nFound {len(inputs)} input elements")
        
        for i, input_elem in enumerate(inputs, 1):
            try:
                tag_name = await input_elem.evaluate('el => el.tagName')
                input_type = await input_elem.get_attribute('type')
                name = await input_elem.get_attribute('name')
                placeholder = await input_elem.get_attribute('placeholder')
                
                logger.info(f"Input {i}: {tag_name} type={input_type} name={name} placeholder={placeholder}")
            except:
                pass
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_competition_page())
