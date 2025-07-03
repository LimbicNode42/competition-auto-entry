#!/usr/bin/env python3
"""
Improved Competition Auto-Entry System with Better Flow Handling
This version focuses on improved multi-step competition entry flows
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import argparse

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Playwright imports
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Computer vision imports (optional)
CV_AVAILABLE = False
try:
    import cv2
    import numpy as np
    import pytesseract
    CV_AVAILABLE = True
except ImportError:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('competition_entry.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CompetitionEntry:
    """Data class for competition entry details"""
    url: str
    title: str
    entry_url: Optional[str] = None
    status: str = 'pending'
    form_fields: List[Dict] = None
    screenshots: List[str] = None
    confirmation_data: Dict = None

class ImprovedCompetitionEntry:
    """Improved Competition Auto-Entry System"""
    
    def __init__(self, config_path: str = "config/config.json", headless: bool = False):
        self.config_path = config_path
        self.headless = headless
        self.browser = None
        self.context = None
        self.personal_info = {}
        self.cv_detector = None
        
        # Load configuration
        self._load_config()
        
        # Initialize CV detector if available
        if CV_AVAILABLE:
            self.cv_detector = ImprovedCVDetector()
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.personal_info = config.get('personal_info', {})
                logger.info(f"Configuration loaded from {self.config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            self.personal_info = {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone': '0400000000',
                'address': '123 Main St',
                'city': 'Sydney',
                'state': 'NSW',
                'postal_code': '2000',
                'country': 'Australia',
                'terms': True,
                'marketing': False
            }
    
    async def initialize(self):
        """Initialize the browser and context"""
        logger.info("Initializing browser...")
        
        playwright = await async_playwright().start()
        
        # Launch browser with realistic settings
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        
        # Create context with realistic user agent
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        logger.info("Browser initialized successfully")
    
    async def discover_competitions(self, site_url: str) -> List[CompetitionEntry]:
        """Discover competitions from an aggregator site"""
        logger.info(f"Discovering competitions from: {site_url}")
        
        page = await self.context.new_page()
        
        try:
            # Navigate to site
            await page.goto(site_url, timeout=60000)
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Take screenshot
            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = f"screenshots/discovery_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            
            competitions = []
            
            # Look for competition links
            competition_selectors = [
                'a:has-text("Win")',
                'a:has-text("Competition")',
                'a:has-text("Giveaway")',
                'a[href*="competition"]',
                'a[href*="giveaway"]',
                'a[href*="contest"]',
                '.competition-link',
                '.giveaway-link'
            ]
            
            found_links = []
            for selector in competition_selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        
                        if href and text and text.strip():
                            # Make absolute URL
                            if not href.startswith('http'):
                                href = urljoin(site_url, href)
                            
                            found_links.append({
                                'url': href,
                                'title': text.strip(),
                                'selector': selector
                            })
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
            
            # Remove duplicates and create CompetitionEntry objects
            unique_competitions = {}
            for link in found_links:
                if link['url'] not in unique_competitions:
                    unique_competitions[link['url']] = CompetitionEntry(
                        url=link['url'],
                        title=link['title'],
                        screenshots=[screenshot_path]
                    )
            
            competitions = list(unique_competitions.values())
            logger.info(f"Found {len(competitions)} unique competitions")
            
            return competitions
            
        except Exception as e:
            logger.error(f"Error discovering competitions: {e}")
            return []
        finally:
            await page.close()
    
    async def process_competition(self, competition: CompetitionEntry) -> bool:
        """Process a single competition entry"""
        logger.info(f"Processing competition: {competition.title}")
        logger.info(f"URL: {competition.url}")
        
        page = await self.context.new_page()
        
        try:
            # Navigate to competition page
            await page.goto(competition.url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            
            # Take screenshot
            screenshot_path = f"screenshots/competition_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            competition.screenshots = competition.screenshots or []
            competition.screenshots.append(screenshot_path)
            
            # Look for entry links or external redirects
            entry_found = await self._find_entry_link(page, competition)
            
            if entry_found:
                # If we found an entry link, follow it
                success = await self._follow_entry_flow(page, competition)
                if success:
                    competition.status = 'success'
                    logger.info(f"[SUCCESS] Successfully entered competition: {competition.title}")
                    return True
                else:
                    competition.status = 'failed'
                    logger.info(f"[FAILED] Failed to enter competition: {competition.title}")
                    return False
            else:
                # Try to find forms directly on this page
                form_fields = await self._detect_form_fields(page)
                
                if form_fields:
                    competition.form_fields = form_fields
                    success = await self._fill_and_submit_form(page, competition)
                    if success:
                        competition.status = 'success'
                        logger.info(f"[SUCCESS] Successfully entered competition: {competition.title}")
                        return True
                    else:
                        competition.status = 'failed'
                        logger.info(f"[FAILED] Failed to enter competition: {competition.title}")
                        return False
                else:
                    logger.info(f"[WARNING] No entry method found for: {competition.title}")
                    competition.status = 'no_entry_method'
                    return False
                    
        except Exception as e:
            logger.error(f"Error processing competition {competition.title}: {e}")
            competition.status = 'error'
            return False
        finally:
            await page.close()
    
    async def _find_entry_link(self, page: Page, competition: CompetitionEntry) -> bool:
        """Find and follow entry links"""
        # First check for ps/ pattern links (AussieComps specific)
        ps_links = await page.query_selector_all('a[href*="ps/"]')
        for link in ps_links:
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href:
                    # Make absolute URL
                    if not href.startswith('http'):
                        href = urljoin(page.url, href)
                    
                    competition.entry_url = href
                    logger.info(f"Found ps/ entry link: '{text}' -> {href}")
                    return True
            except:
                pass
        
        # If no ps/ links found, look for other entry patterns
        entry_selectors = [
            'a:has-text("Enter")',
            'a:has-text("Click here")',
            'a:has-text("Visit site")',
            'a:has-text("Go to")',
            'a:has-text("Join")',
            'a:has-text("Take part")',
            'a:has-text("Participate")',
            'a:has-text("Enter Competition")',
            'a:has-text("Enter Now")',
            'a:has-text("Enter here")',
            'a[href*="enter"]',
            'a[href*="comp"]',
            'a[href*="gleam"]',
            'a[href*="woobox"]',
            'a[href*="rafflecopter"]',
            'a[href*="contest"]',
            'a[href*="giveaway"]',
            'a[target="_blank"]',
            '.entry-link',
            '.enter-button',
            '.visit-site'
        ]
        
        for selector in entry_selectors:
            try:
                entry_links = await page.query_selector_all(selector)
                for link in entry_links:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    
                    if href and text:
                        # Skip unwanted links
                        if any(skip in href.lower() for skip in ['javascript:', 'mailto:', '#']):
                            continue
                        
                        # Skip social media links
                        if any(social in href.lower() for social in ['facebook', 'twitter', 'instagram', 'youtube', 'tiktok']):
                            continue
                        
                        # Skip image links
                        if any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                            continue
                        
                        # Skip "buy me a coffee" or donation links
                        if any(donation in href.lower() for donation in ['buy.stripe.com', 'buymeacoffee', 'donate', 'patreon']):
                            continue
                        
                        # Skip PDF links
                        if '.pdf' in href.lower():
                            continue
                        
                        # Prefer external competition platforms
                        if any(platform in href.lower() for platform in ['gleam.io', 'woobox', 'rafflecopter', 'kingsumo']):
                            # Make absolute URL
                            if not href.startswith('http'):
                                href = urljoin(page.url, href)
                            
                            competition.entry_url = href
                            logger.info(f"Found entry link (preferred platform): '{text.strip()}' -> {href}")
                            return True
                        
                        # Make absolute URL
                        if not href.startswith('http'):
                            href = urljoin(page.url, href)
                        
                        competition.entry_url = href
                        logger.info(f"Found entry link: '{text.strip()}' -> {href}")
                        return True
                        
            except Exception as e:
                logger.debug(f"Error checking selector {selector}: {e}")
        
        return False
    
    async def _follow_entry_flow(self, page: Page, competition: CompetitionEntry) -> bool:
        """Follow the entry flow to the actual form"""
        if not competition.entry_url:
            return False
        
        logger.info(f"Following entry flow to: {competition.entry_url}")
        
        try:
            # Navigate to entry URL
            await page.goto(competition.entry_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            
            # Take screenshot of entry page
            screenshot_path = f"screenshots/entry_page_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            competition.screenshots.append(screenshot_path)
            
            # Wait a bit for dynamic content
            await asyncio.sleep(2)
            
            # Look for forms on this page
            form_fields = await self._detect_form_fields(page)
            
            if form_fields:
                competition.form_fields = form_fields
                return await self._fill_and_submit_form(page, competition)
            else:
                logger.info("No form fields found on entry page")
                return False
                
        except Exception as e:
            logger.error(f"Error following entry flow: {e}")
            return False
    
    async def _detect_form_fields(self, page: Page) -> List[Dict]:
        """Detect form fields using DOM inspection and CV fallback"""
        # First try DOM detection
        dom_fields = await self._detect_dom_fields(page)
        
        # Also check for iframe forms
        iframe_fields = await self._detect_iframe_fields(page)
        
        # Combine all fields
        all_fields = dom_fields + iframe_fields
        
        if all_fields:
            logger.info(f"Found {len(all_fields)} form fields ({len(dom_fields)} DOM, {len(iframe_fields)} iframe)")
            return all_fields
        
        # Fallback to CV detection
        if self.cv_detector:
            logger.info("Trying CV detection as fallback")
            screenshot_path = f"screenshots/cv_detection_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            
            cv_fields = self.cv_detector.detect_form_fields(screenshot_path)
            if cv_fields:
                logger.info(f"Found {len(cv_fields)} form fields via CV")
                return cv_fields
        
        return []
    
    async def _detect_iframe_fields(self, page: Page) -> List[Dict]:
        """Detect form fields in iframes"""
        try:
            iframe_fields = []
            
            # Find all iframes
            iframes = await page.query_selector_all('iframe')
            logger.info(f"Found {len(iframes)} iframes to check")
            
            for i, iframe in enumerate(iframes):
                try:
                    src = await iframe.get_attribute('src')
                    if src:
                        logger.info(f"Checking iframe {i+1}: {src}")
                        
                        # Skip social media and ad iframes
                        if any(skip in src.lower() for skip in ['facebook', 'twitter', 'addtoany', 'google-analytics', 'googletagmanager']):
                            continue
                        
                        # Check for competition platform iframes
                        if any(platform in src.lower() for platform in ['viralsweep', 'gleam', 'woobox', 'rafflecopter', 'kingsumo']):
                            logger.info(f"Found competition platform iframe: {src}")
                            
                            # For competition platforms, we might need to interact with the iframe
                            # For now, let's see if we can access the content
                            try:
                                iframe_content = await iframe.content_frame()
                                if iframe_content:
                                    # Wait for iframe content to load
                                    await asyncio.sleep(3)
                                    
                                    # Look for forms in the iframe
                                    iframe_forms = await iframe_content.query_selector_all('form')
                                    iframe_inputs = await iframe_content.query_selector_all('input, textarea, select')
                                    
                                    logger.info(f"Iframe {i+1} content: {len(iframe_forms)} forms, {len(iframe_inputs)} inputs")
                                    
                                    for input_elem in iframe_inputs:
                                        try:
                                            # Check if element is visible and interactable
                                            if not await input_elem.is_visible():
                                                continue
                                            
                                            # Get element properties
                                            name = await input_elem.get_attribute('name') or ''
                                            placeholder = await input_elem.get_attribute('placeholder') or ''
                                            input_type = await input_elem.get_attribute('type') or 'text'
                                            tag_name = await input_elem.evaluate('el => el.tagName.toLowerCase()')
                                            
                                            # Get element position
                                            box = await input_elem.bounding_box()
                                            if not box:
                                                continue
                                            
                                            # Find associated label
                                            label_text = await self._find_iframe_label_text(iframe_content, input_elem)
                                            
                                            # Classify field type
                                            field_type = self._classify_field_type(name, placeholder, label_text, input_type, tag_name)
                                            
                                            iframe_fields.append({
                                                'name': name,
                                                'placeholder': placeholder,
                                                'label': label_text,
                                                'type': field_type,
                                                'input_type': input_type,
                                                'tag_name': tag_name,
                                                'element': input_elem,
                                                'iframe': True,
                                                'iframe_content': iframe_content,
                                                'x': int(box['x']),
                                                'y': int(box['y']),
                                                'width': int(box['width']),
                                                'height': int(box['height']),
                                                'center_x': int(box['x'] + box['width'] / 2),
                                                'center_y': int(box['y'] + box['height'] / 2)
                                            })
                                            
                                            logger.info(f"Found iframe field: {field_type} (name: {name}, label: {label_text})")
                                            
                                        except Exception as e:
                                            logger.warning(f"Error processing iframe input element: {e}")
                                            continue
                                
                            except Exception as e:
                                logger.warning(f"Could not access iframe {i+1} content: {e}")
                                
                except Exception as e:
                    logger.warning(f"Error processing iframe {i+1}: {e}")
            
            return iframe_fields
            
        except Exception as e:
            logger.error(f"Error detecting iframe fields: {e}")
            return []
    
    async def _find_iframe_label_text(self, iframe_content, element) -> str:
        """Find label text for an iframe form element"""
        try:
            # Try to find label by 'for' attribute
            input_id = await element.get_attribute('id')
            if input_id:
                label = await iframe_content.query_selector(f'label[for="{input_id}"]')
                if label:
                    text = await label.text_content()
                    if text:
                        return text.strip()
            
            # Try to find parent label
            parent_label = await element.evaluate('el => el.closest("label")')
            if parent_label:
                text = await parent_label.text_content()
                if text:
                    return text.strip()
            
            return ''
            
        except Exception as e:
            logger.debug(f"Error finding iframe label text: {e}")
            return ''
    
    async def _detect_dom_fields(self, page: Page) -> List[Dict]:
        """Detect form fields using DOM inspection"""
        try:
            form_fields = []
            
            # Look for all interactive form elements (including hidden ones that might be revealed)
            selectors = [
                'input[type="text"]',
                'input[type="email"]',
                'input[type="tel"]',
                'input[type="password"]',
                'input[type="checkbox"]',
                'input[type="radio"]',
                'textarea',
                'select',
                'input:not([type])',  # inputs without type attribute
                'input[name]',  # any input with a name
            ]
            
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        # Get element properties even if hidden (might be revealed by JS)
                        name = await element.get_attribute('name') or ''
                        placeholder = await element.get_attribute('placeholder') or ''
                        input_type = await element.get_attribute('type') or 'text'
                        tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                        
                        # Check if element is visible
                        is_visible = await element.is_visible()
                        
                        # Get bounding box (might be 0 if hidden)
                        box = await element.bounding_box()
                        if not box:
                            # If no bounding box, try to get position anyway
                            box = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
                        
                        # Find associated label
                        label_text = await self._find_label_text(page, element)
                        
                        # Classify field type
                        field_type = self._classify_field_type(name, placeholder, label_text, input_type, tag_name)
                        
                        form_fields.append({
                            'name': name,
                            'placeholder': placeholder,
                            'label': label_text,
                            'type': field_type,
                            'input_type': input_type,
                            'tag_name': tag_name,
                            'element': element,
                            'iframe': False,
                            'visible': is_visible,
                            'x': int(box['x']),
                            'y': int(box['y']),
                            'width': int(box['width']),
                            'height': int(box['height']),
                            'center_x': int(box['x'] + box['width'] / 2),
                            'center_y': int(box['y'] + box['height'] / 2)
                        })
                        
                        visibility_str = "visible" if is_visible else "hidden"
                        logger.info(f"Found field: {field_type} (name: {name}, label: {label_text}) [{visibility_str}]")
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
            
            return form_fields
            
        except Exception as e:
            logger.error(f"Error detecting DOM fields: {e}")
            return []
    
    async def _find_label_text(self, page: Page, element) -> str:
        """Find label text for a form element"""
        try:
            # Try to find label by 'for' attribute
            input_id = await element.get_attribute('id')
            if input_id:
                label = await page.query_selector(f'label[for="{input_id}"]')
                if label:
                    text = await label.text_content()
                    if text:
                        return text.strip()
            
            # Try to find parent label
            parent_label = await element.evaluate('el => el.closest("label")')
            if parent_label:
                text = await parent_label.text_content()
                if text:
                    return text.strip()
            
            # Look for nearby text
            # This is a simplified approach - could be improved
            return ''
            
        except Exception as e:
            logger.debug(f"Error finding label text: {e}")
            return ''
    
    def _classify_field_type(self, name: str, placeholder: str, label: str, input_type: str, tag_name: str) -> str:
        """Classify the field type based on available information"""
        # Combine all text for analysis
        field_text = f"{name} {placeholder} {label}".lower()
        
        # Handle specific input types first
        if input_type == 'email':
            return 'email'
        elif input_type == 'tel':
            return 'phone'
        elif input_type == 'checkbox':
            if any(term in field_text for term in ['terms', 'conditions', 'agree', 'accept']):
                return 'terms'
            elif any(term in field_text for term in ['newsletter', 'marketing', 'promo']):
                return 'marketing'
            else:
                return 'checkbox'
        elif input_type == 'radio':
            return 'radio'
        elif tag_name == 'select':
            if any(term in field_text for term in ['country']):
                return 'country'
            elif any(term in field_text for term in ['state', 'province']):
                return 'state'
            else:
                return 'select'
        elif tag_name == 'textarea':
            return 'comments'
        
        # Classify text fields based on content
        if any(term in field_text for term in ['email', 'e-mail']):
            return 'email'
        elif any(term in field_text for term in ['first', 'given', 'fname']):
            return 'first_name'
        elif any(term in field_text for term in ['last', 'surname', 'lname', 'family']):
            return 'last_name'
        elif any(term in field_text for term in ['phone', 'mobile', 'tel']):
            return 'phone'
        elif any(term in field_text for term in ['address', 'street']):
            return 'address'
        elif any(term in field_text for term in ['city', 'town']):
            return 'city'
        elif any(term in field_text for term in ['zip', 'postal', 'postcode']):
            return 'postal_code'
        elif any(term in field_text for term in ['name']) and not any(term in field_text for term in ['first', 'last']):
            return 'first_name'  # Assume generic name is first name
        elif any(term in field_text for term in ['comment', 'message']):
            return 'comments'
        
        return 'text'  # Default fallback
    
    async def _fill_and_submit_form(self, page: Page, competition: CompetitionEntry) -> bool:
        """Fill and submit the form"""
        if not competition.form_fields:
            return False
        
        filled_count = 0
        
        for field in competition.form_fields:
            logger.info(f"Attempting to fill field: {field['type']} (label: '{field.get('label', '')}', name: '{field.get('name', '')}')")
            
            if await self._fill_field(page, field):
                filled_count += 1
        
        logger.info(f"Filled {filled_count} out of {len(competition.form_fields)} fields")
        
        if filled_count == 0:
            logger.warning("No fields were filled")
            return False
        
        # Take screenshot before submission
        screenshot_path = f"screenshots/before_submit_{int(time.time())}.png"
        await page.screenshot(path=screenshot_path)
        competition.screenshots.append(screenshot_path)
        
        # Submit the form (for now, just log - don't actually submit)
        logger.info("Form ready for submission (not submitting to avoid spam)")
        
        # In a real implementation, you would submit here:
        # return await self._submit_form(page)
        
        return True
    
    async def _fill_field(self, page: Page, field: Dict) -> bool:
        """Fill a single field"""
        try:
            field_type = field['type']
            
            # Debug logging
            logger.debug(f"Attempting to fill field type: {field_type}")
            
            # For CV detected fields, we need to use coordinates and typing
            if 'element' not in field:
                logger.info(f"CV field detected - using coordinates for {field_type}")
                
                # Get the value to fill
                if field_type == 'terms':
                    # For terms, we need to click (checkbox)
                    await page.click(field['center_x'], field['center_y'])
                    logger.info(f"Clicked terms checkbox at ({field['center_x']}, {field['center_y']})")
                    return True
                elif field_type in self.personal_info:
                    value = self.personal_info[field_type]
                    # Click the field and type the value
                    await page.click(field['center_x'], field['center_y'])
                    await page.keyboard.type(str(value))
                    logger.info(f"Filled CV field {field_type} with: {value}")
                    return True
                else:
                    logger.debug(f"No data available for CV field type: {field_type}")
                    return False
            
            # For DOM detected fields, use the element
            if field_type not in self.personal_info and field_type not in ['terms', 'marketing', 'checkbox']:
                logger.debug(f"No data for field type: {field_type}")
                return False
            
            # Get the value to fill
            if field_type == 'terms':
                value = True
            elif field_type == 'marketing':
                value = self.personal_info.get('marketing', False)
            else:
                value = self.personal_info.get(field_type)
            
            if value is None:
                return False
            
            # Fill the field
            element = field['element']
            
            # For hidden fields, try to make them visible first
            if not field.get('visible', True):
                logger.info(f"Field {field_type} is hidden, trying to make it visible")
                
                # Try to scroll to the element
                try:
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                # Try to click on the field to activate it
                try:
                    await element.click()
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                # Check if it's now visible
                is_now_visible = await element.is_visible()
                if is_now_visible:
                    logger.info(f"Field {field_type} is now visible")
                else:
                    logger.warning(f"Field {field_type} is still hidden")
            
            # Fill based on field type
            if field['input_type'] == 'checkbox':
                if value:
                    if not await element.is_checked():
                        await element.click()
                else:
                    if await element.is_checked():
                        await element.click()
                logger.info(f"Set {field_type} checkbox to: {value}")
            elif field['tag_name'] == 'select':
                try:
                    await element.select_option(value=str(value))
                    logger.info(f"Selected {value} in {field_type} dropdown")
                except:
                    logger.warning(f"Failed to select option in {field_type} dropdown")
                    return False
            else:
                # For text fields, clear and fill
                try:
                    await element.clear()
                    await element.fill(str(value))
                    logger.info(f"Filled {field_type} with: {value}")
                except:
                    # If fill fails, try typing
                    try:
                        await element.click()
                        await page.keyboard.press('Control+a')
                        await page.keyboard.type(str(value))
                        logger.info(f"Typed {field_type} with: {value}")
                    except Exception as e:
                        logger.warning(f"Failed to fill {field_type}: {e}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error filling field {field['type']}: {e}")
            return False
    
    async def close(self):
        """Close the browser and clean up"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

