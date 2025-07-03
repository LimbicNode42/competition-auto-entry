#!/usr/bin/env python3
"""
Adaptive Competition Entry System
Main orchestrator for dynamic competition entry with backtracking and symbolic decision trees
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import time
from enum import Enum

# Import our adaptive entry system
from adaptive_competition_entry import AdaptiveCompetitionEntry, CompetitionEntry, CompetitionStatus, DecisionNode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompetitionStatus(Enum):
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    ENTRY_FOUND = "entry_found"
    FORM_DETECTED = "form_detected"
    FILLED = "filled"
    SUBMITTED = "submitted"
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"

class DecisionNode:
    """Symbolic decision node for backtracking and learning"""
    def __init__(self, node_id: str, page_url: str, screenshot_path: str, 
                 decision_type: str, context: str):
        self.node_id = node_id
        self.page_url = page_url
        self.screenshot_path = screenshot_path
        self.decision_type = decision_type
        self.context = context
        self.options = []
        self.chosen_option = None
        self.children = []
        self.parent = None
        self.success = None
        self.error_message = None
        self.timestamp = datetime.now()
        self.ai_analysis = {}
        self.retry_count = 0

    def add_option(self, option: Dict):
        """Add a possible decision option"""
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
        """Mark this decision as successful"""
        self.success = True

    def mark_failure(self, error: str):
        """Mark this decision as failed"""
        self.success = False
        self.error_message = error

    def get_path_to_root(self) -> List['DecisionNode']:
        """Get the decision path from root to this node"""
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
        
        return [opt for opt in self.options if opt != self.chosen_option]

@dataclass
class CompetitionEntry:
    """Represents a competition with adaptive tracking"""
    url: str
    title: str
    status: CompetitionStatus = CompetitionStatus.DISCOVERED
    decision_tree: Optional[DecisionNode] = None
    screenshots: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

class AdaptiveCompetitionSystem:
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
        self.ai_client = None
        self.decision_history = []
        
        # Ensure directories exist
        Path("screenshots").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("decision_trees").mkdir(exist_ok=True)
        
        self._load_config()
        self._initialize_ai()

    def _load_config(self):
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.personal_info = config.get('personal_info', {})
                logger.info(f"Configuration loaded")
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

    def _initialize_ai(self):
        """Initialize AI client if available"""
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.ai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            logger.info("OpenAI client initialized")
        else:
            logger.info("Running without AI assistance (using heuristics)")

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

    async def create_decision_node(self, page: Page, decision_type: str, context: str) -> DecisionNode:
        """Create a new decision node with analysis"""
        node_id = f"{decision_type}_{int(time.time())}"
        screenshot_path = f"screenshots/decision_{node_id}.png"
        
        await page.screenshot(path=screenshot_path)
        
        node = DecisionNode(
            node_id=node_id,
            page_url=page.url,
            screenshot_path=screenshot_path,
            decision_type=decision_type,
            context=context
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
            
        except Exception as e:
            logger.error(f"Error analyzing page: {e}")

    async def _detect_entry_methods(self, page: Page, node: DecisionNode):
        """Detect possible entry methods on the page"""
        
        # First check for AussieComps ps/ pattern (specific to this site)
        ps_links = await page.query_selector_all('a[href*="ps/"]')
        for link in ps_links:
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href:
                    node.add_option({
                        'type': 'aussiecomps_entry',
                        'description': f'AussieComps entry link: {text.strip() if text else href}',
                        'selector': f'a[href*="ps/"]',
                        'confidence': 0.95,
                        'url': href
                    })
            except:
                pass
        
        # Check for direct forms
        forms = await page.query_selector_all('form')
        if forms:
            for i, form in enumerate(forms):
                inputs = await form.query_selector_all('input, textarea, select')
                if inputs:
                    node.add_option({
                        'type': 'direct_form',
                        'description': f'Fill form {i+1} with {len(inputs)} fields',
                        'selector': f'form:nth-of-type({i+1})',
                        'confidence': 0.8,
                        'target': form
                    })

        # Check for external platform links
        links = await page.query_selector_all('a')
        for link in links:
            try:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href and text:
                    # Check for competition platforms
                    platforms = ['gleam.io', 'woobox', 'rafflecopter', 'viralsweep', 'kingsumo']
                    for platform in platforms:
                        if platform in href.lower():
                            node.add_option({
                                'type': 'external_platform',
                                'description': f'External entry via {platform}: {text.strip()}',
                                'selector': f'a[href*="{platform}"]',
                                'confidence': 0.9,
                                'platform': platform,
                                'url': href
                            })
                            break
                    
                    # Check for entry-related text
                    entry_keywords = ['enter', 'join', 'participate', 'click here', 'visit site', 'enter now', 'enter competition']
                    if any(keyword in text.lower() for keyword in entry_keywords):
                        # Skip if it's a social media or unwanted link
                        if not any(skip in href.lower() for skip in ['facebook', 'twitter', 'instagram', 'mailto:', 'javascript:']):
                            node.add_option({
                                'type': 'entry_link',
                                'description': f'Entry link: {text.strip()}',
                                'selector': f'a:has-text("{text.strip()}")',
                                'confidence': 0.6,
                                'url': href
                            })
                        
            except Exception as e:
                logger.debug(f"Error analyzing link: {e}")

        # Check for iframes (embedded competitions)
        iframes = await page.query_selector_all('iframe')
        if iframes:
            for i, iframe in enumerate(iframes):
                src = await iframe.get_attribute('src')
                if src and any(platform in src.lower() for platform in ['viralsweep', 'gleam', 'woobox']):
                    node.add_option({
                        'type': 'iframe_competition',
                        'description': f'Embedded competition in iframe {i+1}',
                        'selector': f'iframe:nth-of-type({i+1})',
                        'confidence': 0.85,
                        'src': src
                    })
        
        logger.info(f"Found {len(node.options)} entry method options")

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
                        'element': input_elem
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
        # Look for buttons and links that might lead to entry forms
        buttons = await page.query_selector_all('button')
        for button in buttons:
            try:
                text = await button.text_content()
                if text and any(keyword in text.lower() for keyword in ['enter', 'start', 'begin', 'next']):
                    node.add_option({
                        'type': 'navigation_button',
                        'description': f'Click button: {text.strip()}',
                        'selector': f'button:has-text("{text.strip()}")',
                        'confidence': 0.7,
                        'action': 'click'
                    })
            except:
                pass

        # Look for navigation links
        links = await page.query_selector_all('a')
        for link in links:
            try:
                text = await link.text_content()
                href = await link.get_attribute('href')
                
                if text and href and any(keyword in text.lower() for keyword in ['continue', 'next', 'proceed']):
                    node.add_option({
                        'type': 'navigation_link',
                        'description': f'Navigate: {text.strip()}',
                        'selector': f'a:has-text("{text.strip()}")',
                        'confidence': 0.6,
                        'action': 'navigate',
                        'url': href
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
                        iframe_forms = await iframe_content.query_selector_all('form')
                        iframe_inputs = await iframe_content.query_selector_all('input, textarea, select')
                        
                        if iframe_forms or iframe_inputs:
                            node.add_option({
                                'type': 'iframe_form',
                                'description': f'Iframe {i+1} with {len(iframe_inputs)} form fields',
                                'iframe_index': i,
                                'confidence': 0.8,
                                'src': src
                            })
                            
            except Exception as e:
                logger.debug(f"Error analyzing iframe {i}: {e}")

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
        elif 'phone' in identifier or 'mobile' in identifier:
            return 'phone'
        elif input_type == 'tel':
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

    async def execute_decision(self, page: Page, node: DecisionNode, option_index: int = 0) -> bool:
        """Execute a decision option"""
        if not node.choose_option(option_index):
            logger.error(f"Invalid option index: {option_index}")
            return False

        option = node.chosen_option
        logger.info(f"Executing: {option['description']}")

        try:
            if option['type'] == 'direct_form':
                return await self._fill_direct_form(page, option)
            elif option['type'] == 'external_platform':
                return await self._handle_external_platform(page, option)
            elif option['type'] == 'entry_link':
                return await self._click_entry_link(page, option)
            elif option['type'] == 'iframe_competition':
                return await self._handle_iframe_competition(page, option)
            elif option['type'] == 'fillable_form':
                return await self._fill_form_fields(page, option['fields'])
            elif option['type'] == 'navigation_button' or option['type'] == 'navigation_link':
                return await self._handle_navigation(page, option)
            elif option['type'] == 'iframe_form':
                return await self._handle_iframe_form(page, option)
            else:
                logger.warning(f"Unknown option type: {option['type']}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing decision: {e}")
            node.mark_failure(str(e))
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
                await page.wait_for_load_state('networkidle', timeout=10000)
                logger.info(f"Navigated to external platform: {option['platform']}")
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
                await page.wait_for_load_state('networkidle', timeout=10000)
                logger.info(f"Clicked entry link")
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
                    # Look for forms in the iframe
                    iframe_inputs = await iframe_content.query_selector_all('input, textarea, select')
                    
                    filled_count = 0
                    for input_elem in iframe_inputs:
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
                            logger.debug(f"Error filling iframe field: {e}")
                    
                    logger.info(f"Filled {filled_count} fields in iframe")
                    return filled_count > 0
                    
        except Exception as e:
            logger.error(f"Error handling iframe competition: {e}")
        
        return False

    async def _fill_form_fields(self, page: Page, fields: List[Dict]) -> bool:
        """Fill identified form fields"""
        filled_count = 0
        
        for field in fields:
            try:
                element = field['element']
                field_type = field['type']
                value = self._get_field_value(field_type)
                
                if value is not None and await element.is_visible():
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
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    return True
            elif option['action'] == 'navigate':
                url = option['url']
                if not url.startswith('http'):
                    url = urljoin(page.url, url)
                await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=10000)
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

    async def process_competition_adaptively(self, competition: CompetitionEntry, max_depth: int = 5) -> bool:
        """Process a competition using adaptive decision tree approach"""
        logger.info(f"Processing competition adaptively: {competition.title}")
        
        try:
            page = await self.context.new_page()
            await page.goto(competition.url)
            await page.wait_for_load_state('domcontentloaded')
            
            # Create root decision node
            root_node = await self.create_decision_node(page, "entry_method_detection", f"Initial analysis of {competition.title}")
            competition.decision_tree = root_node
            
            # Start adaptive processing
            success = await self._recursive_decision_process(page, competition, root_node, 0, max_depth)
            
            if success:
                competition.status = CompetitionStatus.SUCCESS
                logger.info(f"✅ Successfully processed: {competition.title}")
            else:
                competition.status = CompetitionStatus.FAILED
                logger.warning(f"❌ Failed to process: {competition.title}")
            
            # Save decision tree
            await self._save_decision_tree(competition)
            
            await page.close()
            return success
            
        except Exception as e:
            logger.error(f"Error in adaptive processing: {e}")
            competition.status = CompetitionStatus.FAILED
            return False

    async def _recursive_decision_process(self, page: Page, competition: CompetitionEntry, 
                                        node: DecisionNode, depth: int, max_depth: int) -> bool:
        """Recursive decision-making process with backtracking"""
        if depth >= max_depth:
            logger.warning(f"Maximum depth {max_depth} reached")
            return False
        
        logger.info(f"Decision depth {depth}: {node.decision_type}")
        
        if not node.options:
            logger.warning("No decision options available")
            return False
        
        # Try each option in order of confidence
        sorted_options = sorted(enumerate(node.options), key=lambda x: x[1].get('confidence', 0), reverse=True)
        
        for option_index, option in sorted_options:
            logger.info(f"Trying option {option_index}: {option['description']}")
            
            # Execute the decision
            success = await self.execute_decision(page, node, option_index)
            
            if success:
                node.mark_success()
                
                # Check if we've completed the entry process
                if await self._is_entry_complete(page):
                    logger.info("Entry process completed successfully!")
                    return True
                
                # Determine next decision type
                next_decision_type = await self._determine_next_decision(page, node)
                
                if next_decision_type:
                    # Create next decision node
                    next_node = await self.create_decision_node(page, next_decision_type, f"Following {node.decision_type}")
                    node.add_child(next_node)
                    
                    # Continue recursively
                    if await self._recursive_decision_process(page, competition, next_node, depth + 1, max_depth):
                        return True
                
            else:
                logger.warning(f"Option {option_index} failed, trying next option")
                node.mark_failure(f"Option {option_index} execution failed")
        
        # All options failed
        logger.warning(f"All options failed at depth {depth}")
        return False

    async def _is_entry_complete(self, page: Page) -> bool:
        """Check if the entry process is complete"""
        try:
            page_text = await page.text_content('body')
            success_indicators = [
                'thank you', 'thanks', 'entered', 'submission received',
                'success', 'confirmed', 'complete', 'registered', 'entry recorded'
            ]
            
            return any(indicator in page_text.lower() for indicator in success_indicators)
            
        except:
            return False

    async def _determine_next_decision(self, page: Page, current_node: DecisionNode) -> Optional[str]:
        """Determine what decision to make next"""
        try:
            # Check for forms
            forms = await page.query_selector_all('form')
            inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
            
            if forms and inputs:
                return "form_analysis"
            
            # Check for iframes
            iframes = await page.query_selector_all('iframe')
            if iframes:
                return "iframe_analysis"
            
            # Check for navigation options
            buttons = await page.query_selector_all('button')
            nav_links = await page.query_selector_all('a')
            
            if buttons or nav_links:
                return "navigation"
            
            return None
            
        except:
            return None

    async def _save_decision_tree(self, competition: CompetitionEntry):
        """Save decision tree for learning"""
        if not competition.decision_tree:
            return
        
        try:
            tree_data = self._serialize_node(competition.decision_tree)
            filename = f"decision_trees/{competition.title.replace(' ', '_')[:30]}_{int(time.time())}.json"
            
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
            'context': node.context,
            'options': [self._serialize_option(opt) for opt in node.options],
            'chosen_option': self._serialize_option(node.chosen_option) if node.chosen_option else None,
            'success': node.success,
            'error_message': node.error_message,
            'timestamp': node.timestamp,
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

    async def discover_competitions(self, aggregator_url: str) -> List[CompetitionEntry]:
        """Discover competitions from aggregator site"""
        logger.info(f"Discovering competitions from: {aggregator_url}")
        
        try:
            page = await self.context.new_page()
            await page.goto(aggregator_url)
            await page.wait_for_load_state('domcontentloaded')
            
            competitions = []
            
            # Look for competition links
            links = await page.query_selector_all('a')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    
                    if href and text and self._is_competition_link(text, href):
                        if not href.startswith('http'):
                            href = urljoin(aggregator_url, href)
                        
                        competitions.append(CompetitionEntry(
                            url=href,
                            title=text.strip()
                        ))
                        
                except:
                    continue
            
            await page.close()
            
            logger.info(f"Discovered {len(competitions)} competitions")
            return competitions
            
        except Exception as e:
            logger.error(f"Error discovering competitions: {e}")
            return []

    def _is_competition_link(self, text: str, href: str) -> bool:
        """Heuristic to identify competition links"""
        text_lower = text.lower()
        href_lower = href.lower()
        
        # Skip email links
        if href_lower.startswith('mailto:'):
            return False
        
        # Skip navigation links
        if any(nav in text_lower for nav in ['home', 'about', 'contact', 'faq', 'terms', 'privacy']):
            return False
        
        # Check for competition keywords in text
        competition_keywords = ['win', 'giveaway', 'contest', 'competition', 'prize', 'enter', 'chance to win']
        if any(keyword in text_lower for keyword in competition_keywords):
            return True
        
        # Check for competition patterns in URL
        if any(pattern in href_lower for pattern in ['comp', 'contest', 'giveaway', 'ps/', 'id=']):
            return True
        
        return False

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Adaptive Competition Auto-Entry System')
    parser.add_argument('--aggregator-url', default='https://www.aussiecomps.com/', help='Competition aggregator URL')
    parser.add_argument('--max-competitions', type=int, default=3, help='Maximum competitions to process')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--max-depth', type=int, default=5, help='Maximum decision tree depth')
    
    args = parser.parse_args()
    
    system = AdaptiveCompetitionSystem(headless=args.headless)
    
    try:
        await system.initialize()
        
        # Discover competitions
        competitions = await system.discover_competitions(args.aggregator_url)
        
        if not competitions:
            logger.warning("No competitions discovered")
            return
        
        # Process competitions
        successful_entries = 0
        
        for i, competition in enumerate(competitions[:args.max_competitions], 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing competition {i}/{min(len(competitions), args.max_competitions)}")
            logger.info(f"Title: {competition.title}")
            logger.info(f"URL: {competition.url}")
            logger.info(f"{'='*60}")
            
            success = await system.process_competition_adaptively(competition, args.max_depth)
            
            if success:
                successful_entries += 1
            
            # Brief pause between competitions
            await asyncio.sleep(2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY: {successful_entries}/{min(len(competitions), args.max_competitions)} competitions processed successfully")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await system.close()

if __name__ == "__main__":
    asyncio.run(main())
