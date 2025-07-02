#!/usr/bin/env python3
"""
Competition Auto-Entry System - Production Version with Improved Windows Support
Combines DOM inspection and computer vision for robust competition entry
"""

import asyncio
import json
import logging
import time
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv

# Import optional computer vision libraries
try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    CV_AVAILABLE = True
    # Configure Tesseract path for Windows
    if sys.platform == "win32":
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    CV_AVAILABLE = False

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Fix Windows encoding issues
if sys.platform == "win32":
    try:
        import codecs
        if hasattr(sys.stdout, 'detach'):
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        if hasattr(sys.stderr, 'detach'):
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except Exception as e:
        print(f"Warning: Failed to set up Unicode output: {e}")

# Configure logging
os.makedirs('logs', exist_ok=True)
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/competition_entry_{current_time}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompetitionAutoEntry:
    """
    Main competition auto-entry system
    Handles competition discovery, form detection, and entry
    """
    
    def __init__(self, config_path: str = "config/config.json", headless: bool = False):
        self.config = self._load_config(config_path)
        self.headless = headless
        self.cv_detector = ComputerVisionFormDetector() if CV_AVAILABLE else None
        self.playwright = None
        self.browser = None
        self.context = None
        
        # Load personal info from config and .env
        self._load_personal_info()
    
    def _load_personal_info(self):
        """Load personal information from config file and environment variables"""
        # First load from config
        self.personal_info = self.config.get('personal_info', {})
        
        # Then load from environment variables (overriding config)
        load_dotenv()
        env_vars = {
            'FIRST_NAME': 'first_name',
            'LAST_NAME': 'last_name',
            'EMAIL': 'email',
            'PHONE': 'phone',
            'ADDRESS_LINE1': 'address',
            'CITY': 'city',
            'STATE': 'state',
            'POSTAL_CODE': 'postal_code',
            'COUNTRY': 'country'
        }
        
        for env_var, field_name in env_vars.items():
            value = os.getenv(env_var)
            if value:
                self.personal_info[field_name] = value
        
        # Default values for missing fields
        if not self.personal_info:
            self.personal_info = {
                'email': 'example@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+61400000000',
                'address': '123 Sample St',
                'city': 'Sydney',
                'state': 'NSW',
                'postal_code': '2000',
                'country': 'Australia',
                'comments': 'Thank you for the opportunity to participate!'
            }
        
        # Common field aliases
        self.personal_info['address_line1'] = self.personal_info.get('address_line1', self.personal_info.get('address', '123 Sample St'))
        self.personal_info['postcode'] = self.personal_info.get('postal_code', '2000')
        
        # Boolean fields
        self.personal_info['terms'] = True  # Always accept terms
        self.personal_info['terms_checkbox'] = True  # Always accept terms
        self.personal_info['checkbox'] = False  # Default for other checkboxes (marketing etc)
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return {}
    
    async def initialize(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.context = await self.browser.new_context()
        logger.info("Browser initialized")
    
    async def close(self):
        """Close Playwright browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")
    
    async def authenticate(self, site: str):
        """Authenticate with a competition site"""
        logger.info(f"Authenticating with {site}...")
        
        if site.lower() == "competitioncloud":
            return await self._authenticate_competition_cloud()
        elif site.lower() == "gleam":
            return await self._authenticate_gleam()
        else:
            logger.warning(f"No authentication method available for {site}")
            return False
    
    async def _authenticate_competition_cloud(self):
        """Authenticate with CompetitionCloud"""
        email = os.getenv("COMPETITION_CLOUD_UNAME")
        password = os.getenv("COMPETITION_CLOUD_PWORD")
        
        if not email or not password:
            logger.error("Missing CompetitionCloud credentials in .env file")
            return False
        
        try:
            login_page = await self.context.new_page()
            logger.info(f"Navigating to CompetitionCloud login page")
            try:
                # Add longer timeout and progress indicator
                logger.info("Waiting for login page to load (can take a minute)...")
                await login_page.goto("https://www.competitioncloud.com.au/Account/Login", timeout=120000)
                logger.info("Login page loaded, waiting for network to be idle...")
                await login_page.wait_for_load_state('networkidle', timeout=60000)
            except Exception as e:
                logger.warning(f"Timeout while waiting for page to load fully: {e}")
                logger.info("Attempting to continue anyway...")
                
            # Take a screenshot of the login page
            os.makedirs("screenshots", exist_ok=True)
            await login_page.screenshot(path=f"screenshots/login_page_{int(time.time())}.png")
            
            # Print the page content to help with debugging
            page_content = await login_page.content()
            logger.info(f"Page title: {await login_page.title()}")
            logger.info(f"Current URL: {login_page.url}")
            
            # Look for input fields with more relaxed selectors
            email_field = await login_page.query_selector('input[name="Email"], input[type="email"], input[id*="email" i]')
            if not email_field:
                logger.error("Email field not found on login page")
                logger.info("Attempting to use XPath as a fallback...")
                try:
                    email_field = await login_page.query_selector('//input[contains(@placeholder, "Email") or contains(@id, "email") or contains(@name, "email")]')
                except:
                    pass
                
            if not email_field:
                logger.error("Email field not found on login page")
                await login_page.close()
                return False
                
            # Enter credentials
            logger.info(f"Filling email field with: {email}")
            await login_page.fill('input[name="Email"]', email)
            
            logger.info("Filling password field")
            # Remove any quotes that might be in the password from the .env file
            clean_password = password.strip("'")
            await login_page.fill('input[name="Password"]', clean_password)
            
            # Take screenshot before clicking login
            await login_page.screenshot(path=f"screenshots/before_login_{int(time.time())}.png")
            logger.info("Clicking login button")
            
            # Click login button
            await login_page.click('button[type="submit"]')
            
            # Wait for successful login indicators
            try:
                await login_page.wait_for_load_state('networkidle', timeout=30000)
                await login_page.screenshot(path=f"screenshots/after_login_click_{int(time.time())}.png")
                
                for i in range(30):
                    logger.info(f"Waiting for login completion (attempt {i+1}/30)")
                    # Check for logout link
                    logout_link = await login_page.query_selector('a:has-text("Logout")')
                    if logout_link:
                        logger.info("Found logout link - login successful")
                        await login_page.screenshot(path=f"screenshots/login_success_{int(time.time())}.png")
                        await login_page.close()
                        return True
                    
                    # Check for user profile
                    user_profile = await login_page.query_selector('.user-profile')
                    if user_profile:
                        logger.info("Found user profile - login successful")
                        await login_page.screenshot(path=f"screenshots/login_success_{int(time.time())}.png")
                        await login_page.close()
                        return True
                    
                    # Check current URL to see if we're redirected to the dashboard
                    current_url = login_page.url
                    if "dashboard" in current_url.lower() or "account" in current_url.lower():
                        logger.info(f"Redirected to {current_url} - login successful")
                        await login_page.screenshot(path=f"screenshots/login_success_{int(time.time())}.png")
                        await login_page.close()
                        return True
                    
                    # Check for login error messages
                    error_message = await login_page.query_selector('.validation-summary-errors')
                    if error_message:
                        error_text = await error_message.inner_text()
                        logger.error(f"Login error: {error_text}")
                        await login_page.screenshot(path=f"screenshots/login_error_{int(time.time())}.png")
                        await login_page.close()
                        return False
                    
                    await asyncio.sleep(1)
                
                logger.error("Authentication timeout - login indicators not found")
                await login_page.screenshot(path=f"screenshots/login_failed_{int(time.time())}.png")
                # Dump the page content for debugging
                page_content = await login_page.content()
                with open(f"screenshots/failed_login_page_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                await login_page.close()
                return False
            except Exception as e:
                logger.error(f"Error waiting for login completion: {e}")
                await login_page.screenshot(path=f"screenshots/login_exception_{int(time.time())}.png")
                await login_page.close()
                return False
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            if 'login_page' in locals():
                await login_page.screenshot(path=f"screenshots/auth_exception_{int(time.time())}.png")
                await login_page.close()
            return False
            
    async def _authenticate_gleam(self):
        """Authenticate with Gleam.io"""
        email = os.getenv("GLEAM_EMAIL")
        password = os.getenv("GLEAM_PASSWORD")
        
        if not email or not password:
            logger.error("Missing Gleam credentials in .env file")
            return False
        
        try:
            login_page = await self.context.new_page()
            
            # Navigate to any Gleam competition to trigger the login
            await login_page.goto("https://gleam.io/examples/competitions/simple", timeout=60000)
            
            # Click the login button
            login_button = await login_page.query_selector('.login-button')
            if login_button:
                await login_button.click()
                
                # Wait for the login form
                await login_page.wait_for_selector('input[type="email"]', timeout=10000)
                
                # Enter credentials
                await login_page.fill('input[type="email"]', email)
                await login_page.fill('input[type="password"]', password)
                
                # Click the login button
                submit_button = await login_page.query_selector('button[type="submit"]')
                if submit_button:
                    await submit_button.click()
                    
                    # Wait for login to complete
                    await login_page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # Check if login was successful
                    if await login_page.query_selector('.user-details'):
                        logger.info("Successfully logged in to Gleam")
                        await login_page.close()
                        return True
            
            logger.error("Failed to log in to Gleam")
            await login_page.close()
            return False
        except Exception as e:
            logger.error(f"Error during Gleam authentication: {e}")
            if 'login_page' in locals():
                await login_page.close()
            return False
    
    async def enter_competition(self, url: str, needs_auth: bool = False, site: str = None) -> bool:
        """Enter a competition at the given URL"""
        logger.info(f"Attempting to enter competition: {url}")
        
        # Determine site from URL if not provided
        if not site:
            if "competitioncloud.com" in url:
                site = "competitioncloud"
            elif "gleam.io" in url:
                site = "gleam"
        
        # Authenticate if needed
        if needs_auth and site:
            auth_success = await self.authenticate(site)
            if not auth_success:
                logger.error(f"Authentication with {site} failed, cannot continue")
                return False
        
        try:
            # Open competition page
            page = await self.context.new_page()
            logger.info(f"Navigating to {url}")
            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                logger.info("Page loaded, waiting for network idle...")
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logger.warning(f"Timeout while waiting for page to load fully: {e}")
                logger.info("Attempting to continue anyway...")
            
            # Take initial screenshot
            timestamp = int(time.time())
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=f"screenshots/competition_{timestamp}.png")
            
            # Detect form fields (DOM first, CV as fallback)
            form_fields = await self._detect_form_fields(page)
            
            if not form_fields:
                logger.warning("No form fields detected")
                await page.close()
                return False
            
            # Fill form fields
            filled_count = await self._fill_form_fields(page, form_fields)
            
            if filled_count == 0:
                logger.warning("No fields were filled")
                await page.close()
                return False
            
            # Submit the form
            submit_success = await self._submit_form(page)
            
            if not submit_success:
                logger.warning("Failed to submit the form")
                await page.close()
                return False
            
            # Verify submission success
            success = await self._verify_submission_success(page)
            
            # Take final screenshot
            timestamp = int(time.time())
            os.makedirs("confirmations", exist_ok=True)
            
            screenshot_path = f"confirmations/{'success' if success else 'failure'}_{timestamp}.png"
            await page.screenshot(path=screenshot_path)
            
            # Save confirmation data
            confirmation_data = {
                "url": url,
                "timestamp": timestamp,
                "success": success,
                "fields_filled": filled_count,
                "screenshot": screenshot_path
            }
            
            confirmation_file = f"confirmations/{'success' if success else 'failure'}_{timestamp}.json"
            with open(confirmation_file, "w", encoding="utf-8") as f:
                json.dump(confirmation_data, f, indent=2)
            
            await page.close()
            return success
            
        except Exception as e:
            logger.error(f"Error entering competition: {e}")
            if 'page' in locals():
                await page.close()
            return False
    
    async def _detect_form_fields(self, page: Page) -> List[Dict]:
        """Detect form fields using DOM inspection and computer vision"""
        # First try DOM inspection
        dom_fields = await self._detect_form_fields_with_dom(page)
        
        if dom_fields:
            logger.info(f"Detected {len(dom_fields)} form fields via DOM")
            return dom_fields
        
        # Fallback to computer vision if available
        if self.cv_detector and CV_AVAILABLE:
            logger.info("Falling back to computer vision for form detection")
            screenshot_path = f"screenshots/form_detection_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            
            cv_fields = self.cv_detector.detect_form_fields(screenshot_path)
            logger.info(f"Detected {len(cv_fields)} form fields via computer vision")
            
            return cv_fields
        else:
            logger.warning("Computer vision fallback not available")
            return []
    
    async def _detect_form_fields_with_dom(self, page: Page) -> List[Dict]:
        """Detect form fields using Playwright DOM inspection"""
        try:
            form_fields = []
            
            # Find all input elements (text, email, checkboxes) and textareas
            inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[name], textarea, input[type="checkbox"], select')
            
            for input_elem in inputs:
                try:
                    # Get element properties
                    name = await input_elem.get_attribute('name') or ''
                    placeholder = await input_elem.get_attribute('placeholder') or ''
                    input_type = await input_elem.get_attribute('type') or 'text'
                    tag_name = await input_elem.evaluate('el => el.tagName.toLowerCase()')
                    
                    # Get element position
                    box = await input_elem.bounding_box()
                    if not box:
                        continue
                    
                    # Try to find associated label
                    label_text = ''
                    try:
                        # Look for label by 'for' attribute
                        input_id = await input_elem.get_attribute('id')
                        if input_id:
                            label = await page.query_selector(f'label[for="{input_id}"]')
                            if label:
                                label_text = await label.inner_text()
                        
                        # If no label found, look for nearby labels
                        if not label_text:
                            nearby_labels = await page.query_selector_all('label')
                            for label in nearby_labels:
                                label_box = await label.bounding_box()
                                if label_box:
                                    # Check if label is near the input
                                    if (abs(label_box['x'] - box['x']) < 150 and 
                                        abs(label_box['y'] - box['y']) < 50):
                                        label_text = await label.inner_text()
                                        break
                    except Exception as e:
                        logger.debug(f"Error finding label: {e}")
                    
                    # Determine field type
                    field_type = 'unknown'
                    field_identifier = f"{name} {placeholder} {label_text}".lower()
                    
                    if input_type == 'checkbox':
                        field_type = 'checkbox'
                        if any(term in field_identifier for term in ['terms', 'conditions', 'agree', 'accept']):
                            field_type = 'terms'
                    elif tag_name == 'select':
                        field_type = 'select'
                        # Try to determine more specific type from name/label
                        if any(keyword in field_identifier for keyword in ['state', 'province']):
                            field_type = 'state'
                        elif any(keyword in field_identifier for keyword in ['country']):
                            field_type = 'country'
                    else:
                        # Classify based on name/label
                        if any(keyword in field_identifier for keyword in ['email', 'e-mail']):
                            field_type = 'email'
                        elif any(keyword in field_identifier for keyword in ['first', 'given', 'fname']):
                            field_type = 'first_name'
                        elif any(keyword in field_identifier for keyword in ['last', 'surname', 'lname']):
                            field_type = 'last_name'
                        elif 'name' in field_identifier and not any(word in field_identifier for word in ['first', 'last']):
                            field_type = 'first_name'  # Assume generic name field is first name
                        elif any(keyword in field_identifier for keyword in ['phone', 'mobile', 'tel']):
                            field_type = 'phone'
                        elif any(keyword in field_identifier for keyword in ['address', 'street']):
                            field_type = 'address'
                        elif any(keyword in field_identifier for keyword in ['city', 'town']):
                            field_type = 'city'
                        elif any(keyword in field_identifier for keyword in ['zip', 'postal', 'postcode']):
                            field_type = 'postal_code'
                        elif any(keyword in field_identifier for keyword in ['country']):
                            field_type = 'country'
                        elif any(keyword in field_identifier for keyword in ['comment', 'message']):
                            field_type = 'comments'
                    
                    form_fields.append({
                        'x': int(box['x']),
                        'y': int(box['y']),
                        'width': int(box['width']),
                        'height': int(box['height']),
                        'center_x': int(box['x'] + box['width'] / 2),
                        'center_y': int(box['y'] + box['height'] / 2),
                        'name': name,
                        'placeholder': placeholder,
                        'label': label_text,
                        'type': field_type,
                        'input_type': input_type,
                        'tag_name': tag_name,
                        'element': input_elem
                    })
                    
                    logger.info(f"Detected field: {field_type} (name: {name}, label: {label_text})")
                    
                except Exception as e:
                    logger.warning(f"Error processing input element: {e}")
                    continue
            
            return form_fields
            
        except Exception as e:
            logger.error(f"Error detecting form fields with DOM: {e}")
            return []
    
    async def _fill_form_fields(self, page: Page, form_fields: List[Dict]) -> int:
        """Fill form fields with personal information"""
        filled_count = 0
        
        for field in form_fields:
            field_type = field['type']
            
            if field_type in self.personal_info:
                value = self.personal_info[field_type]
                if await self._fill_field(page, field, value):
                    filled_count += 1
            else:
                logger.info(f"Skipping unknown field type: {field_type}")
        
        logger.info(f"Filled {filled_count} out of {len(form_fields)} fields")
        return filled_count
    
    async def _fill_field(self, page: Page, field: Dict, value: Any) -> bool:
        """Fill a single form field"""
        try:
            field_type = field['type']
            # For terms checkbox fields, always check them
            if field_type in ['terms', 'terms_checkbox']:
                value = True
            
            if 'element' in field:
                tag_name = field.get('tag_name', '').lower()
                input_type = field.get('input_type', '').lower()
                
                if input_type == 'checkbox':
                    # Handle checkboxes
                    current_checked = await field['element'].is_checked()
                    should_check = value if isinstance(value, bool) else value.lower() in ['true', 'yes', '1']
                    
                    if current_checked != should_check:
                        await field['element'].click()
                    
                    logger.info(f"Set checkbox {field_type} to: {should_check}")
                    return True
                    
                elif tag_name == 'select':
                    # Handle dropdowns
                    if isinstance(value, (list, tuple)) and len(value) > 0:
                        # If value is a list, use the first item
                        value = value[0]
                    
                    # Try to select by value, text, or index
                    try:
                        await field['element'].select_option(value=str(value))
                    except:
                        try:
                            await field['element'].select_option(label=str(value))
                        except:
                            try:
                                await field['element'].select_option(index=0)  # Select first option as fallback
                            except Exception as e:
                                logger.warning(f"Failed to select option in dropdown: {e}")
                                return False
                    
                    logger.info(f"Selected option in {field_type} dropdown")
                    return True
                    
                else:
                    # Standard text/email fields
                    await field['element'].fill(str(value))
                    logger.info(f"Filled field {field_type} with value: {value}")
                    return True
            else:
                # Fallback to clicking coordinates and typing
                await page.click(field['center_x'], field['center_y'])
                await page.fill('*:focus', str(value))
                logger.info(f"Filled field {field_type} at ({field['center_x']}, {field['center_y']}) with value: {value}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to fill field {field_type}: {e}")
            return False
    
    async def _submit_form(self, page: Page) -> bool:
        """Find and click the submit button"""
        submit_selectors = [
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Enter")',
            'button:has-text("Send")',
            'button:has-text("Join")',
            'button:has-text("Register")',
            'button:has-text("Sign Up")',
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'button:has-text("Apply")',
            'input[value="Submit"]',
            'input[value="Enter"]',
            '.submit-button',
            '#submit',
            'button.btn-primary',
            'button.primary',
            'button.enter-button',
            'a.submit-button',
            'a.enter-button',
            'form .button',
            'form button[type]'
        ]
        
        # Take screenshot before trying to submit
        await page.screenshot(path=f"screenshots/before_submit_{int(time.time())}.png")
        
        # Try each selector
        for selector in submit_selectors:
            try:
                submit_button = await page.query_selector(selector)
                if submit_button:
                    # Check if button is visible and enabled
                    is_visible = await submit_button.is_visible()
                    if not is_visible:
                        logger.info(f"Found submit button {selector} but it's not visible, skipping")
                        continue
                    
                    # Click the button
                    await submit_button.click()
                    logger.info(f"Clicked submit button: {selector}")
                    
                    # Wait for navigation or network idle
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    
                    return True
            except Exception as e:
                logger.warning(f"Error clicking submit button {selector}: {e}")
        
        # Fallback: Try to find buttons by looking for promising candidates
        try:
            logger.info("Using fallback button detection method...")
            buttons = await page.query_selector_all('button, input[type="button"], input[type="submit"], a.button, .btn')
            for button in buttons:
                try:
                    button_text = await button.text_content() or ""
                    button_text = button_text.lower().strip()
                    
                    # Check if this looks like a submit button
                    if any(keyword in button_text for keyword in ['submit', 'enter', 'join', 'register', 'sign up', 'continue', 'next', 'apply']):
                        logger.info(f"Found promising button with text: {button_text}")
                        await button.click()
                        
                        # Wait for navigation or network idle
                        try:
                            await page.wait_for_load_state('networkidle', timeout=10000)
                        except:
                            pass
                            
                        return True
                except Exception as e:
                    logger.warning(f"Error checking/clicking button: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Error in fallback button detection: {e}")
        
        # Last resort: Try to submit any form on the page
        try:
            forms = await page.query_selector_all('form')
            if forms:
                logger.info(f"Attempting to submit form directly")
                await page.evaluate("""() => {
                    document.querySelector('form').submit();
                }""")
                
                # Wait for navigation or network idle
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    pass
                    
                return True
        except Exception as e:
            logger.warning(f"Error submitting form directly: {e}")
        
        logger.warning("Could not find and click any submit button")
        return False
    
    async def _verify_submission_success(self, page: Page) -> bool:
        """Verify that the competition entry was successful"""
        success_indicators = [
            'thank you',
            'thanks for entering',
            'entry received',
            'entry confirmed',
            'entry successful',
            'thank you for your entry',
            'success',
            'confirmation',
            'completed',
            'congratulations',
            'your entry has been submitted',
            'entered successfully',
            'your competition entry',
            'subscribed',
            'we have received your',
            'confirmed',
            'done',
            'complete'
        ]
        
        try:
            # Wait a moment for any redirect or page change
            await asyncio.sleep(2)
            
            # Take a screenshot of the confirmation page
            await page.screenshot(path=f"screenshots/confirmation_{int(time.time())}.png")
            
            # Get page content
            content = await page.content()
            content_lower = content.lower()
            
            # Get page title
            title = await page.title()
            
            # Check for success indicators in page content
            for indicator in success_indicators:
                if indicator.lower() in content_lower or indicator.lower() in title.lower():
                    logger.info(f"Found success indicator: {indicator}")
                    
                    # Capture more details to confirm success
                    message_elements = await page.query_selector_all('h1, h2, h3, h4, .success, .confirmation, .thank-you, .message')
                    for elem in message_elements:
                        try:
                            message = await elem.text_content()
                            if message and len(message.strip()) > 0:
                                logger.info(f"Success message found: {message.strip()}")
                        except:
                            pass
                            
                    return True
            
            # Check for visual confirmation elements
            confirmation_selectors = [
                '.success', 
                '.thank-you', 
                '.confirmation', 
                '.completed',
                '.message',
                '.check-mark',
                '.check-icon',
                '.success-icon',
                '.success-message',
                '#success-message',
                '.alert-success'
            ]
            
            for selector in confirmation_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.info(f"Found visual confirmation element: {selector}")
                    return True
            
            # Check URL change (might indicate redirect to success page)
            current_url = page.url
            if any(word in current_url.lower() for word in ['success', 'thank', 'confirm']):
                logger.info(f"Success URL detected: {current_url}")
                return True
            
            # Take a screenshot of the possible failure
            await page.screenshot(path=f"screenshots/verification_failed_{int(time.time())}.png")
            logger.warning("No success indicators found in the page content")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying submission success: {e}")
            return False

class ComputerVisionFormDetector:
    """
    Computer vision-based form detection system
    Only used as a fallback when DOM detection fails
    """
    
    def __init__(self):
        if not CV_AVAILABLE:
            logger.warning("Computer vision libraries not available. CV-based form detection disabled.")
            return
            
        self.screenshot_path = Path("screenshots")
        self.screenshot_path.mkdir(exist_ok=True)
    
    def detect_form_fields(self, image_path: str) -> List[Dict]:
        """Detect form fields in an image using computer vision"""
        if not CV_AVAILABLE:
            logger.warning("Computer vision libraries not available. Cannot detect form fields.")
            return []
            
        logger.info(f"Analyzing image for form fields: {image_path}")
        
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to load image: {image_path}")
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect form fields using edge detection and contour finding
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        form_fields = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter out very small or very large rectangles
            if w > 50 and h > 15 and w < 1000 and h < 200:
                # Extract the potential field region
                field_region = gray[y:y+h, x:x+w]
                
                # Try to extract text using OCR
                try:
                    label_text = pytesseract.image_to_string(field_region).strip()
                except Exception as e:
                    logger.warning(f"OCR failed for field at ({x}, {y}): {e}")
                    label_text = ""
                
                # Classify the field type
                field_type = self._classify_field_type(label_text)
                
                form_fields.append({
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h,
                    'center_x': x + w // 2,
                    'center_y': y + h // 2,
                    'label': label_text,
                    'type': field_type
                })
                
                logger.info(f"Detected field via CV: {form_fields[-1]}")
        
        return form_fields
    
    def _classify_field_type(self, label_text: str) -> str:
        """Classify the type of form field based on label text"""
        label_lower = label_text.lower()
        
        # Email field detection
        if any(keyword in label_lower for keyword in ['email', 'e-mail', 'mail']):
            return 'email'
        # Name field detection
        elif any(keyword in label_lower for keyword in ['first', 'given', 'fname', 'firstname']):
            return 'first_name'
        elif any(keyword in label_lower for keyword in ['last', 'surname', 'family', 'lname', 'lastname']):
            return 'last_name'
        elif any(keyword in label_lower for keyword in ['name']) and not any(word in label_lower for word in ['first', 'last', 'user']):
            return 'first_name'  # Assume general "name" field is first name
        # Contact info
        elif any(keyword in label_lower for keyword in ['phone', 'mobile', 'tel', 'number']):
            return 'phone'
        # Address fields
        elif any(keyword in label_lower for keyword in ['address', 'street']):
            return 'address'
        elif any(keyword in label_lower for keyword in ['city', 'town']):
            return 'city'
        elif any(keyword in label_lower for keyword in ['state', 'province']):
            return 'state'
        elif any(keyword in label_lower for keyword in ['zip', 'postal', 'postcode']):
            return 'postal_code'
        # Terms and checkboxes
        elif any(keyword in label_lower for keyword in ['terms', 'conditions', 'agree', 'accept']):
            return 'terms'
        elif any(keyword in label_lower for keyword in ['marketing', 'newsletter', 'subscribe']):
            return 'checkbox'
        # Common form fields
        elif any(keyword in label_lower for keyword in ['custname', 'customer', 'comments', 'message']):
            # Try to guess based on context
            if 'name' in label_lower:
                return 'first_name'
            else:
                return 'comments'
        else:
            return 'unknown'

async def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description='Competition Auto-Entry System')
    parser.add_argument('--url', help='URL of the competition to enter')
    parser.add_argument('--auth', action='store_true', help='Authenticate before entering')
    parser.add_argument('--site', help='Site name for authentication (e.g., competitioncloud, gleam)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--test', action='store_true', help='Run in test mode with local form')
    parser.add_argument('--config', default='config/config.json', help='Path to config file')
    
    args = parser.parse_args()
    
    # If testing with local form
    if args.test:
        local_form_path = os.path.abspath("test_form.html")
        if os.path.exists(local_form_path):
            url = f"file://{local_form_path}"
            logger.info(f"Running in test mode with local form: {local_form_path}")
        else:
            logger.error("Test form not found: test_form.html")
            return
    else:
        url = args.url
    
    if not url:
        logger.error("No URL provided. Use --url or --test")
        return
    
    # Initialize the auto-entry system
    auto_entry = CompetitionAutoEntry(config_path=args.config, headless=args.headless)
    
    try:
        await auto_entry.initialize()
        
        # Enter the competition
        success = await auto_entry.enter_competition(
            url, 
            needs_auth=args.auth,
            site=args.site
        )
        
        if success:
            logger.info("✓ Competition entry successful!")
        else:
            logger.warning("✗ Competition entry failed")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await auto_entry.close()

if __name__ == "__main__":
    asyncio.run(main())