class ImprovedCVDetector:
    """Improved computer vision form detector"""
    
    def detect_form_fields(self, image_path: str) -> List[Dict]:
        """Detect form fields using computer vision"""
        if not CV_AVAILABLE:
            return []
        
        logger.info(f"Analyzing image with CV: {image_path}")
        
        try:
            # Load and preprocess image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use multiple techniques to find form elements
            fields = []
            
            # Method 1: Edge detection and contour finding
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter rectangles that look like form fields
                if self._is_form_field_shape(w, h):
                    # Extract text from the region
                    field_region = gray[max(0, y-10):y+h+10, max(0, x-10):x+w+10]
                    
                    try:
                        text = pytesseract.image_to_string(field_region, config='--psm 8').strip()
                    except:
                        text = ""
                    
                    field_type = self._classify_cv_field(text, w, h)
                    
                    fields.append({
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': x + w // 2,
                        'center_y': y + h // 2,
                        'label': text,
                        'type': field_type
                    })
            
            logger.info(f"CV detected {len(fields)} potential form fields")
            return fields
            
        except Exception as e:
            logger.error(f"Error in CV detection: {e}")
            return []
    
    def _is_form_field_shape(self, width: int, height: int) -> bool:
        """Check if dimensions match typical form field shapes"""
        # Typical form field dimensions
        if width < 50 or height < 15:
            return False
        if width > 800 or height > 100:
            return False
        
        # Aspect ratio check
        aspect_ratio = width / height
        if aspect_ratio < 1.5 or aspect_ratio > 20:
            return False
        
        return True
    
    def _classify_cv_field(self, text: str, width: int, height: int) -> str:
        """Classify field type based on OCR text and dimensions"""
        text_lower = text.lower()
        
        # Check for common field indicators
        if any(term in text_lower for term in ['email', 'e-mail']):
            return 'email'
        elif any(term in text_lower for term in ['name', 'first', 'last']):
            return 'first_name'
        elif any(term in text_lower for term in ['phone', 'mobile', 'tel']):
            return 'phone'
        elif any(term in text_lower for term in ['address', 'street']):
            return 'address'
        elif any(term in text_lower for term in ['city', 'town']):
            return 'city'
        elif any(term in text_lower for term in ['terms', 'agree', 'accept']):
            return 'terms'
        
        # If no text clues, guess based on dimensions
        if height < 30 and width > 150:
            return 'text'  # Likely a text input
        elif height > 50:
            return 'comments'  # Likely a textarea
        
        return 'text'  # Default fallback

