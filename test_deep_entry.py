#!/usr/bin/env python3
"""
Enhanced CV/MCP Test - Navigate to actual competition entry forms
This test goes deeper into the competition flow to find actual entry forms
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import our final competition entry system
from competition_auto_entry_final import CompetitionAutoEntry, logger

# Configure logging
logging.getLogger().setLevel(logging.INFO)

async def test_deep_competition_entry():
    """Test going deeper into competition entry flow"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize the auto-entry system (visible browser for debugging)
    headless = False
    auto_entry = CompetitionAutoEntry(config_path="config/config.json", headless=headless)
    
    try:
        # Initialize the browser
        await auto_entry.initialize()
        
        # Test with a known competition site that has forms
        test_urls = [
            # Direct competition entry pages that likely have forms
            "https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads",  # Cubot smartphone
            "https://gleam.io/kgvZb/xbox-series-x-giveaway-july-2025",  # Known working Gleam competition
        ]
        
        for url in test_urls:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing deep entry for: {url}")
            logger.info(f"{'='*60}")
            
            page = await auto_entry.context.new_page()
            
            try:
                # Navigate to the competition
                logger.info(f"Navigating to: {url}")
                await page.goto(url, timeout=60000)
                
                # Wait for dynamic content to load
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                # Take initial screenshot
                initial_screenshot = f"screenshots/initial_{int(time.time())}.png"
                await page.screenshot(path=initial_screenshot)
                logger.info(f"Initial screenshot: {initial_screenshot}")
                
                # Get page title
                title = await page.title()
                logger.info(f"Page title: {title}")
                
                # Look for entry buttons, "Enter" links, or form submission buttons
                entry_button_selectors = [
                    'a:has-text("Enter")',
                    'a:has-text("Click here")',
                    'a:has-text("Visit site")',
                    'a:has-text("Go to")',
                    'button:has-text("Enter")',
                    '.enter-button',
                    '.visit-site',
                    'a[href*="enter"]',
                    'a[href*="comp"]',
                    'a[target="_blank"]',  # Many competition sites open in new tabs
                ]
                
                entry_url = None
                for selector in entry_button_selectors:
                    try:
                        entry_link = await page.query_selector(selector)
                        if entry_link:
                            href = await entry_link.get_attribute('href')
                            text = await entry_link.text_content()
                            if href and text:
                                logger.info(f"Found entry link: '{text.strip()}' -> {href}")
                                
                                # Skip if it's a javascript: or mailto: link
                                if href.startswith(('javascript:', 'mailto:', '#')):
                                    continue
                                
                                entry_url = href
                                break
                    except Exception as e:
                        logger.debug(f"Error checking selector {selector}: {e}")
                
                if entry_url:
                    # Navigate to the actual entry form
                    if not entry_url.startswith('http'):
                        # Relative URL, make it absolute
                        current_url = page.url
                        if current_url.endswith('/'):
                            base_url = current_url[:-1]
                        else:
                            base_url = '/'.join(current_url.split('/')[:-1])
                        entry_url = f"{base_url}/{entry_url.lstrip('/')}" if not entry_url.startswith('/') else f"{'/'.join(current_url.split('/')[:3])}{entry_url}"
                    
                    logger.info(f"Following entry link to: {entry_url}")
                    
                    # Navigate to the entry form
                    await page.goto(entry_url, timeout=60000)
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    
                    # Take screenshot of entry page
                    entry_screenshot = f"screenshots/entry_form_{int(time.time())}.png"
                    await page.screenshot(path=entry_screenshot)
                    logger.info(f"Entry form screenshot: {entry_screenshot}")
                    
                    # Get new page title
                    entry_title = await page.title()
                    logger.info(f"Entry page title: {entry_title}")
                
                # Now try to detect forms on this page
                logger.info("Detecting form fields...")
                form_fields = await auto_entry._detect_form_fields(page)
                
                if form_fields:
                    logger.info(f"✅ Found {len(form_fields)} form fields!")
                    
                    # Display the fields found
                    for i, field in enumerate(form_fields, 1):
                        logger.info(f"  Field {i}: {field['type']} (label: '{field.get('label', '')}', name: '{field.get('name', '')}')")
                    
                    # Try to fill the form
                    logger.info("Attempting to fill form fields...")
                    filled_count = await auto_entry._fill_form_fields(page, form_fields)
                    logger.info(f"Successfully filled {filled_count} out of {len(form_fields)} fields")
                    
                    # Take screenshot after filling
                    filled_screenshot = f"screenshots/filled_form_{int(time.time())}.png"
                    await page.screenshot(path=filled_screenshot)
                    logger.info(f"Filled form screenshot: {filled_screenshot}")
                    
                    if filled_count > 0:
                        logger.info("✅ Form filling successful! (Not submitting to avoid spam)")
                        
                        # Try to find submit button for validation
                        submit_selectors = [
                            'input[type="submit"]',
                            'button[type="submit"]',
                            'button:has-text("Submit")',
                            'button:has-text("Enter")',
                            '.submit-button'
                        ]
                        
                        submit_found = False
                        for selector in submit_selectors:
                            try:
                                submit_btn = await page.query_selector(selector)
                                if submit_btn and await submit_btn.is_visible():
                                    submit_text = await submit_btn.text_content()
                                    logger.info(f"✅ Found submit button: '{submit_text}' ({selector})")
                                    submit_found = True
                                    break
                            except:
                                pass
                        
                        if not submit_found:
                            logger.info("⚠ No visible submit button found")
                    else:
                        logger.info("⚠ No fields could be filled")
                else:
                    logger.info("❌ No form fields detected on this page")
                    
                    # Try to find any input elements for debugging
                    all_inputs = await page.query_selector_all('input, textarea, select')
                    if all_inputs:
                        logger.info(f"Found {len(all_inputs)} input elements, but they weren't detected as form fields")
                    else:
                        logger.info("No input elements found on the page")
                
            except Exception as e:
                logger.error(f"Error testing {url}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await page.close()
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        await auto_entry.close()

if __name__ == "__main__":
    asyncio.run(test_deep_competition_entry())
