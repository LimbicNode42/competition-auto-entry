#!/usr/bin/env python3
"""
Enhanced Competition Auto-Entry System
Uses computer vision and DOM inspection for robust competition entry
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import sqlite3

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from playwright.async_api import async_playwright
import cv2
import numpy as np
from PIL import Image
import pytesseract
import anthropic

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

class MCPBrowserAutomation:
    """
    Integration with MCP browser automation servers for reliable form interaction
    """
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        
    async def initialize(self):
        """Initialize Playwright for browser automation"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Keep visible for debugging
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
    async def get_page_accessibility_tree(self, url: str) -> Dict:
        """
        Get structured accessibility snapshot similar to Microsoft Playwright MCP
        This provides form elements in a structured format for AI analysis
        """
        page = await self.context.new_page()
        await page.goto(url)
        
        # Wait for page to load
        await page.wait_for_load_state('networkidle')
        
        # Get accessibility tree focused on interactive elements
        accessibility_tree = await page.accessibility.snapshot(
            interesting_only=True
        )
        
        # Extract form elements specifically
        form_elements = await page.evaluate("""
            () => {
                const forms = [];
                document.querySelectorAll('form').forEach(form => {
                    const inputs = [];
                    form.querySelectorAll('input, textarea, select').forEach(input => {
                        inputs.push({
                            type: input.type || input.tagName.toLowerCase(),
                            name: input.name,
                            id: input.id,
                            placeholder: input.placeholder,
                            required: input.required,
                            value: input.value,
                            labels: Array.from(document.querySelectorAll(`label[for="${input.id}"]`))
                                .map(label => label.textContent.trim())
                        });
                    });
                    
                    forms.push({
                        action: form.action,
                        method: form.method,
                        inputs: inputs,
                        submit_buttons: Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'))
                            .map(btn => ({
                                text: btn.textContent || btn.value,
                                id: btn.id,
                                name: btn.name
                            }))
                    });
                });
                return forms;
            }
        """)
        
        await page.close()
        
        return {
            'accessibility_tree': accessibility_tree,
            'form_elements': form_elements,
            'url': url,
            'timestamp': datetime.now().isoformat()
        }

