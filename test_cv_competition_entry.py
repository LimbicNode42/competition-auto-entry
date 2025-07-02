#!/usr/bin/env python3
"""
Working Test Version of Enhanced Competition Auto-Entry System
Uses computer vision and real browser automation without non-existent MCP dependencies
"""

import asyncio
import json
import logging
import time
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv

import cv2
import numpy as np
from PIL import Image
import pytesseract
from playwright.async_api import async_playwright, Page, Browser

# Fix Windows Unicode encoding issues
if sys.platform == "win32":
    import codecs
    if hasattr(sys.stdout, 'detach'):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    if hasattr(sys.stderr, 'detach'):
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
import pyautogui
from mss import mss

# Configure logging with UTF-8 encoding
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/cv_competition_entry.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure Tesseract path for Windows
if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class ComputerVisionFormDetector:
    """
    Computer vision-based form detection and filling system
    """
    
    def __init__(self):
        self.screenshot_path = Path("screenshots")
        self.screenshot_path.mkdir(exist_ok=True)
    
    def take_screenshot(self, filename: str = None) -> str:
        """Take a screenshot of the current screen"""
        if filename is None:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.screenshot_path / filename
        
        with mss() as sct:
            # Get the primary monitor
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            # Convert to PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            img.save(filepath)
        
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)
    
    def detect_form_fields(self, image_path: str) -> List[Dict]:
        """
        Use computer vision to detect form fields in a screenshot
        """
        logger.info(f"Analyzing image for form fields: {image_path}")
        
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Could not load image: {image_path}")
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect form elements using edge detection and contours
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        form_fields = []
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter for rectangular shapes that could be input fields
            aspect_ratio = w / h if h > 0 else 0
            area = w * h
            
            # Look for input field-like rectangles
            if (area > 1000 and area < 50000 and  # Reasonable size
                aspect_ratio > 2 and aspect_ratio < 10 and  # Wide rectangle
                w > 100 and h > 15 and h < 60):  # Input field dimensions
                
                # Extract the region for OCR analysis
                roi = gray[y:y+h, x:x+w]
                
                # Use OCR to detect if there's placeholder text or labels nearby
                try:
                    # Look above the field for labels
                    label_roi = gray[max(0, y-30):y, x:x+w] if y > 30 else None
                    label_text = ""
                    if label_roi is not None and label_roi.size > 0:
                        label_text = pytesseract.image_to_string(label_roi, config='--psm 8').strip()
                    
                    field_info = {
                        'x': x, 'y': y, 'width': w, 'height': h,
                        'center_x': x + w//2, 'center_y': y + h//2,
                        'label': label_text,
                        'type': self._classify_field_type(label_text)
                    }
                    
                    form_fields.append(field_info)
                    logger.info(f"Detected field: {field_info}")
                    
                except Exception as e:
                    logger.warning(f"OCR failed for field at ({x}, {y}): {e}")
        
        logger.info(f"Detected {len(form_fields)} form fields")
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
        # Common form fields
        elif any(keyword in label_lower for keyword in ['custname', 'customer', 'comments', 'message']):
            # Try to guess based on context
            if 'name' in label_lower:
                return 'first_name'
            else:
                return 'comments'
        else:
            return 'unknown'
    
    def fill_field_with_cv(self, field_info: Dict, value: str) -> bool:
        """
        Fill a form field using computer vision coordinates
        """
        try:
            # Click on the field
            pyautogui.click(field_info['center_x'], field_info['center_y'])
            time.sleep(0.5)
            
            # Clear any existing content
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            
            # Type the value
            pyautogui.write(value)
            time.sleep(0.5)
            
            logger.info(f"Filled field {field_info['type']} with value: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fill field {field_info['type']}: {e}")
            return False

