#!/usr/bin/env python3
"""
Final test script for the Competition Auto-Entry System
Tests both authentication and entry on CompetitionCloud
"""

import asyncio
import os
import sys
import logging
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure the correct paths are set up
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import the main entry system
from competition_auto_entry_final import CompetitionAutoEntry, logger

# Configure logging
logging.getLogger().setLevel(logging.INFO)

# Test with CompetitionCloud authentication and a specific competition
async def run_test():
    """Run the full test with CompetitionCloud authentication and entry"""
    
    # Load environment variables
    load_dotenv()
    
    # Check for required credentials
    email = os.getenv("COMPETITION_CLOUD_UNAME")
    password = os.getenv("COMPETITION_CLOUD_PWORD")
    
    if not email or not password:
        logger.error("Missing CompetitionCloud credentials in .env file")
        logger.error("Please add COMPETITION_CLOUD_UNAME and COMPETITION_CLOUD_PWORD to your .env file")
        return
    
    # Initialize the auto-entry system (visible browser for debugging)
    headless = False
    auto_entry = CompetitionAutoEntry(config_path="config/config.json", headless=headless)
    
    try:
        # Initialize the browser
        await auto_entry.initialize()
        
        # Authenticate with CompetitionCloud first (using the main page)
        logger.info("Authenticating with CompetitionCloud...")
        
        # Navigate to the login page directly
        page = await auto_entry.context.new_page()
        login_url = "https://www.competitioncloud.com.au/Account/Login"
        
        logger.info(f"Navigating to login page: {login_url}")
        await page.goto(login_url, timeout=120000)
        
        # Take a screenshot of the login page
        os.makedirs("screenshots", exist_ok=True)
        login_screenshot = f"screenshots/login_page_manual_{int(time.time())}.png"
        await page.screenshot(path=login_screenshot)
        logger.info(f"Login page screenshot saved: {login_screenshot}")
        
        # Fill in login form manually
        logger.info(f"Filling login form with email: {email}")
        await page.fill('input[name="Email"]', email)
        await page.fill('input[name="Password"]', password)
        
        # Click the login button
        logger.info("Clicking login button...")
        await page.click('button[type="submit"]')
        
        # Wait for navigation
        logger.info("Waiting for login to complete...")
        try:
            await page.wait_for_load_state('networkidle', timeout=30000)
        except Exception as e:
            logger.warning(f"Timeout waiting for login completion: {e}")
        
        # Take a screenshot after login attempt
        post_login_screenshot = f"screenshots/post_login_{int(time.time())}.png"
        await page.screenshot(path=post_login_screenshot)
        logger.info(f"Post-login screenshot saved: {post_login_screenshot}")
        
        # Check if login was successful
        current_url = page.url
        logger.info(f"Current URL after login attempt: {current_url}")
        
        if "/Account/Login" in current_url:
            logger.error("Login failed - still on login page")
            return
        
        logger.info("Login appears successful!")
        
        # Now try to navigate to a competition and enter it
        competition_url = "https://www.competitioncloud.com.au/Home/Competition/3eb8cf56-3037-4c91-9ed1-d3d9f3cbef79"
        logger.info(f"Navigating to competition: {competition_url}")
        
        await page.goto(competition_url, timeout=60000)
        
        # Take a screenshot of the competition page
        comp_screenshot = f"screenshots/competition_page_{int(time.time())}.png"
        await page.screenshot(path=comp_screenshot)
        logger.info(f"Competition page screenshot saved: {comp_screenshot}")
        
        # Look for a "Visit Site" button or link
        logger.info("Looking for 'Visit Site' button...")
        visit_site_button = await page.query_selector('a:has-text("Visit Site")')
        
        if visit_site_button:
            logger.info("Found 'Visit Site' button, clicking it...")
            
            # Open in a new tab
            competition_entry_page = await auto_entry.context.new_page()
            
            # Get the href attribute
            href = await visit_site_button.get_attribute("href")
            entry_url = f"https://www.competitioncloud.com.au{href}" if href.startswith("/") else href
            
            logger.info(f"Navigating to entry URL: {entry_url}")
            await competition_entry_page.goto(entry_url, timeout=60000)
            
            # Take a screenshot of the entry page
            entry_screenshot = f"screenshots/entry_page_{int(time.time())}.png"
            await competition_entry_page.screenshot(path=entry_screenshot)
            logger.info(f"Entry page screenshot saved: {entry_screenshot}")
            
            # Wait for any redirects
            try:
                await competition_entry_page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logger.warning(f"Timeout waiting for entry page to stabilize: {e}")
            
            # Now use our entry system to fill and submit the form
            logger.info("Attempting to fill and submit the entry form...")
            
            # Detect form fields
            form_fields = await auto_entry._detect_form_fields(competition_entry_page)
            
            if form_fields:
                logger.info(f"Detected {len(form_fields)} form fields")
                
                # Fill the form
                filled_count = await auto_entry._fill_form_fields(competition_entry_page, form_fields)
                logger.info(f"Filled {filled_count} fields")
                
                # Submit the form
                submit_success = await auto_entry._submit_form(competition_entry_page)
                
                if submit_success:
                    logger.info("Form submitted successfully")
                    
                    # Verify success
                    verify_success = await auto_entry._verify_submission_success(competition_entry_page)
                    
                    if verify_success:
                        logger.info("✓ Competition entry successful!")
                    else:
                        logger.warning("⚠ Competition entry form submitted, but success verification failed")
                else:
                    logger.warning("✗ Failed to submit the competition entry form")
            else:
                logger.warning("No form fields detected on the competition entry page")
        else:
            logger.warning("Could not find 'Visit Site' button on the competition page")
            
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        await auto_entry.close()

if __name__ == "__main__":
    asyncio.run(run_test())