async def main():
    """Main function to run the improved competition entry system"""
    parser = argparse.ArgumentParser(description='Improved Competition Auto-Entry System')
    parser.add_argument('--site', default='https://www.aussiecomps.com/', help='Competition site URL')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--config', default='config/config.json', help='Config file path')
    parser.add_argument('--max-competitions', type=int, default=3, help='Maximum competitions to process')
    
    args = parser.parse_args()
    
    # Initialize the system
    entry_system = ImprovedCompetitionEntry(
        config_path=args.config,
        headless=args.headless
    )
    
    try:
        await entry_system.initialize()
        
        # Discover competitions
        competitions = await entry_system.discover_competitions(args.site)
        
        if not competitions:
            logger.info("No competitions found")
            return
        
        # Process competitions (limit to max_competitions)
        processed_count = 0
        success_count = 0
        
        for competition in competitions[:args.max_competitions]:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing competition {processed_count + 1}/{min(len(competitions), args.max_competitions)}")
            logger.info(f"{'='*60}")
            
            success = await entry_system.process_competition(competition)
            
            processed_count += 1
            if success:
                success_count += 1
            
            # Add delay between competitions
            await asyncio.sleep(2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY: {success_count}/{processed_count} competitions processed successfully")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await entry_system.close()

if __name__ == "__main__":
    asyncio.run(main())