class EnhancedCompetitionEntry:
    """
    Enhanced competition entry system with computer vision capabilities
    """
    
    def __init__(self):
        self.cv_detector = ComputerVisionFormDetector()
        self.playwright = None
        self.browser = None
        self.context = None
        
        # Personal info (should be loaded from config)
        self.personal_info = {
            'email': 'wbenjamin400@gmail.com',
            'first_name': 'Benjamin',
            'last_name': 'Wheeler',
            'phone': '+61407099391',
            'address': '39 Hanlan St S',
            'city': 'Narara',
            'state': 'NSW',
            'postal_code': '2250',
            'comments': 'Thank you for the opportunity to participate!',
            'terms_checkbox': True,  # Always accept terms
            'checkbox': False  # Default for other checkboxes (marketing etc)
        }
    
    async def initialize_playwright(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Keep visible for debugging
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.context = await self.browser.new_context()
        logger.info("Playwright browser initialized")
    
    async def close_playwright(self):
        """Close Playwright browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Playwright browser closed")
    
    async def enter_competition_with_cv(self, url: str) -> bool:
        """
        Enter a competition using computer vision for form detection
        """
        logger.info(f"Attempting to enter competition with CV: {url}")
        
        try:
            # Open the page with Playwright
            page = await self.context.new_page()
            # Increase timeout for navigation and add wait options
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Wait a moment for the page to fully render
            await asyncio.sleep(3)
            
            # First try to detect form fields using Playwright DOM inspection
            form_fields = await self._detect_form_fields_with_dom(page)
            
            if not form_fields:
                # Fallback to computer vision detection
                logger.info("No DOM form fields found, falling back to computer vision")
                screenshot_path = self.cv_detector.take_screenshot(f"competition_{int(time.time())}.png")
                form_fields = self.cv_detector.detect_form_fields(screenshot_path)
                
                if not form_fields:
                    logger.warning("No form fields detected by either method")
                    return False
            
            # Fill detected fields
            filled_count = 0
            for field in form_fields:
                field_type = field['type']
                if field_type in self.personal_info:
                    value = self.personal_info[field_type]
                    if await self._fill_field_with_playwright(page, field, value):
                        filled_count += 1
                else:
                    logger.info(f"Skipping unknown field type: {field_type}")
            
            logger.info(f"Filled {filled_count} out of {len(form_fields)} fields")
            
            if filled_count > 0:
                # Look for submit button and click it
                await self._find_and_click_submit_button(page)
                
                # Take another screenshot to confirm submission
                time.sleep(2)
                confirmation_screenshot = self.cv_detector.take_screenshot(f"confirmation_{int(time.time())}.png")
                
                # Check for success indicators
                success = await self._check_submission_success(page)
                
                if success:
                    logger.info("Competition entry successful!")
                    return True
                else:
                    logger.warning("Could not confirm successful submission")
                    return False
            else:
                logger.warning("No fields were filled")
                return False
                
        except Exception as e:
            logger.error(f"Error entering competition: {e}")
            return False
        finally:
            if 'page' in locals():
                await page.close()
    
    async def _detect_form_fields_with_dom(self, page: Page) -> List[Dict]:
        """Detect form fields using Playwright DOM inspection"""
        try:
            form_fields = []
            
            # Find all input elements (text, email, checkboxes) and textareas
            inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[name], textarea, input[type="checkbox"]')
            
            for input_elem in inputs:
                try:
                    # Get element properties
                    name = await input_elem.get_attribute('name') or ''
                    placeholder = await input_elem.get_attribute('placeholder') or ''
                    input_type = await input_elem.get_attribute('type') or 'text'
                    
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
                    except:
                        pass
                    
                    # Special handling for checkboxes
                    if input_type == 'checkbox':
                        field_type = 'checkbox'
                        # Check if this is a terms checkbox
                        if any(term in label_text.lower() for term in ['terms', 'conditions', 'agree', 'accept']):
                            field_type = 'terms_checkbox'
                    else:
                        # Use name, placeholder, or label to determine field type
                        field_identifier = f"{name} {placeholder} {label_text}".lower()
                        field_type = self.cv_detector._classify_field_type(field_identifier)
                    
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
                        'element': input_elem
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing input element: {e}")
                    continue
            
            logger.info(f"Detected {len(form_fields)} form fields via DOM")
            return form_fields
            
        except Exception as e:
            logger.error(f"Error detecting form fields with DOM: {e}")
            return []
    
    async def _fill_field_with_playwright(self, page: Page, field: Dict, value: str) -> bool:
        """Fill a form field using Playwright"""
        try:
            if 'element' in field:
                # Different handling based on input type
                if field.get('input_type') == 'checkbox':
                    # For checkboxes, check or uncheck based on boolean value
                    current_checked = await field['element'].is_checked()
                    should_check = value if isinstance(value, bool) else value.lower() in ['true', 'yes', '1']
                    
                    if current_checked != should_check:
                        await field['element'].click()
                    
                    logger.info(f"Set checkbox {field['type']} to: {should_check}")
                    return True
                else:
                    # Standard text/email fields
                    await field['element'].fill(str(value))
                    logger.info(f"Filled field {field['type']} with value: {value}")
                    return True
            else:
                # Fallback to clicking coordinates and typing
                await page.click(field['center_x'], field['center_y'])
                await page.fill('*:focus', str(value))
                logger.info(f"Filled field {field['type']} at ({field['center_x']}, {field['center_y']}) with value: {value}")
                return True
        except Exception as e:
            logger.error(f"Failed to fill field {field['type']}: {e}")
            return False
    
    async def _find_and_click_submit_button(self, page: Page):
        """Find and click the submit button using multiple strategies"""
        submit_selectors = [
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Enter")',
            'button:has-text("Send")',
            'input[value*="Submit"]',
            'input[value*="Enter"]'
        ]
        
        for selector in submit_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible():
                    await button.click()
                    logger.info(f"Clicked submit button: {selector}")
                    return
            except:
                continue
        
        logger.warning("Could not find submit button")
    
    async def _check_submission_success(self, page: Page) -> bool:
        """Check for indicators of successful submission"""
        success_indicators = [
            "thank you",
            "success",
            "submitted",
            "entered",
            "confirmation",
            "received"
        ]
        
        try:
            # Wait for potential redirect or page update
            await asyncio.sleep(2)
            
            # Get page content
            content = await page.content()
            content_lower = content.lower()
            
            # Check for success indicators
            for indicator in success_indicators:
                if indicator in content_lower:
                    logger.info(f"Found success indicator: {indicator}")
                    return True
            
            # Check URL change (might indicate redirect to success page)
            current_url = page.url
            if any(word in current_url.lower() for word in ['success', 'thank', 'confirm']):
                logger.info(f"Success URL detected: {current_url}")
                return True
            
        except Exception as e:
            logger.error(f"Error checking submission success: {e}")
        
        return False
    
    async def authenticate_competition_cloud(self):
        """Authenticate with CompetitionCloud before entering competitions"""
        logger.info("Authenticating with CompetitionCloud...")
        
        # Load credentials from .env file
        from dotenv import load_dotenv
        import os
        
        # Load environment variables
        load_dotenv()
        email = os.getenv("COMPETITION_CLOUD_UNAME")
        password = os.getenv("COMPETITION_CLOUD_PWORD")
        
        if not email or not password:
            logger.error("Missing credentials in .env file")
            return False
        
        try:
            login_page = await self.context.new_page()
            await login_page.goto("https://www.competitioncloud.com.au/Account/Login", timeout=60000)
            await login_page.wait_for_load_state('networkidle', timeout=30000)
            
            # Enter credentials
            logger.info(f"Filling email field with: {email}")
            await login_page.fill('input[name="Email"]', email)
            
            logger.info("Filling password field")
            await login_page.fill('input[name="Password"]', password.strip("'"))  # Remove any quotes from password
            
            # Take screenshot before clicking login
            await login_page.screenshot(path="screenshots/before_login.png")
            logger.info("Clicking login button")
            
            # Click login button
            await login_page.click('button[type="submit"]')
            
            # Wait for navigation to complete - don't use wait_for_navigation as it can be unreliable
            # Instead wait for elements that indicate successful login
            try:
                # Wait up to 30 seconds for either a logout link or user profile to appear
                for _ in range(30):
                    if await login_page.query_selector('a:has-text("Logout")') or await login_page.query_selector('.user-profile'):
                        logger.info("Successfully authenticated with CompetitionCloud")
                        await login_page.close()
                        return True
                    await asyncio.sleep(1)
                
                # If we get here, login failed
                logger.error("Failed to authenticate with CompetitionCloud - timeout waiting for success indicators")
                # Take a screenshot to debug
                await login_page.screenshot(path="screenshots/login_failed.png")
                await login_page.close()
                return False
            except Exception as e:
                logger.error(f"Error while waiting for login completion: {e}")
                await login_page.close()
                return False
                
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            if 'login_page' in locals():
                await login_page.close()
            return False

async def test_enhanced_system():
    """Test the enhanced competition entry system"""
    logger.info("Testing Enhanced Competition Entry System with Computer Vision")
    
    # Create directories
    Path("logs").mkdir(exist_ok=True)
    Path("screenshots").mkdir(exist_ok=True)
    
    entry_system = EnhancedCompetitionEntry()
    
    try:
        await entry_system.initialize_playwright()
        
        # Use a local test form instead of requiring authentication
        local_form_path = os.path.abspath("test_form.html")
        test_url = f"file://{local_form_path}"
        
        logger.info(f"Testing with local test form: {test_url}")
        
        # Test computer vision detection first
        logger.info("Taking initial screenshot for testing...")
        screenshot = entry_system.cv_detector.take_screenshot("test_initial.png")
        
        # Test the competition entry
        success = await entry_system.enter_competition_with_cv(test_url)
        
        if success:
            logger.info("[PASS] Enhanced competition entry test PASSED")
        else:
            logger.warning("[FAIL] Enhanced competition entry test FAILED")
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
    finally:
        await entry_system.close_playwright()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_enhanced_system())
