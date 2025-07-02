#!/usr/bin/env python3
"""
Enhanced Competition Auto-Entry System with MCP Integration
Combines browser automation with computer vision for intelligent form filling
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image
import pytesseract
import pyautogui
from mss import mss
from playwright.async_api import async_playwright, Page, Browser
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from loguru import logger
import structlog

# Configure logging
logger.remove()
logger.add("logs/competition_mcp_{time}.log", rotation="1 day", retention="7 days")

class CompetitionStatus(Enum):
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    ENTERING = "entering"
    COMPLETED = "completed"
    FAILED = "failed"
    EXCLUDED = "excluded"

class FormFieldType(Enum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    FILE_UPLOAD = "file_upload"
    CAPTCHA = "captcha"

@dataclass
class FormField:
    """Represents a detected form field"""
    field_type: FormFieldType
    selector: str
    label: str
    required: bool
    placeholder: str = ""
    options: List[str] = None
    coordinates: Tuple[int, int, int, int] = None  # x, y, width, height
    confidence: float = 0.0

@dataclass
class CompetitionEntry:
    """Represents a competition entry attempt"""
    url: str
    title: str
    deadline: Optional[datetime]
    status: CompetitionStatus
    entry_requirements: List[str]
    form_fields: List[FormField]
    screenshots: List[str]
    success_indicators: List[str]
    failure_reasons: List[str]

class MCPComputerVision:
    """Computer Vision module for form detection and analysis"""
    
    def __init__(self):
        self.sct = mss()
        self.template_cache = {}
        
    async def capture_screenshot(self, region: Optional[Dict] = None) -> np.ndarray:
        """Capture screenshot of specified region or full screen"""
        if region:
            screenshot = self.sct.grab(region)
        else:
            screenshot = self.sct.grab(self.sct.monitors[1])  # Primary monitor
        
        # Convert to numpy array
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    async def detect_form_fields(self, screenshot: np.ndarray) -> List[FormField]:
        """Use computer vision to detect form fields in screenshot"""
        fields = []
        
        # Convert to grayscale for processing
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        
        # Detect text fields using edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size (likely form fields)
            if 100 < w < 500 and 20 < h < 60:
                # Extract text around the field for labeling
                roi = gray[max(0, y-30):y+h+30, max(0, x-100):x+w+100]
                text = pytesseract.image_to_string(roi, config='--psm 8').strip()
                
                # Determine field type based on context
                field_type = self._classify_field_type(text, w, h)
                
                field = FormField(
                    field_type=field_type,
                    selector=f"field_{x}_{y}",
                    label=text,
                    required="*" in text or "required" in text.lower(),
                    coordinates=(x, y, w, h),
                    confidence=0.8
                )
                fields.append(field)
        
        return fields
    
    def _classify_field_type(self, text: str, width: int, height: int) -> FormFieldType:
        """Classify form field type based on context clues"""
        text_lower = text.lower()
        
        if "email" in text_lower:
            return FormFieldType.EMAIL
        elif "phone" in text_lower or "tel" in text_lower:
            return FormFieldType.PHONE
        elif "name" in text_lower:
            return FormFieldType.TEXT
        elif height > 60:  # Taller fields are likely textareas
            return FormFieldType.TEXTAREA
        elif width < 150:  # Narrow fields might be selects
            return FormFieldType.SELECT
        else:
            return FormFieldType.TEXT
    
    async def detect_submit_button(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        """Detect submit button location"""
        # Load submit button templates
        templates = [
            "templates/submit_button.png",
            "templates/enter_button.png",
            "templates/send_button.png"
        ]
        
        for template_path in templates:
            if os.path.exists(template_path):
                template = cv2.imread(template_path, 0)
                gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > 0.8:  # Good match
                    return max_loc
        
        return None
    
    async def solve_simple_captcha(self, screenshot: np.ndarray, 
                                 captcha_region: Tuple[int, int, int, int]) -> Optional[str]:
        """Attempt to solve simple text-based CAPTCHAs"""
        x, y, w, h = captcha_region
        captcha_img = screenshot[y:y+h, x:x+w]
        
        # Preprocess for better OCR
        gray = cv2.cvtColor(captcha_img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Use OCR to extract text
        captcha_text = pytesseract.image_to_string(binary, config='--psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        
        return captcha_text.strip() if captcha_text.strip() else None

class MCPBrowserAutomation:
    """Enhanced browser automation using MCP patterns"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.cv_module = MCPComputerVision()
        
    async def initialize_browser(self, headless: bool = False):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ]
        )
        self.page = await self.browser.new_page()
        
        # Set viewport and user agent
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        
    async def navigate_to_competition(self, url: str) -> bool:
        """Navigate to competition page with error handling"""
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Allow dynamic content to load
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            return False
    
    async def analyze_page_structure(self) -> Dict[str, Any]:
        """Analyze page structure using both DOM and computer vision"""
        analysis = {
            "title": await self.page.title(),
            "url": self.page.url,
            "forms": [],
            "visual_fields": [],
            "potential_errors": []
        }
        
        # DOM-based form detection
        forms = await self.page.query_selector_all("form")
        for i, form in enumerate(forms):
            form_data = await self._analyze_form_dom(form, i)
            analysis["forms"].append(form_data)
        
        # Computer vision-based detection
        screenshot = await self.cv_module.capture_screenshot()
        visual_fields = await self.cv_module.detect_form_fields(screenshot)
        analysis["visual_fields"] = visual_fields
        
        return analysis
    
    async def _analyze_form_dom(self, form_element, form_index: int) -> Dict[str, Any]:
        """Analyze form using DOM inspection"""
        form_data = {
            "index": form_index,
            "action": await form_element.get_attribute("action"),
            "method": await form_element.get_attribute("method"),
            "fields": []
        }
        
        # Find all input fields
        inputs = await form_element.query_selector_all("input, select, textarea")
        for input_elem in inputs:
            field_info = {
                "type": await input_elem.get_attribute("type"),
                "name": await input_elem.get_attribute("name"),
                "id": await input_elem.get_attribute("id"),
                "placeholder": await input_elem.get_attribute("placeholder"),
                "required": await input_elem.get_attribute("required") is not None,
                "selector": await self._generate_selector(input_elem)
            }
            form_data["fields"].append(field_info)
        
        return form_data
    
    async def _generate_selector(self, element) -> str:
        """Generate a robust CSS selector for an element"""
        element_id = await element.get_attribute("id")
        if element_id:
            return f"#{element_id}"
        
        element_name = await element.get_attribute("name")
        if element_name:
            return f"[name='{element_name}']"
        
        # Fallback to xpath
        return await element.evaluate("el => { const path = []; while (el.nodeType === Node.ELEMENT_NODE) { let siblingCount = 0; let siblingIndex = 0; for (let i = 0; i < el.parentNode.childNodes.length; i++) { const sibling = el.parentNode.childNodes[i]; if (sibling.nodeType === Node.ELEMENT_NODE) { if (sibling === el) siblingIndex = siblingCount; siblingCount++; } } if (siblingCount > 1) { path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (siblingIndex + 1) + ')'); } else { path.unshift(el.tagName.toLowerCase()); } el = el.parentNode; } return path.join(' > '); }")
    
    async def intelligent_form_fill(self, user_data: Dict[str, Any], 
                                  form_analysis: Dict[str, Any]) -> bool:
        """Fill form using intelligent field mapping"""
        try:
            for form in form_analysis["forms"]:
                success = await self._fill_single_form(form, user_data)
                if success:
                    return True
            return False
        except Exception as e:
            logger.error(f"Form filling failed: {e}")
            return False
    
    async def _fill_single_form(self, form_data: Dict[str, Any], 
                              user_data: Dict[str, Any]) -> bool:
        """Fill a single form with user data"""
        filled_fields = 0
        
        for field in form_data["fields"]:
            field_value = self._map_field_value(field, user_data)
            if field_value:
                try:
                    selector = field["selector"]
                    await self.page.fill(selector, str(field_value))
                    filled_fields += 1
                    await asyncio.sleep(0.5)  # Human-like delay
                except Exception as e:
                    logger.warning(f"Failed to fill field {selector}: {e}")
        
        return filled_fields > 0
    
    def _map_field_value(self, field: Dict[str, Any], user_data: Dict[str, Any]) -> Optional[str]:
        """Map form field to appropriate user data"""
        field_name = (field.get("name", "") or "").lower()
        field_placeholder = (field.get("placeholder", "") or "").lower()
        field_id = (field.get("id", "") or "").lower()
        
        # Combine all identifiers for matching
        field_context = f"{field_name} {field_placeholder} {field_id}"
        
        # Email mapping
        if any(keyword in field_context for keyword in ["email", "mail"]):
            return user_data.get("email")
        
        # Name mapping
        if any(keyword in field_context for keyword in ["firstname", "first_name", "fname"]):
            return user_data.get("first_name")
        if any(keyword in field_context for keyword in ["lastname", "last_name", "lname", "surname"]):
            return user_data.get("last_name")
        if "fullname" in field_context or "full_name" in field_context:
            return f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        
        # Phone mapping
        if any(keyword in field_context for keyword in ["phone", "tel", "mobile"]):
            return user_data.get("phone")
        
        # Address mapping
        if "address" in field_context:
            return user_data.get("address")
        if "city" in field_context:
            return user_data.get("city")
        if "postcode" in field_context or "zip" in field_context:
            return user_data.get("postcode")
        
        # Age/DOB mapping
        if "age" in field_context:
            return user_data.get("age")
        if any(keyword in field_context for keyword in ["dob", "birth", "birthday"]):
            return user_data.get("date_of_birth")
        
        return None
    
    async def submit_form_with_verification(self) -> bool:
        """Submit form and verify submission"""
        try:
            # Look for submit button
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Enter')",
                "button:has-text('Send')",
                ".submit-btn",
                "#submit",
                "[name='submit']"
            ]
            
            for selector in submit_selectors:
                submit_btn = await self.page.query_selector(selector)
                if submit_btn:
                    await submit_btn.click()
                    break
            else:
                logger.warning("No submit button found")
                return False
            
            # Wait for submission response
            await asyncio.sleep(3)
            
            # Check for success indicators
            success_indicators = [
                "thank you",
                "success",
                "submitted",
                "confirmation",
                "entered successfully"
            ]
            
            page_content = await self.page.content()
            for indicator in success_indicators:
                if indicator in page_content.lower():
                    logger.info("Form submission successful")
                    return True
            
            # Check for error indicators
            error_indicators = [
                "error",
                "failed",
                "invalid",
                "required field",
                "please complete"
            ]
            
            for indicator in error_indicators:
                if indicator in page_content.lower():
                    logger.warning(f"Form submission failed: {indicator}")
                    return False
            
            return True  # Assume success if no clear indicators
            
        except Exception as e:
            logger.error(f"Form submission failed: {e}")
            return False
    
    async def close(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()

class EnhancedCompetitionEntrySystem:
    """Main system orchestrating MCP-based competition entry"""
    
    def __init__(self, config_path: str = "config/mcp_config.json"):
        self.config = self._load_config(config_path)
        self.browser_automation = MCPBrowserAutomation()
        self.cv_module = MCPComputerVision()
        self.session_log = []
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration with MCP settings"""
        default_config = {
            "user_data": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "1234567890",
                "address": "123 Main St",
                "city": "Anytown",
                "postcode": "12345",
                "age": "25",
                "date_of_birth": "01/01/1999"
            },
            "entry_settings": {
                "max_entries_per_day": 10,
                "delay_between_entries": 30,
                "headless_browser": False,
                "enable_computer_vision": True,
                "screenshot_failed_attempts": True
            },
            "exclusion_rules": [
                "requires purchase",
                "subscription required",
                "premium only",
                "gambling",
                "adults only"
            ]
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    async def run_entry_session(self, competition_urls: List[str]) -> Dict[str, Any]:
        """Run a complete entry session"""
        session_results = {
            "started_at": datetime.now().isoformat(),
            "total_attempts": 0,
            "successful_entries": 0,
            "failed_entries": 0,
            "excluded_competitions": 0,
            "entries": []
        }
        
        await self.browser_automation.initialize_browser(
            headless=self.config["entry_settings"]["headless_browser"]
        )
        
        try:
            for url in competition_urls:
                if session_results["total_attempts"] >= self.config["entry_settings"]["max_entries_per_day"]:
                    logger.info("Daily entry limit reached")
                    break
                
                result = await self._attempt_single_entry(url)
                session_results["entries"].append(result)
                session_results["total_attempts"] += 1
                
                if result["status"] == "completed":
                    session_results["successful_entries"] += 1
                elif result["status"] == "excluded":
                    session_results["excluded_competitions"] += 1
                else:
                    session_results["failed_entries"] += 1
                
                # Delay between entries
                await asyncio.sleep(self.config["entry_settings"]["delay_between_entries"])
        
        finally:
            await self.browser_automation.close()
        
        session_results["completed_at"] = datetime.now().isoformat()
        return session_results
    
    async def _attempt_single_entry(self, url: str) -> Dict[str, Any]:
        """Attempt to enter a single competition"""
        entry_result = {
            "url": url,
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "screenshots": [],
            "error_messages": [],
            "success_indicators": []
        }
        
        try:
            # Navigate to competition
            logger.info(f"Attempting entry for: {url}")
            if not await self.browser_automation.navigate_to_competition(url):
                entry_result["error_messages"].append("Failed to navigate to URL")
                return entry_result
            
            # Analyze page structure
            page_analysis = await self.browser_automation.analyze_page_structure()
            
            # Check exclusion rules
            if self._check_exclusion_rules(page_analysis):
                entry_result["status"] = "excluded"
                entry_result["error_messages"].append("Competition excluded by rules")
                return entry_result
            
            # Fill form intelligently
            if await self.browser_automation.intelligent_form_fill(
                self.config["user_data"], page_analysis
            ):
                # Submit form
                if await self.browser_automation.submit_form_with_verification():
                    entry_result["status"] = "completed"
                    entry_result["success_indicators"].append("Form submitted successfully")
                else:
                    entry_result["error_messages"].append("Form submission failed")
            else:
                entry_result["error_messages"].append("Failed to fill form")
            
            # Take screenshot for debugging
            if self.config["entry_settings"]["screenshot_failed_attempts"] or entry_result["status"] == "completed":
                screenshot_path = f"screenshots/entry_{int(time.time())}.png"
                await self.browser_automation.page.screenshot(path=screenshot_path)
                entry_result["screenshots"].append(screenshot_path)
        
        except Exception as e:
            logger.error(f"Entry attempt failed for {url}: {e}")
            entry_result["error_messages"].append(str(e))
        
        return entry_result
    
    def _check_exclusion_rules(self, page_analysis: Dict[str, Any]) -> bool:
        """Check if competition should be excluded"""
        page_content = page_analysis.get("title", "").lower()
        
        for rule in self.config["exclusion_rules"]:
            if rule in page_content:
                return True
        
        return False

async def main():
    """Main execution function"""
    # Example competition URLs
    competition_urls = [
        "https://example-competition1.com/enter",
        "https://example-competition2.com/giveaway",
        "https://example-competition3.com/contest"
    ]
    
    # Initialize enhanced system
    system = EnhancedCompetitionEntrySystem()
    
    # Run entry session
    results = await system.run_entry_session(competition_urls)
    
    # Print results
    print(json.dumps(results, indent=2))
    
    logger.info(f"Session completed: {results['successful_entries']} successful, {results['failed_entries']} failed")

if __name__ == "__main__":
    asyncio.run(main())
