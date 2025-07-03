#!/usr/bin/env python3
"""
Adaptive Competition Entry System with Symbolic Decision Trees and Backtracking
Uses CV + AI to dynamically adapt to any competition format
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin, urlparse

# Playwright for browser automation
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DecisionNode:
    """Symbolic decision node for backtracking and learning"""
    def __init__(self, node_id: str, page_url: str, screenshot_path: str, 
                 decision_type: str, description: str = ""):
        self.node_id = node_id
        self.page_url = page_url
        self.screenshot_path = screenshot_path
        self.decision_type = decision_type
        self.description = description
        self.options = []
        self.chosen_option = None
        self.children = []
        self.parent = None
        self.success = None
        self.error_message = None
        self.timestamp = datetime.now()
        self.retry_count = 0
        self.metadata = {}

    def add_option(self, option: Dict):
        """Add a decision option"""
        option['option_id'] = len(self.options)
        self.options.append(option)

    def choose_option(self, option_index: int):
        """Choose a specific option"""
        if 0 <= option_index < len(self.options):
            self.chosen_option = self.options[option_index]
            return True
        return False

    def add_child(self, child: 'DecisionNode'):
        """Add a child node"""
        child.parent = self
        self.children.append(child)

    def mark_success(self):
        """Mark as successful"""
        self.success = True

    def mark_failure(self, error: str):
        """Mark as failed"""
        self.success = False
        self.error_message = error

    def get_path_to_root(self) -> List['DecisionNode']:
        """Get decision path from root to this node"""
        path = []
        current = self
        while current:
            path.append(current)
            current = current.parent
        return path[::-1]

    def find_alternative_options(self) -> List[Dict]:
        """Find unused options for backtracking"""
        if not self.chosen_option:
            return self.options
        
        chosen_id = self.chosen_option.get('option_id')
        return [opt for opt in self.options if opt.get('option_id') != chosen_id]

class AdaptiveCompetitionEntry:
    """
    Adaptive competition entry system with symbolic decision trees
    Can learn from failures and adapt to new competition formats
    """
    
    def __init__(self, config_path: str = "config/config.json", headless: bool = False):
        self.config_path = config_path
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.personal_info = {}
        self.decision_history = []
        
        # Ensure directories exist
        Path("screenshots").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("decision_trees").mkdir(exist_ok=True)
        
        self._load_config()

    def _load_config(self):
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.personal_info = config.get('personal_info', {})
                logger.info("Configuration loaded")
        except Exception as e:
            logger.warning(f"Using default config: {e}")
            self.personal_info = {
                'first_name': 'Benjamin',
                'last_name': 'Wheeler',
                'email': 'wbenjamin400@gmail.com',
                'phone': '+61407099391',
                'postal_code': '2250',
                'address': '123 Main St',
                'city': 'Sydney',
                'state': 'NSW',
                'country': 'Australia',
                'marketing': False
            }

    async def initialize(self):
        """Initialize browser"""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        logger.info("Browser initialized")

    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def create_decision_node(self, page: Page, decision_type: str, description: str) -> DecisionNode:
        """Create a new decision node with analysis"""
        node_id = f"{decision_type}_{int(time.time())}"
        screenshot_path = f"screenshots/decision_{node_id}.png"
        
        await page.screenshot(path=screenshot_path)
        
        node = DecisionNode(
            node_id=node_id,
            page_url=page.url,
            screenshot_path=screenshot_path,
            decision_type=decision_type,
            description=description
        )
        
        # Analyze page and add options
        await self._analyze_page_and_add_options(page, node)
        
        return node

    async def _analyze_page_and_add_options(self, page: Page, node: DecisionNode):
        """Analyze page and populate decision options"""
        try:
            if node.decision_type == "entry_method_detection":
                await self._detect_entry_methods(page, node)
            elif node.decision_type == "form_analysis":
                await self._analyze_forms(page, node)
            elif node.decision_type == "navigation":
                await self._analyze_navigation_options(page, node)
            elif node.decision_type == "iframe_analysis":
                await self._analyze_iframes(page, node)
            elif node.decision_type == "social_media_actions":
                await self._analyze_social_media_actions(page, node)
            
            logger.info(f"Found {len(node.options)} options for {node.decision_type}")
            
            # Sort options by priority and confidence
            if node.options:
                node.options.sort(key=lambda x: (x.get('priority', 10), -x.get('confidence', 0)))
            
        except Exception as e:
            logger.error(f"Error analyzing page: {e}")

    async def _detect_entry_methods(self, page: Page, node: DecisionNode):
        """Detect possible entry methods on the page"""
        
        # Priority 1: AussieComps ps/ pattern (known working pattern)
        # Look for ps/ links and prioritize competition-specific ones
        ps_links = await page.query_selector_all('a[href*="ps/"]')
        
        # Separate generic and competition-specific links
        competition_specific_links = []
        generic_links = []
        
        for i, link in enumerate(ps_links):
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href:
                    # Check if this is a competition-specific link
                    # Generic links are usually ps/15595, competition-specific are higher numbers
                    ps_id = href.split('/')[-1]
                    if ps_id.isdigit():
                        ps_num = int(ps_id)
                        if ps_num > 15595:  # Competition-specific numbers are higher
                            competition_specific_links.append((link, href, text, i))
                        else:
                            generic_links.append((link, href, text, i))
                    else:
                        generic_links.append((link, href, text, i))
            except:
                pass
        
        # Add competition-specific links first (higher priority)
        for link, href, text, i in competition_specific_links:
            link_id = await link.get_attribute('id')
            link_class = await link.get_attribute('class')
            
            # Build a more specific selector
            if link_id:
                selector = f'a[id="{link_id}"]'
            elif link_class:
                selector = f'a[class="{link_class}"][href="{href}"]'
            else:
                selector = f'a[href="{href}"]'
            
            node.add_option({
                'type': 'aussiecomps_entry',
                'description': f'Competition-specific ps/ link: {href}',
                'selector': selector,
                'confidence': 0.98,  # Higher confidence for competition-specific
                'url': href,
                'priority': 1
            })
        
        # Add generic links as fallback (lower priority)
        for link, href, text, i in generic_links:
            link_id = await link.get_attribute('id')
            link_class = await link.get_attribute('class')
            
            # Build a more specific selector
            if link_id:
                selector = f'a[id="{link_id}"]'
            elif link_class:
                selector = f'a[class="{link_class}"][href="{href}"]'
            else:
                selector = f'a[href="{href}"]'
            
            node.add_option({
                'type': 'aussiecomps_entry',
                'description': f'Generic ps/ link: {href}',
                'selector': selector,
                'confidence': 0.85,  # Lower confidence for generic
                'url': href,
                'priority': 2
            })
        
        # Priority 2: Direct forms
        forms = await page.query_selector_all('form')
        for i, form in enumerate(forms):
            inputs = await form.query_selector_all('input, textarea, select')
            if inputs:
                node.add_option({
                    'type': 'direct_form',
                    'description': f'Direct form with {len(inputs)} fields',
                    'selector': f'form:nth-of-type({i+1})',
                    'confidence': 0.8,
                    'priority': 2
                })

        # Priority 3: External platform links
        platforms = ['gleam.io', 'woobox', 'rafflecopter', 'viralsweep', 'kingsumo', 'typeform']
        links = await page.query_selector_all('a[href]')
        
        for link in links:
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href and text:
                    for platform in platforms:
                        if platform in href.lower():
                            node.add_option({
                                'type': 'external_platform',
                                'description': f'{platform} entry: {text.strip()}',
                                'selector': f'a[href*="{platform}"]',
                                'confidence': 0.9,
                                'platform': platform,
                                'url': href,
                                'priority': 3
                            })
                            break
                    
                    # General entry links
                    entry_keywords = ['enter', 'join', 'participate', 'click here', 'visit site', 'enter now']
                    if any(keyword in text.lower() for keyword in entry_keywords):
                        if not any(skip in href.lower() for skip in ['facebook', 'twitter', 'instagram', 'mailto:']):
                            node.add_option({
                                'type': 'entry_link',
                                'description': f'Entry link: {text.strip()}',
                                'selector': f'a:has-text("{text.strip()}")',
                                'confidence': 0.6,
                                'url': href,
                                'priority': 4
                            })
                        
            except Exception as e:
                logger.debug(f"Error analyzing link: {e}")

        # Priority 4: Iframes (embedded competitions)
        iframes = await page.query_selector_all('iframe')
        for i, iframe in enumerate(iframes):
            try:
                src = await iframe.get_attribute('src')
                if src and any(platform in src.lower() for platform in ['viralsweep', 'gleam', 'woobox']):
                    node.add_option({
                        'type': 'iframe_competition',
                        'description': f'Embedded competition iframe {i+1}',
                        'selector': f'iframe:nth-of-type({i+1})',
                        'confidence': 0.85,
                        'src': src,
                        'priority': 3
                    })
            except:
                pass

    async def _analyze_forms(self, page: Page, node: DecisionNode):
        """Analyze forms on the page"""
        forms = await page.query_selector_all('form')
        
        for i, form in enumerate(forms):
            inputs = await form.query_selector_all('input, textarea, select')
            
            form_fields = []
            for input_elem in inputs:
                try:
                    name = await input_elem.get_attribute('name') or ''
                    placeholder = await input_elem.get_attribute('placeholder') or ''
                    input_type = await input_elem.get_attribute('type') or 'text'
                    
                    field_type = self._classify_field_type(name, placeholder, input_type)
                    
                    form_fields.append({
                        'name': name,
                        'placeholder': placeholder,
                        'type': field_type,
                        'input_type': input_type,
                        'selector': f'form:nth-of-type({i+1}) input[name="{name}"], form:nth-of-type({i+1}) textarea[name="{name}"], form:nth-of-type({i+1}) select[name="{name}"]'
                    })
                    
                except Exception as e:
                    logger.debug(f"Error analyzing input: {e}")
            
            if form_fields:
                node.add_option({
                    'type': 'fillable_form',
                    'description': f'Form {i+1} with {len(form_fields)} fields',
                    'fields': form_fields,
                    'confidence': 0.8
                })

    async def _analyze_navigation_options(self, page: Page, node: DecisionNode):
        """Analyze navigation options"""
        # Look for buttons with expanded keywords
        buttons = await page.query_selector_all('button, input[type="button"], input[type="submit"]')
        for button in buttons:
            try:
                text = await button.text_content()
                if text:
                    text_lower = text.lower().strip()
                    # Expanded keywords for different competition platforms
                    navigation_keywords = ['enter', 'start', 'begin', 'next', 'continue', 'join', 'giveaway', 'participate', 'register', 'submit']
                    
                    if any(keyword in text_lower for keyword in navigation_keywords):
                        # Higher confidence for specific competition keywords
                        confidence = 0.9 if any(keyword in text_lower for keyword in ['join', 'giveaway', 'enter']) else 0.7
                        
                        node.add_option({
                            'type': 'navigation_button',
                            'description': f'Button: {text.strip()}',
                            'selector': f'button:has-text("{text.strip()}")',
                            'confidence': confidence,
                            'action': 'click',
                            'priority': 1 if confidence > 0.8 else 2
                        })
            except:
                pass

        # Look for navigation links
        links = await page.query_selector_all('a[href]')
        for link in links:
            try:
                text = await link.text_content()
                href = await link.get_attribute('href')
                
                if text and href:
                    text_lower = text.lower().strip()
                    navigation_keywords = ['continue', 'next', 'proceed', 'enter', 'join', 'giveaway', 'participate']
                    
                    if any(keyword in text_lower for keyword in navigation_keywords):
                        confidence = 0.8 if any(keyword in text_lower for keyword in ['join', 'giveaway', 'enter']) else 0.6
                        
                        node.add_option({
                            'type': 'navigation_link',
                            'description': f'Link: {text.strip()}',
                            'selector': f'a:has-text("{text.strip()}")',
                            'confidence': confidence,
                            'action': 'navigate',
                            'url': href,
                            'priority': 1 if confidence > 0.7 else 2
                        })
            except:
                pass

    async def _analyze_iframes(self, page: Page, node: DecisionNode):
        """Analyze iframes for embedded competitions"""
        iframes = await page.query_selector_all('iframe')
        
        for i, iframe in enumerate(iframes):
            try:
                src = await iframe.get_attribute('src')
                if src:
                    # Try to access iframe content
                    iframe_content = await iframe.content_frame()
                    if iframe_content:
                        iframe_inputs = await iframe_content.query_selector_all('input, textarea, select')
                        
                        if iframe_inputs:
                            node.add_option({
                                'type': 'iframe_form',
                                'description': f'Iframe {i+1} with {len(iframe_inputs)} form fields',
                                'iframe_index': i,
                                'confidence': 0.8,
                                'src': src
                            })
                            
            except Exception as e:
                logger.debug(f"Error analyzing iframe {i}: {e}")

    async def _analyze_social_media_actions(self, page: Page, node: DecisionNode):
        """Analyze social media actions for platforms like Gleam.io"""
        try:
            # Look for Gleam.io specific action elements
            gleam_actions = await page.query_selector_all('.entry-method, .entry-action, [data-ng-click]')
            
            for i, action in enumerate(gleam_actions):
                try:
                    # Get action text
                    action_text = await action.text_content()
                    if action_text:
                        action_text = action_text.strip()
                        
                        # Check if it's a social media action
                        social_keywords = ['follow', 'like', 'share', 'tweet', 'instagram', 'facebook', 'twitter', 'visit']
                        
                        if any(keyword in action_text.lower() for keyword in social_keywords):
                            # Check if it's already completed
                            is_completed = await action.query_selector('.completed, .done, .success')
                            
                            if not is_completed:
                                node.add_option({
                                    'type': 'social_media_action',
                                    'description': f'Social action: {action_text}',
                                    'selector': f'.entry-method:nth-of-type({i+1}), .entry-action:nth-of-type({i+1})',
                                    'confidence': 0.8,
                                    'action': 'click',
                                    'priority': 1
                                })
                except Exception as e:
                    logger.debug(f"Error analyzing social action {i}: {e}")
            
            # Also look for general clickable elements with social keywords
            clickable_elements = await page.query_selector_all('button, a, [onclick], [data-click]')
            
            for element in clickable_elements:
                try:
                    text = await element.text_content()
                    if text:
                        text_lower = text.lower().strip()
                        social_keywords = ['follow', 'like', 'share', 'tweet', 'instagram', 'facebook', 'twitter', 'visit', 'subscribe']
                        
                        if any(keyword in text_lower for keyword in social_keywords):
                            # Check if it's not already processed
                            existing_descriptions = [opt['description'] for opt in node.options]
                            if not any(text.strip() in desc for desc in existing_descriptions):
                                node.add_option({
                                    'type': 'social_media_action',
                                    'description': f'Social action: {text.strip()}',
                                    'selector': f'button:has-text("{text.strip()}"), a:has-text("{text.strip()}")',
                                    'confidence': 0.7,
                                    'action': 'click',
                                    'priority': 2
                                })
                except Exception as e:
                    logger.debug(f"Error analyzing clickable element: {e}")
                    
        except Exception as e:
            logger.error(f"Error analyzing social media actions: {e}")

    def _classify_field_type(self, name: str, placeholder: str, input_type: str) -> str:
        """Classify form field type"""
        identifier = f"{name} {placeholder}".lower()
        
        if input_type == 'email' or 'email' in identifier:
            return 'email'
        elif 'first' in identifier or 'fname' in identifier:
            return 'first_name'
        elif 'last' in identifier or 'lname' in identifier:
            return 'last_name'
        elif 'name' in identifier and 'first' not in identifier and 'last' not in identifier:
            return 'first_name'
        elif 'phone' in identifier or 'mobile' in identifier or input_type == 'tel':
            return 'phone'
        elif 'zip' in identifier or 'postal' in identifier or 'postcode' in identifier:
            return 'postal_code'
        elif 'address' in identifier:
            return 'address'
        elif 'city' in identifier:
            return 'city'
        elif 'state' in identifier:
            return 'state'
        elif input_type == 'checkbox':
            if 'terms' in identifier or 'agree' in identifier:
                return 'terms'
            elif 'marketing' in identifier or 'newsletter' in identifier:
                return 'marketing'
            else:
                return 'checkbox'
        else:
            return 'text'

    async def execute_decision(self, page: Page, node: DecisionNode, option_index: int = None) -> bool:
        """Execute a decision option"""
        if not node.options:
            logger.warning("No options available")
            return False
        
        # Choose option by priority if not specified
        if option_index is None:
            # Sort by priority (lower number = higher priority) then by confidence
            sorted_options = sorted(enumerate(node.options), 
                                  key=lambda x: (x[1].get('priority', 99), -x[1].get('confidence', 0)))
            option_index = sorted_options[0][0]
        
        if not node.choose_option(option_index):
            logger.error(f"Invalid option index: {option_index}")
            return False

        option = node.chosen_option
        logger.info(f"Executing: {option['description']}")

        try:
            option_type = option['type']
            
            if option_type == 'aussiecomps_entry':
                return await self._handle_aussiecomps_entry(page, option)
            elif option_type == 'direct_form':
                return await self._fill_direct_form(page, option)
            elif option_type == 'external_platform':
                return await self._handle_external_platform(page, option)
            elif option_type == 'entry_link':
                return await self._click_entry_link(page, option)
            elif option_type == 'iframe_competition':
                return await self._handle_iframe_competition(page, option)
            elif option_type == 'fillable_form':
                return await self._fill_form_fields(page, option['fields'])
            elif option_type == 'navigation_button' or option_type == 'navigation_link':
                return await self._handle_navigation(page, option)
            elif option_type == 'iframe_form':
                return await self._handle_iframe_form(page, option)
            elif option_type == 'social_media_action':
                return await self._handle_social_media_action(page, option)
            else:
                logger.warning(f"Unknown option type: {option_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing decision: {e}")
            node.mark_failure(str(e))
            return False

    async def _handle_aussiecomps_entry(self, page: Page, option: Dict) -> bool:
        """Handle AussieComps ps/ entry link"""
        try:
            selector = option['selector']
            element = await page.query_selector(selector)
            
            if element:
                await element.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                logger.info("Clicked AussieComps ps/ link")
                return True
                
        except Exception as e:
            logger.error(f"Error handling AussieComps entry: {e}")
        
        return False

    async def _fill_direct_form(self, page: Page, option: Dict) -> bool:
        """Fill a direct form on the page"""
        try:
            selector = option['selector']
            form = await page.query_selector(selector)
            
            if not form:
                return False
            
            inputs = await form.query_selector_all('input, textarea, select')
            filled_count = 0
            
            for input_elem in inputs:
                try:
                    name = await input_elem.get_attribute('name') or ''
                    placeholder = await input_elem.get_attribute('placeholder') or ''
                    input_type = await input_elem.get_attribute('type') or 'text'
                    
                    field_type = self._classify_field_type(name, placeholder, input_type)
                    value = self._get_field_value(field_type)
                    
                    if value is not None:
                        if input_type == 'checkbox':
                            if value and not await input_elem.is_checked():
                                await input_elem.click()
                        else:
                            await input_elem.fill(str(value))
                        
                        filled_count += 1
                        logger.info(f"Filled {field_type}: {value}")
                        
                except Exception as e:
                    logger.debug(f"Error filling field: {e}")
            
            logger.info(f"Filled {filled_count} fields in direct form")
            return filled_count > 0
            
        except Exception as e:
            logger.error(f"Error filling direct form: {e}")
            return False

    async def _handle_external_platform(self, page: Page, option: Dict) -> bool:
        """Handle external competition platform"""
        try:
            selector = option['selector']
            element = await page.query_selector(selector)
            
            if element:
                await element.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                logger.info(f"Navigated to external platform: {option.get('platform', 'unknown')}")
                return True
                
        except Exception as e:
            logger.error(f"Error handling external platform: {e}")
        
        return False

    async def _click_entry_link(self, page: Page, option: Dict) -> bool:
        """Click an entry link"""
        try:
            selector = option['selector']
            element = await page.query_selector(selector)
            
            if element:
                await element.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                logger.info("Clicked entry link")
                return True
                
        except Exception as e:
            logger.error(f"Error clicking entry link: {e}")
        
        return False

    async def _handle_iframe_competition(self, page: Page, option: Dict) -> bool:
        """Handle iframe-based competition"""
        try:
            selector = option['selector']
            iframe = await page.query_selector(selector)
            
            if iframe:
                iframe_content = await iframe.content_frame()
                if iframe_content:
                    return await self._fill_iframe_content(iframe_content)
                    
        except Exception as e:
            logger.error(f"Error handling iframe competition: {e}")
        
        return False

    async def _fill_form_fields(self, page: Page, fields: List[Dict]) -> bool:
        """Fill identified form fields"""
        filled_count = 0
        
        for field in fields:
            try:
                selector = field['selector']
                field_type = field['type']
                value = self._get_field_value(field_type)
                
                if value is not None:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        if field['input_type'] == 'checkbox':
                            if value and not await element.is_checked():
                                await element.click()
                        else:
                            await element.fill(str(value))
                        
                        filled_count += 1
                        logger.info(f"Filled {field_type}: {value}")
                    
            except Exception as e:
                logger.debug(f"Error filling field: {e}")
        
        logger.info(f"Filled {filled_count} out of {len(fields)} fields")
        return filled_count > 0

    async def _handle_navigation(self, page: Page, option: Dict) -> bool:
        """Handle navigation action"""
        try:
            if option['action'] == 'click':
                selector = option['selector']
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    return True
            elif option['action'] == 'navigate':
                url = option['url']
                if not url.startswith('http'):
                    url = urljoin(page.url, url)
                await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=15000)
                return True
                
        except Exception as e:
            logger.error(f"Error in navigation: {e}")
        
        return False

    async def _handle_iframe_form(self, page: Page, option: Dict) -> bool:
        """Handle form inside iframe"""
        try:
            iframe_index = option['iframe_index']
            iframes = await page.query_selector_all('iframe')
            
            if iframe_index < len(iframes):
                iframe = iframes[iframe_index]
                iframe_content = await iframe.content_frame()
                
                if iframe_content:
                    return await self._fill_iframe_content(iframe_content)
                    
        except Exception as e:
            logger.error(f"Error handling iframe form: {e}")
        
        return False

    async def _fill_iframe_content(self, iframe_content) -> bool:
        """Fill content inside an iframe"""
        try:
            inputs = await iframe_content.query_selector_all('input, textarea, select')
            filled_count = 0
            
            for input_elem in inputs:
                try:
                    if not await input_elem.is_visible():
                        continue
                        
                    name = await input_elem.get_attribute('name') or ''
                    placeholder = await input_elem.get_attribute('placeholder') or ''
                    input_type = await input_elem.get_attribute('type') or 'text'
                    
                    field_type = self._classify_field_type(name, placeholder, input_type)
                    value = self._get_field_value(field_type)
                    
                    if value is not None:
                        if input_type == 'checkbox':
                            if value and not await input_elem.is_checked():
                                await input_elem.click()
                        else:
                            await input_elem.fill(str(value))
                        
                        filled_count += 1
                        logger.info(f"Filled iframe field {field_type}: {value}")
                        
                except Exception as e:
                    logger.debug(f"Error filling iframe input: {e}")
            
            return filled_count > 0
            
        except Exception as e:
            logger.error(f"Error filling iframe content: {e}")
            return False

    async def _handle_social_media_action(self, page: Page, option: Dict) -> bool:
        """Handle social media actions like follow, like, share"""
        try:
            selector = option['selector']
            element = await page.query_selector(selector)
            
            if element:
                logger.info(f"Executing social media action: {option['description']}")
                
                # Click the action element
                await element.click()
                await asyncio.sleep(2)  # Wait for action to register
                
                # Check if action opened a new tab/window
                if len(page.context.pages) > 1:
                    logger.info("Social media action opened new tab - handling external navigation")
                    
                    # Get the new page
                    new_page = page.context.pages[-1]
                    await new_page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # Close the new tab after a moment (social media actions usually just need to be opened)
                    await asyncio.sleep(3)
                    await new_page.close()
                    
                    # Return to original page
                    await page.bring_to_front()
                
                # Check if the action is now marked as completed
                await asyncio.sleep(1)
                completed_element = await page.query_selector(f"{selector}.completed, {selector}.done, {selector}.success")
                
                if completed_element:
                    logger.info("Social media action completed successfully")
                    return True
                else:
                    logger.info("Social media action executed (completion status unclear)")
                    return True  # Consider it successful if we could click it
                    
            else:
                logger.warning(f"Could not find element for social media action: {selector}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling social media action: {e}")
            return False

    def _get_field_value(self, field_type: str) -> Any:
        """Get value for a field type"""
        mapping = {
            'email': self.personal_info.get('email'),
            'first_name': self.personal_info.get('first_name'),
            'last_name': self.personal_info.get('last_name'),
            'phone': self.personal_info.get('phone'),
            'postal_code': self.personal_info.get('postal_code'),
            'address': self.personal_info.get('address'),
            'city': self.personal_info.get('city'),
            'state': self.personal_info.get('state'),
            'country': self.personal_info.get('country'),
            'terms': True,
            'marketing': self.personal_info.get('marketing', False),
            'checkbox': False
        }
        return mapping.get(field_type)

    async def process_competition_adaptively(self, competition_url: str, title: str = "", max_depth: int = 5) -> bool:
        """Process a competition using adaptive decision tree approach"""
        logger.info(f"Processing competition adaptively: {title or competition_url}")
        
        try:
            page = await self.context.new_page()
            await page.goto(competition_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Create root decision node
            root_node = await self.create_decision_node(page, "entry_method_detection", f"Initial analysis")
            
            # Start adaptive processing with backtracking
            success = await self._recursive_decision_process(page, root_node, 0, max_depth)
            
            if success:
                logger.info(f"✅ Successfully processed: {title}")
            else:
                logger.warning(f"❌ Failed to process: {title}")
            
            # Save decision tree
            await self._save_decision_tree(root_node, title)
            
            await page.close()
            return success
            
        except Exception as e:
            logger.error(f"Error in adaptive processing: {e}")
            return False

    async def _recursive_decision_process(self, page: Page, node: DecisionNode, depth: int, max_depth: int) -> bool:
        """Recursive decision-making process with backtracking"""
        if depth >= max_depth:
            logger.warning(f"Maximum depth {max_depth} reached")
            return False
        
        logger.info(f"Decision depth {depth}: {node.decision_type}")
        
        if not node.options:
            logger.warning("No decision options available")
            return False
        
        # Try each option in order of priority/confidence
        for option_index in range(len(node.options)):
            logger.info(f"Trying option {option_index}: {node.options[option_index]['description']}")
            
            # Execute the decision
            success = await self.execute_decision(page, node, option_index)
            
            if success:
                node.mark_success()
                
                # Wait for page to settle
                await asyncio.sleep(2)
                
                # Check if we've completed the entry process
                if await self._is_entry_complete(page):
                    logger.info("✅ Entry process completed successfully!")
                    return True
                
                # Determine next decision type
                next_decision_type = await self._determine_next_decision(page, node)
                
                if next_decision_type:
                    # Create next decision node
                    next_node = await self.create_decision_node(page, next_decision_type, f"Following {node.decision_type}")
                    node.add_child(next_node)
                    
                    # Continue recursively
                    if await self._recursive_decision_process(page, next_node, depth + 1, max_depth):
                        return True
                else:
                    # No next step determined, check if we're on a platform that needs manual completion
                    current_url = page.url.lower()
                    if any(platform in current_url for platform in ['gleam.io', 'cubot.net', 'coinxchange']):
                        # On external platform - consider this successful navigation
                        logger.info("✅ Successfully navigated to external competition platform")
                        return True
                    else:
                        # No next step determined, might be complete
                        logger.info("No next step determined, checking for completion")
                        return await self._is_entry_complete(page)
                
            else:
                logger.warning(f"Option {option_index} failed, trying next option")
                node.mark_failure(f"Option {option_index} execution failed")
        
        # All options failed
        logger.warning(f"All options failed at depth {depth}")
        return False

    async def _is_entry_complete(self, page: Page) -> bool:
        """Check if the entry process is complete"""
        try:
            current_url = page.url
            page_text = await page.text_content('body')
            title = await page.title()
            
            success_indicators = [
                'thank you', 'thanks', 'entered', 'submission received',
                'success', 'confirmed', 'complete', 'registered', 'entry recorded',
                'good luck', 'congratulations'
            ]
            
            page_text_lower = page_text.lower()
            url_lower = current_url.lower()
            title_lower = title.lower()
            
            # Check for success indicators in text, URL, or title
            has_success_indicator = False
            for indicator in success_indicators:
                if (indicator in page_text_lower or 
                    indicator in url_lower or 
                    indicator in title_lower):
                    logger.info(f"Success indicator found: {indicator}")
                    has_success_indicator = True
                    break
            
            # If we're on a competition platform, check if there are forms that need filling
            platform_domains = ['gleam.io', 'woobox.com', 'rafflecopter.com', 'viralsweep.com', 'kingsumo.com']
            
            if any(domain in url_lower for domain in platform_domains):
                # We're on a competition platform
                forms = await page.query_selector_all('form')
                visible_inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
                
                logger.info(f"On competition platform: {current_url}")
                logger.info(f"Found {len(forms)} forms and {len(visible_inputs)} visible inputs")
                
                # On competition platforms, prioritize form filling over success indicators
                # unless we have very specific completion indicators
                specific_completion_indicators = [
                    'entry complete', 'entry confirmed', 'entry successful', 'entry recorded',
                    'you have entered', 'congratulations', 'well done', 'you\'re in'
                ]
                
                has_specific_completion = any(indicator in page_text_lower for indicator in specific_completion_indicators)
                
                if forms and visible_inputs and not has_specific_completion:
                    logger.info("Competition platform with forms detected - forms need to be filled first")
                    return False  # There are forms to fill
                
                if has_specific_completion:
                    logger.info("Specific completion indicator found on competition platform")
                    return True
            
            # Check if we're on a brand/direct competition site with forms
            competition_keywords = ['competition', 'giveaway', 'contest', 'sweepstakes', 'win', 'prize']
            if any(keyword in page_text_lower for keyword in competition_keywords):
                forms = await page.query_selector_all('form')
                visible_inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
                
                if forms and visible_inputs and not has_success_indicator:
                    logger.info("Direct competition site with unfilled forms - entry NOT complete")
                    return False
            
            # If we have success indicators, entry is complete
            if has_success_indicator:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking entry completion: {e}")
            return False

    async def _determine_next_decision(self, page: Page, current_node: DecisionNode) -> Optional[str]:
        """Determine what decision to make next"""
        try:
            current_url = page.url.lower()
            
            # Check if we're on a known competition platform
            platform_domains = ['gleam.io', 'woobox.com', 'rafflecopter.com', 'viralsweep.com', 'kingsumo.com', 'cubot.net', 'coinxchange.com.au']
            
            if any(domain in current_url for domain in platform_domains):
                logger.info(f"Detected competition platform: {page.url}")
                
                # Check depth to avoid infinite loops on social media platforms
                if current_node.decision_type == "social_media_actions" and len(current_node.children) >= 2:
                    logger.info("Already processed social media actions multiple times, considering entry complete")
                    return None
                
                # Special handling for different platform types
                if 'gleam.io' in current_url:
                    # Gleam.io typically has social media actions, not traditional forms
                    # Only analyze social media actions if we haven't done it extensively
                    if current_node.decision_type != "social_media_actions":
                        action_elements = await page.query_selector_all('.entry-method, .entry-action, button[data-ng-click]')
                        if action_elements:
                            logger.info("Found Gleam.io action elements - analyzing social media actions")
                            return "social_media_actions"
                    
                    # If we've already done social media actions, check for forms
                    forms = await page.query_selector_all('form')
                    inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
                    if forms and inputs:
                        logger.info("Found forms on Gleam.io - analyzing")
                        return "form_analysis"
                
                elif 'cubot.net' in current_url:
                    # Cubot typically has a "Join Giveaway" button
                    join_buttons = await page.query_selector_all('button, a')
                    for button in join_buttons:
                        text = await button.text_content()
                        if text and any(keyword in text.lower() for keyword in ['join', 'giveaway', 'enter']):
                            logger.info("Found join/giveaway button - analyzing navigation")
                            return "navigation"
                
                elif 'coinxchange.com.au' in current_url:
                    # Coinxchange might have forms or navigation
                    forms = await page.query_selector_all('form')
                    if forms:
                        logger.info("Found forms on coinxchange - analyzing")
                        return "form_analysis"
                
                # Always analyze forms on competition platforms if present
                forms = await page.query_selector_all('form')
                inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
                
                if forms and inputs:
                    logger.info("Found forms on competition platform - analyzing")
                    return "form_analysis"
            
            # Check for forms on any site
            forms = await page.query_selector_all('form')
            inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
            
            if forms and inputs:
                logger.info("Found forms - analyzing")
                return "form_analysis"
            
            # Check for iframes
            iframes = await page.query_selector_all('iframe')
            if iframes:
                logger.info("Found iframes - analyzing")
                return "iframe_analysis"
            
            # Check for navigation options (expanded search)
            buttons = await page.query_selector_all('button, input[type="button"], input[type="submit"]')
            nav_links = await page.query_selector_all('a')
            
            if buttons or nav_links:
                # Look for entry-related navigation with expanded keywords
                entry_keywords = ['enter', 'start', 'begin', 'next', 'continue', 'join', 'giveaway', 'participate', 'register', 'submit']
                
                for button in buttons:
                    text = await button.text_content()
                    if text and any(keyword in text.lower() for keyword in entry_keywords):
                        logger.info(f"Found navigation button: '{text.strip()}' - analyzing")
                        return "navigation"
                
                for link in nav_links:
                    text = await link.text_content()
                    if text and any(keyword in text.lower() for keyword in entry_keywords):
                        logger.info(f"Found navigation link: '{text.strip()}' - analyzing")
                        return "navigation"
            
            logger.info("No further decisions needed")
            return None
            
        except Exception as e:
            logger.error(f"Error determining next decision: {e}")
            return None

    async def _save_decision_tree(self, root_node: DecisionNode, title: str):
        """Save decision tree for learning"""
        try:
            tree_data = self._serialize_node(root_node)
            filename = f"decision_trees/{title.replace(' ', '_')[:30]}_{int(time.time())}.json"
            
            with open(filename, 'w') as f:
                json.dump(tree_data, f, indent=2, default=str)
            
            logger.info(f"Decision tree saved: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving decision tree: {e}")

    def _serialize_node(self, node: DecisionNode) -> Dict:
        """Serialize decision node to dict"""
        return {
            'node_id': node.node_id,
            'page_url': node.page_url,
            'screenshot_path': node.screenshot_path,
            'decision_type': node.decision_type,
            'description': node.description,
            'options': [self._serialize_option(opt) for opt in node.options],
            'chosen_option': self._serialize_option(node.chosen_option) if node.chosen_option else None,
            'success': node.success,
            'error_message': node.error_message,
            'timestamp': node.timestamp,
            'retry_count': node.retry_count,
            'children': [self._serialize_node(child) for child in node.children]
        }

    def _serialize_option(self, option: Dict) -> Dict:
        """Serialize option to dict (remove non-serializable elements)"""
        if not option:
            return None
        
        serializable_option = {}
        for key, value in option.items():
            if key not in ['element', 'target']:  # Skip non-serializable elements
                serializable_option[key] = value
        
        return serializable_option

    async def discover_competitions(self, aggregator_url: str) -> List[Dict]:
        """Discover competitions from aggregator site"""
        logger.info(f"Discovering competitions from: {aggregator_url}")
        
        try:
            page = await self.context.new_page()
            await page.goto(aggregator_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            
            competitions = []
            
            # Look for competition links using various patterns
            selectors = [
                'a:has-text("Win")',  # AussieComps main pattern
                'a[href*="/index.php?id="]',  # AussieComps URL pattern
                'a[href*="/ps/"]',  # AussieComps ps/ pattern
                'a[href*="/competition/"]',
                'a[href*="/comp/"]', 
                'a[href*="enter"]',
                'a[href*="win"]',
                '.competition-link a',
                '.comp-link a'
            ]
            
            for selector in selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        
                        if href and text and self._is_valid_competition_link(text, href):
                            if not href.startswith('http'):
                                href = urljoin(aggregator_url, href)
                            
                            competitions.append({
                                'url': href,
                                'title': text.strip(),
                                'source': aggregator_url,
                                'discovery_method': selector
                            })
                            
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # Remove duplicates
            seen_urls = set()
            unique_competitions = []
            for comp in competitions:
                if comp['url'] not in seen_urls:
                    seen_urls.add(comp['url'])
                    unique_competitions.append(comp)
            
            await page.close()
            
            logger.info(f"Discovered {len(unique_competitions)} competitions")
            return unique_competitions[:10]  # Limit to first 10
            
        except Exception as e:
            logger.error(f"Error discovering competitions: {e}")
            return []

    def _is_valid_competition_link(self, text: str, href: str) -> bool:
        """Validate if this is a legitimate competition link"""
        text_lower = text.lower()
        href_lower = href.lower()
        
        # Skip unwanted links
        if any(skip in href_lower for skip in ['mailto:', 'tel:', 'javascript:', 'facebook', 'twitter', 'instagram']):
            return False
        
        if any(nav in text_lower for nav in ['home', 'about', 'contact', 'faq', 'terms', 'privacy', 'login']):
            return False
        
        # Check for competition keywords
        competition_keywords = ['win', 'giveaway', 'contest', 'competition', 'prize', 'enter', 'chance']
        if any(keyword in text_lower for keyword in competition_keywords):
            return True
        
        # Check for competition URL patterns
        if any(pattern in href_lower for pattern in ['comp', 'contest', 'giveaway', 'ps/', 'id=']):
            return True
        
        return False

async def main():
    """Main function to run the adaptive competition entry system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Adaptive Competition Auto-Entry System')
    parser.add_argument('--aggregator-url', default='https://www.aussiecomps.com/', help='Competition aggregator URL')
    parser.add_argument('--max-competitions', type=int, default=3, help='Maximum competitions to process')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--max-depth', type=int, default=5, help='Maximum decision tree depth')
    
    args = parser.parse_args()
    
    system = AdaptiveCompetitionEntry(headless=args.headless)
    
    try:
        await system.initialize()
        
        # Discover competitions
        competitions = await system.discover_competitions(args.aggregator_url)
        
        if not competitions:
            logger.warning("No competitions discovered")
            return
        
        # Process competitions adaptively
        successful_entries = 0
        
        for i, competition in enumerate(competitions[:args.max_competitions], 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing competition {i}/{min(len(competitions), args.max_competitions)}")
            logger.info(f"Title: {competition['title']}")
            logger.info(f"URL: {competition['url']}")
            logger.info(f"{'='*60}")
            
            success = await system.process_competition_adaptively(
                competition['url'], 
                competition['title'], 
                args.max_depth
            )
            
            if success:
                successful_entries += 1
            
            # Brief pause between competitions
            await asyncio.sleep(3)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"FINAL SUMMARY: {successful_entries}/{min(len(competitions), args.max_competitions)} competitions processed successfully")
        logger.info(f"Success Rate: {successful_entries/min(len(competitions), args.max_competitions)*100:.1f}%")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await system.close()

if __name__ == "__main__":
    asyncio.run(main())
