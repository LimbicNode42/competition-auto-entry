#!/usr/bin/env python3
"""
Test the actual competition entry flow with iframe handling
"""

import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_iframe_competition_entry():
    """Test competition entry with iframe support"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Start with the competition listing page
        competition_url = "https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads"
        
        logger.info(f"Starting with competition: {competition_url}")
        
        await page.goto(competition_url)
        await page.wait_for_load_state('domcontentloaded')
        
        # Take screenshot
        await page.screenshot(path="screenshots/step1_competition_listing.png")
        
        # Find the entry link (ps/ pattern)
        entry_link = await page.query_selector('a[href*="ps/"]')
        if entry_link:
            href = await entry_link.get_attribute('href')
            text = await entry_link.text_content()
            logger.info(f"Found entry link: '{text}' -> {href}")
            
            # Make it absolute
            if not href.startswith('http'):
                href = f"https://www.aussiecomps.com/{href.lstrip('/')}"
            
            # Navigate to the entry page
            logger.info(f"Navigating to entry page: {href}")
            await page.goto(href)
            await page.wait_for_load_state('domcontentloaded')
            
            # Wait for any dynamic content
            await asyncio.sleep(3)
            
            # Take screenshot of entry page
            await page.screenshot(path="screenshots/step2_entry_page.png")
            
            # Check for iframes
            iframes = await page.query_selector_all('iframe')
            logger.info(f"Found {len(iframes)} iframes on entry page")
            
            # Look for forms on the main page first
            forms = await page.query_selector_all('form')
            inputs = await page.query_selector_all('input, textarea, select')
            
            logger.info(f"Main page: {len(forms)} forms, {len(inputs)} inputs")
            
            # Analyze the inputs on the main page
            for i, input_elem in enumerate(inputs, 1):
                try:
                    tag_name = await input_elem.evaluate('el => el.tagName')
                    input_type = await input_elem.get_attribute('type')
                    name = await input_elem.get_attribute('name')
                    placeholder = await input_elem.get_attribute('placeholder')
                    visible = await input_elem.is_visible()
                    
                    logger.info(f"Main page input {i}: {tag_name} type={input_type} name={name} placeholder={placeholder} visible={visible}")
                except Exception as e:
                    logger.error(f"Error analyzing input {i}: {e}")
            
            # If we found forms on the main page, try to fill them
            if forms:
                logger.info("Attempting to fill form on main page...")
                
                # Simple test data
                test_data = {
                    'email': 'john.doe@example.com',
                    'name': 'John Doe',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'phone': '0400000000'
                }
                
                filled_count = 0
                
                for input_elem in inputs:
                    try:
                        if not await input_elem.is_visible():
                            continue
                        
                        input_type = await input_elem.get_attribute('type')
                        name = await input_elem.get_attribute('name')
                        placeholder = await input_elem.get_attribute('placeholder')
                        
                        # Determine what to fill
                        value = None
                        
                        if input_type == 'email' or (name and 'email' in name.lower()) or (placeholder and 'email' in placeholder.lower()):
                            value = test_data['email']
                        elif input_type == 'text':
                            if name and 'name' in name.lower():
                                value = test_data['name']
                            elif placeholder and 'name' in placeholder.lower():
                                value = test_data['name']
                        elif input_type == 'checkbox':
                            # Check checkboxes (assuming they're terms/conditions)
                            if not await input_elem.is_checked():
                                await input_elem.click()
                                logger.info(f"Checked checkbox")
                                filled_count += 1
                            continue
                        
                        if value:
                            await input_elem.fill(value)
                            logger.info(f"Filled {input_type} field with: {value}")
                            filled_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error filling input: {e}")
                
                logger.info(f"Filled {filled_count} fields on main page")
                
                # Take screenshot after filling
                await page.screenshot(path="screenshots/step3_form_filled.png")
                
                # Look for submit button
                submit_selectors = [
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'button:has-text("Submit")',
                    'button:has-text("Sign")',
                    'button:has-text("Enter")',
                    'button:has-text("Join")'
                ]
                
                for selector in submit_selectors:
                    try:
                        submit_btn = await page.query_selector(selector)
                        if submit_btn and await submit_btn.is_visible():
                            submit_text = await submit_btn.text_content()
                            logger.info(f"Found submit button: '{submit_text}' ({selector})")
                            
                            # Don't actually submit, just log
                            logger.info("Form is ready for submission (not submitting to avoid spam)")
                            break
                    except:
                        pass
            
            # Also check iframes for additional forms
            for i, iframe in enumerate(iframes, 1):
                try:
                    src = await iframe.get_attribute('src')
                    if src and not src.startswith('about:'):
                        logger.info(f"Iframe {i} src: {src}")
                        
                        # Skip social media iframes
                        if any(skip in src.lower() for skip in ['facebook', 'twitter', 'addtoany']):
                            continue
                        
                        # Try to access iframe content
                        try:
                            iframe_content = await iframe.content_frame()
                            if iframe_content:
                                iframe_forms = await iframe_content.query_selector_all('form')
                                iframe_inputs = await iframe_content.query_selector_all('input, textarea, select')
                                
                                logger.info(f"Iframe {i} content: {len(iframe_forms)} forms, {len(iframe_inputs)} inputs")
                                
                                # Take screenshot of iframe
                                await iframe_content.screenshot(path=f"screenshots/iframe_{i}_content.png")
                                
                        except Exception as e:
                            logger.warning(f"Could not access iframe {i} content: {e}")
                            
                except Exception as e:
                    logger.error(f"Error analyzing iframe {i}: {e}")
        
        else:
            logger.info("No entry link found")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_iframe_competition_entry())
