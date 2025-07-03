#!/usr/bin/env python3
"""
Test CV/MCP Competition Auto-Entry System with AussieComps.com
Focused test of the enhanced system with the configured aggregator
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

async def test_aussiecomps_discovery():
    """Test competition discovery from AussieComps.com"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize the auto-entry system (visible browser for debugging)
    headless = False
    auto_entry = CompetitionAutoEntry(config_path="config/config.json", headless=headless)
    
    try:
        # Initialize the browser
        await auto_entry.initialize()
        
        # Load aggregator sites configuration
        with open("config/aggregator_sites.json", "r") as f:
            aggregator_sites = json.load(f)
        
        for site in aggregator_sites:
            if site["enabled"]:
                logger.info(f"Testing competition discovery from: {site['name']}")
                logger.info(f"URL: {site['url']}")
                
                # Navigate to the site
                page = await auto_entry.context.new_page()
                
                try:
                    logger.info(f"Navigating to {site['url']}...")
                    await page.goto(site['url'], timeout=60000)
                    
                    # Take a screenshot
                    screenshot_path = f"screenshots/aussiecomps_discovery_{int(time.time())}.png"
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Wait for page to load
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    
                    # Get page title and basic info
                    title = await page.title()
                    logger.info(f"Page title: {title}")
                    
                    # Look for competition links
                    # AussieComps typically has competition links with specific patterns
                    competition_selectors = [
                        'a[href*="competition"]',
                        'a[href*="comp"]',
                        'a[href*="giveaway"]',
                        'a[href*="contest"]',
                        '.competition-link',
                        '.comp-link',
                        'a:has-text("Win")',
                        'a:has-text("Enter")',
                        'a:has-text("Competition")',
                    ]
                    
                    competitions_found = []
                    for selector in competition_selectors:
                        try:
                            links = await page.query_selector_all(selector)
                            for link in links[:10]:  # Increase limit to find more competitions
                                href = await link.get_attribute('href')
                                text = await link.text_content()
                                if href and text and len(text.strip()) > 0:
                                    # Filter out non-competition links
                                    text_lower = text.lower().strip()
                                    href_lower = href.lower()
                                    
                                    # Skip contact, mailto, and other non-competition links
                                    if any(skip in text_lower for skip in ['contact', 'about', 'privacy', 'terms']):
                                        continue
                                    if href.startswith('mailto:'):
                                        continue
                                    
                                    # Prioritize actual competition keywords
                                    competition_keywords = ['win', 'competition', 'giveaway', 'contest', 'prize', 'enter']
                                    if any(keyword in text_lower for keyword in competition_keywords):
                                        competitions_found.append({
                                            'url': href,
                                            'title': text.strip(),
                                            'selector': selector,
                                            'priority': 1 if 'win' in text_lower else 2
                                        })
                        except Exception as e:
                            logger.warning(f"Error with selector {selector}: {e}")
                    
                    # Sort by priority (lower number = higher priority)
                    competitions_found.sort(key=lambda x: x.get('priority', 3))
                    
                    logger.info(f"Found {len(competitions_found)} potential competitions")
                    
                    # Display found competitions
                    for i, comp in enumerate(competitions_found[:3], 1):  # Show first 3
                        logger.info(f"Competition {i}: {comp['title']}")
                        logger.info(f"  URL: {comp['url']}")
                        logger.info(f"  Found via: {comp['selector']}")
                    
                    # Try to enter the first competition if found
                    if competitions_found:
                        first_comp = competitions_found[0]
                        logger.info(f"Attempting to test entry for: {first_comp['title']}")
                        
                        # Navigate to the competition
                        comp_url = first_comp['url']
                        if not comp_url.startswith('http'):
                            # Relative URL, make it absolute
                            base_url = site['url'].rstrip('/')
                            comp_url = f"{base_url}/{comp_url.lstrip('/')}"
                        
                        logger.info(f"Navigating to competition: {comp_url}")
                        await page.goto(comp_url, timeout=60000)
                        
                        # Take screenshot of competition page
                        comp_screenshot = f"screenshots/competition_page_{int(time.time())}.png"
                        await page.screenshot(path=comp_screenshot)
                        logger.info(f"Competition page screenshot: {comp_screenshot}")
                        
                        # Try to detect and fill any forms on the page
                        form_fields = await auto_entry._detect_form_fields(page)
                        
                        if form_fields:
                            logger.info(f"Detected {len(form_fields)} form fields on competition page")
                            
                            # Fill the form
                            filled_count = await auto_entry._fill_form_fields(page, form_fields)
                            logger.info(f"Filled {filled_count} fields")
                            
                            # Take screenshot after filling
                            filled_screenshot = f"screenshots/competition_filled_{int(time.time())}.png"
                            await page.screenshot(path=filled_screenshot)
                            logger.info(f"Filled form screenshot: {filled_screenshot}")
                            
                            # Try to submit (but don't actually submit for testing)
                            logger.info("Form filling test completed. (Not submitting to avoid spam)")
                        else:
                            logger.info("No form fields detected on competition page")
                    
                except Exception as e:
                    logger.error(f"Error testing {site['name']}: {e}")
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
    asyncio.run(test_aussiecomps_discovery())