class ComputerVisionFormAnalyzer:
    """
    Computer vision analysis for form field detection and validation
    """
    
    def __init__(self):
        self.anthropic_client = anthropic.Anthropic(
            # Add your Anthropic API key here or use environment variable
            api_key="your-anthropic-api-key"
        )
    
    async def take_screenshot(self, page, element_selector: Optional[str] = None) -> str:
        """Take screenshot of page or specific element"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"screenshots/form_{timestamp}.png"
        
        Path("screenshots").mkdir(exist_ok=True)
        
        if element_selector:
            element = await page.query_selector(element_selector)
            if element:
                await element.screenshot(path=screenshot_path)
            else:
                await page.screenshot(path=screenshot_path)
        else:
            await page.screenshot(path=screenshot_path, full_page=True)
            
        return screenshot_path
    
    def analyze_form_with_cv(self, screenshot_path: str) -> Dict:
        """
        Use OpenCV and OCR to analyze form structure
        """
        # Load image
        image = cv2.imread(screenshot_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect text regions using OCR
        ocr_data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        
        # Find potential form fields (rectangles/input boxes)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        form_fields = []
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter for likely input field dimensions
            if 50 < w < 500 and 20 < h < 60:
                # Extract text near this region
                nearby_text = self._extract_nearby_text(ocr_data, x, y, w, h)
                
                form_fields.append({
                    'field_id': f'cv_field_{i}',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'nearby_text': nearby_text,
                    'likely_field_type': self._classify_field_type(nearby_text)
                })
        
        return {
            'screenshot_path': screenshot_path,
            'detected_fields': form_fields,
            'ocr_confidence': np.mean([int(conf) for conf in ocr_data['conf'] if int(conf) > 0])
        }
    
    def _extract_nearby_text(self, ocr_data: Dict, x: int, y: int, w: int, h: int) -> List[str]:
        """Extract text near a detected form field"""
        nearby_text = []
        
        for i in range(len(ocr_data['text'])):
            if int(ocr_data['conf'][i]) > 30:  # Confidence threshold
                text_x = int(ocr_data['left'][i])
                text_y = int(ocr_data['top'][i])
                
                # Check if text is near the field (within 100px)
                if (abs(text_x - x) < 100 and abs(text_y - y) < 100):
                    text = ocr_data['text'][i].strip()
                    if text:
                        nearby_text.append(text)
        
        return nearby_text
    
    def _classify_field_type(self, nearby_text: List[str]) -> str:
        """Classify form field type based on nearby text"""
        text_combined = ' '.join(nearby_text).lower()
        
        if any(word in text_combined for word in ['email', 'e-mail', '@']):
            return 'email'
        elif any(word in text_combined for word in ['name', 'first', 'last']):
            return 'name'
        elif any(word in text_combined for word in ['phone', 'mobile', 'tel']):
            return 'phone'
        elif any(word in text_combined for word in ['address', 'street', 'city']):
            return 'address'
        elif any(word in text_combined for word in ['age', 'birth', 'dob']):
            return 'age'
        else:
            return 'unknown'
    
    async def validate_with_claude_vision(self, screenshot_path: str, form_data: Dict) -> Dict:
        """
        Use Claude's vision capabilities to validate form completion
        """
        with open(screenshot_path, 'rb') as image_file:
            image_data = image_file.read()
        
        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data.hex()
                                }
                            },
                            {
                                "type": "text",
                                "text": f"""
                                Analyze this form screenshot and determine:
                                
                                1. Are there any visible form fields that appear empty or incorrectly filled?
                                2. Does this look like a legitimate competition entry form?
                                3. Are there any CAPTCHA or verification elements visible?
                                4. What is the confidence level that this form is ready for submission?
                                
                                Form data being entered: {json.dumps(form_data, indent=2)}
                                
                                Provide analysis as JSON with keys: empty_fields, is_legitimate, has_captcha, confidence_score
                                """
                            }
                        ]
                    }
                ]
            )
            
            return json.loads(response.content[0].text)
            
        except Exception as e:
            logger.error(f"Claude vision analysis failed: {e}")
            return {
                'empty_fields': [],
                'is_legitimate': True,
                'has_captcha': False,
                'confidence_score': 0.5,
                'error': str(e)
            }

class EnhancedCompetitionEntry:
    """
    Enhanced competition entry system with MCP and Computer Vision
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.db_path = "competitions.db"
        self.mcp_browser = MCPBrowserAutomation()
        self.cv_analyzer = ComputerVisionFormAnalyzer()
        self._init_database()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._create_default_config(config_path)
    
    def _create_default_config(self, config_path: str) -> Dict:
        """Create default configuration"""
        default_config = {
            "personal_data": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "555-0123",
                "address": "123 Main St",
                "city": "Anytown",
                "postcode": "12345",
                "age": "25",
                "country": "United Kingdom"
            },
            "competition_sources": [
                "https://www.competitioncloud.co.uk"
            ],
            "entry_limits": {
                "max_per_day": 10,
                "delay_between_entries": 30
            },
            "safety_settings": {
                "require_vision_validation": True,
                "require_terms_check": True,
                "max_retry_attempts": 3
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Created default config at {config_path}")
        return default_config
    
    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS competitions (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    deadline TEXT,
                    status TEXT,
                    terms_accepted BOOLEAN,
                    discovered_date TEXT,
                    last_attempt TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    screenshot_path TEXT,
                    cv_analysis TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY,
                    competition_id INTEGER,
                    entry_date TEXT,
                    status TEXT,
                    confirmation_data TEXT,
                    screenshot_path TEXT,
                    FOREIGN KEY (competition_id) REFERENCES competitions (id)
                )
            """)
    
    async def discover_competitions(self, source_url: str) -> List[Dict]:
        """
        Discover competitions using MCP browser automation for reliability
        """
        await self.mcp_browser.initialize()
        
        try:
            # Get structured page data using MCP-style accessibility analysis
            page_data = await self.mcp_browser.get_page_accessibility_tree(source_url)
            
            competitions = []
            
            # Extract competition links from accessibility tree and form elements
            if 'form_elements' in page_data:
                for form in page_data['form_elements']:
                    # Look for competition entry forms
                    if any('enter' in btn['text'].lower() or 'submit' in btn['text'].lower() 
                          for btn in form.get('submit_buttons', [])):
                        
                        competitions.append({
                            'url': form.get('action', source_url),
                            'title': f"Competition form from {source_url}",
                            'deadline': 'Unknown',
                            'entry_method': 'form',
                            'form_data': form
                        })
            
            # Also use traditional scraping as backup
            traditional_competitions = await self._traditional_discovery(source_url)
            competitions.extend(traditional_competitions)
            
            # Store discovered competitions
            for comp in competitions:
                self._store_competition(comp)
            
            logger.info(f"Discovered {len(competitions)} competitions from {source_url}")
            return competitions
            
        except Exception as e:
            logger.error(f"Competition discovery failed: {e}")
            return []
        
        finally:
            if self.mcp_browser.browser:
                await self.mcp_browser.browser.close()
            if self.mcp_browser.playwright:
                await self.mcp_browser.playwright.stop()
    
    async def _traditional_discovery(self, source_url: str) -> List[Dict]:
        """Traditional web scraping as backup method"""
        try:
            response = requests.get(source_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            competitions = []
            
            # Look for competition links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text(strip=True)
                
                if any(keyword in text.lower() for keyword in ['win', 'prize', 'competition', 'enter', 'free']):
                    if href.startswith('/'):
                        href = f"{source_url.rstrip('/')}{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    competitions.append({
                        'url': href,
                        'title': text,
                        'deadline': 'Unknown',
                        'entry_method': 'link'
                    })
            
            return competitions[:10]  # Limit results
            
        except Exception as e:
            logger.error(f"Traditional discovery failed: {e}")
            return []
    
    async def enter_competition_with_cv(self, competition: Dict) -> Dict:
        """
        Enter competition using computer vision validation
        """
        await self.mcp_browser.initialize()
        
        try:
            page = await self.mcp_browser.context.new_page()
            await page.goto(competition['url'])
            await page.wait_for_load_state('networkidle')
            
            # Take initial screenshot
            screenshot_path = await self.cv_analyzer.take_screenshot(page)
            
            # Analyze form with computer vision
            cv_analysis = self.cv_analyzer.analyze_form_with_cv(screenshot_path)
            
            # Fill form using detected fields and accessibility data
            fill_result = await self._fill_form_intelligently(page, cv_analysis)
            
            # Take screenshot after filling
            filled_screenshot = await self.cv_analyzer.take_screenshot(page)
            
            # Validate with Claude Vision
            if self.config['safety_settings']['require_vision_validation']:
                validation = await self.cv_analyzer.validate_with_claude_vision(
                    filled_screenshot, 
                    self.config['personal_data']
                )
                
                if validation.get('confidence_score', 0) < 0.7:
                    logger.warning(f"Low confidence validation: {validation}")
                    return {
                        'status': 'validation_failed',
                        'validation': validation,
                        'screenshot': filled_screenshot
                    }
            
            # Submit if validation passes
            if fill_result.get('ready_for_submission'):
                submit_result = await self._submit_form(page)
                
                # Take final screenshot
                final_screenshot = await self.cv_analyzer.take_screenshot(page)
                
                return {
                    'status': 'success' if submit_result.get('submitted') else 'failed',
                    'screenshots': [screenshot_path, filled_screenshot, final_screenshot],
                    'cv_analysis': cv_analysis,
                    'validation': validation if 'validation' in locals() else None,
                    'submission_result': submit_result
                }
            
            return {
                'status': 'form_incomplete',
                'cv_analysis': cv_analysis,
                'screenshot': filled_screenshot
            }
            
        except Exception as e:
            logger.error(f"Competition entry failed: {e}")
            return {'status': 'error', 'error': str(e)}
        
        finally:
            await page.close()
            if self.mcp_browser.browser:
                await self.mcp_browser.browser.close()
            if self.mcp_browser.playwright:
                await self.mcp_browser.playwright.stop()
    
    async def _fill_form_intelligently(self, page, cv_analysis: Dict) -> Dict:
        """
        Fill form using computer vision analysis and accessibility data
        """
        personal_data = self.config['personal_data']
        filled_fields = []
        
        try:
            # Get all form inputs
            inputs = await page.query_selector_all('input, textarea, select')
            
            for input_element in inputs:
                input_type = await input_element.get_attribute('type') or 'text'
                name = await input_element.get_attribute('name') or ''
                placeholder = await input_element.get_attribute('placeholder') or ''
                id_attr = await input_element.get_attribute('id') or ''
                
                # Skip hidden, submit, and button inputs
                if input_type in ['hidden', 'submit', 'button']:
                    continue
                
                # Determine field type and fill appropriately
                field_info = name + ' ' + placeholder + ' ' + id_attr
                field_info_lower = field_info.lower()
                
                value_to_fill = None
                
                if input_type == 'email' or 'email' in field_info_lower:
                    value_to_fill = personal_data['email']
                elif 'first' in field_info_lower and 'name' in field_info_lower:
                    value_to_fill = personal_data['first_name']
                elif 'last' in field_info_lower and 'name' in field_info_lower:
                    value_to_fill = personal_data['last_name']
                elif 'name' in field_info_lower and 'first' not in field_info_lower and 'last' not in field_info_lower:
                    value_to_fill = f"{personal_data['first_name']} {personal_data['last_name']}"
                elif 'phone' in field_info_lower or 'mobile' in field_info_lower:
                    value_to_fill = personal_data['phone']
                elif 'address' in field_info_lower:
                    value_to_fill = personal_data['address']
                elif 'city' in field_info_lower:
                    value_to_fill = personal_data['city']
                elif 'post' in field_info_lower or 'zip' in field_info_lower:
                    value_to_fill = personal_data['postcode']
                elif 'age' in field_info_lower:
                    value_to_fill = personal_data['age']
                elif 'country' in field_info_lower:
                    value_to_fill = personal_data['country']
                
                # Fill the field if we determined a value
                if value_to_fill:
                    try:
                        await input_element.fill(value_to_fill)
                        filled_fields.append({
                            'field': field_info,
                            'value': value_to_fill,
                            'type': input_type
                        })
                        
                        # Small delay between fields
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"Failed to fill field {field_info}: {e}")
            
            # Check for required checkboxes (terms, newsletter, etc.)
            checkboxes = await page.query_selector_all('input[type="checkbox"]')
            for checkbox in checkboxes:
                label_text = ''
                
                # Try to find associated label
                checkbox_id = await checkbox.get_attribute('id')
                if checkbox_id:
                    label = await page.query_selector(f'label[for="{checkbox_id}"]')
                    if label:
                        label_text = await label.inner_text()
                
                label_text_lower = label_text.lower()
                
                # Check required terms/conditions boxes
                if any(term in label_text_lower for term in ['terms', 'condition', 'privacy', 'agree']):
                    if self.config['safety_settings']['require_terms_check']:
                        logger.info(f"Found terms checkbox: {label_text}")
                        # Require manual review for terms
                        filled_fields.append({
                            'field': 'terms_checkbox',
                            'value': 'REQUIRES_MANUAL_REVIEW',
                            'label': label_text
                        })
                    else:
                        await checkbox.check()
                        filled_fields.append({
                            'field': 'terms_checkbox',
                            'value': 'checked',
                            'label': label_text
                        })
            
            return {
                'filled_fields': filled_fields,
                'ready_for_submission': len(filled_fields) > 0,
                'requires_manual_review': any(f.get('value') == 'REQUIRES_MANUAL_REVIEW' for f in filled_fields)
            }
            
        except Exception as e:
            logger.error(f"Form filling failed: {e}")
            return {'filled_fields': [], 'ready_for_submission': False, 'error': str(e)}
    
    async def _submit_form(self, page) -> Dict:
        """Submit the form after validation"""
        try:
            # Look for submit button
            submit_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Enter")',
                'input[value*="Submit"]',
                'input[value*="Enter"]'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                submit_button = await page.query_selector(selector)
                if submit_button:
                    break
            
            if not submit_button:
                return {'submitted': False, 'error': 'No submit button found'}
            
            # Click submit button
            await submit_button.click()
            
            # Wait for navigation or success indication
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass  # Continue even if timeout
            
            # Check for success indicators
            page_content = await page.content()
            success_indicators = ['thank you', 'success', 'submitted', 'entered', 'confirmation']
            
            is_success = any(indicator in page_content.lower() for indicator in success_indicators)
            
            return {
                'submitted': True,
                'appears_successful': is_success,
                'final_url': page.url,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Form submission failed: {e}")
            return {'submitted': False, 'error': str(e)}
    
    def _store_competition(self, competition: Dict):
        """Store competition in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO competitions 
                (url, title, deadline, status, discovered_date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                competition['url'],
                competition['title'],
                competition.get('deadline', 'Unknown'),
                'discovered',
                datetime.now().isoformat()
            ))
    
    async def run_automated_entry_session(self):
        """Run automated competition entry session"""
        logger.info("Starting automated competition entry session")
        
        # Discover competitions
        all_competitions = []
        for source in self.config['competition_sources']:
            competitions = await self.discover_competitions(source)
            all_competitions.extend(competitions)
        
        if not all_competitions:
            logger.warning("No competitions discovered")
            return
        
        # Enter competitions with rate limiting
        max_entries = self.config['entry_limits']['max_per_day']
        delay = self.config['entry_limits']['delay_between_entries']
        
        successful_entries = 0
        failed_entries = 0
        
        for i, competition in enumerate(all_competitions[:max_entries]):
            logger.info(f"Entering competition {i+1}/{min(len(all_competitions), max_entries)}: {competition['title']}")
            
            result = await self.enter_competition_with_cv(competition)
            
            if result.get('status') == 'success':
                successful_entries += 1
                logger.info(f"✅ Successfully entered: {competition['title']}")
            else:
                failed_entries += 1
                logger.warning(f"❌ Failed to enter: {competition['title']} - {result.get('error', 'Unknown error')}")
            
            # Store entry result
            self._store_entry_result(competition, result)
            
            # Rate limiting delay
            if i < len(all_competitions) - 1:
                logger.info(f"Waiting {delay} seconds before next entry...")
                await asyncio.sleep(delay)
        
        logger.info(f"Session complete: {successful_entries} successful, {failed_entries} failed")
    
    def _store_entry_result(self, competition: Dict, result: Dict):
        """Store entry result in database"""
        with sqlite3.connect(self.db_path) as conn:
            # Update competition record
            conn.execute("""
                UPDATE competitions 
                SET last_attempt = ?, 
                    success_count = success_count + ?,
                    failure_count = failure_count + ?,
                    screenshot_path = ?,
                    cv_analysis = ?
                WHERE url = ?
            """, (
                datetime.now().isoformat(),
                1 if result.get('status') == 'success' else 0,
                1 if result.get('status') != 'success' else 0,
                str(result.get('screenshots', [])),
                json.dumps(result.get('cv_analysis', {})),
                competition['url']
            ))
            
            # Insert entry record
            conn.execute("""
                INSERT INTO entries (competition_id, entry_date, status, confirmation_data, screenshot_path)
                SELECT id, ?, ?, ?, ? FROM competitions WHERE url = ?
            """, (
                datetime.now().isoformat(),
                result.get('status', 'unknown'),
                json.dumps(result),
                str(result.get('screenshots', [])),
                competition['url']
            ))

async def main():
    """Main function"""
    entry_system = EnhancedCompetitionEntry()
    
    # Check if config needs setup
    if not Path("config.json").exists():
        logger.info("First run detected. Please edit config.json with your personal details.")
        return
    
    # Run automated entry session
    await entry_system.run_automated_entry_session()

if __name__ == "__main__":
    # Install requirements first
    required_packages = [
        "requests", "beautifulsoup4", "selenium", "playwright", 
        "opencv-python", "pillow", "pytesseract", "anthropic", "numpy"
    ]
    
    import subprocess
    import sys
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            logger.info(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # Run main function
    asyncio.run(main())
