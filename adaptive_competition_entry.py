#!/usr/bin/env python3
"""
Adaptive Competition Auto-Entry System
Uses Computer Vision + LLM/MCP to dynamically handle any competition format
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from enum import Enum
import base64

# Playwright for browser automation
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# AI/LLM integration
try:
    import openai
    from anthropic import Anthropic
    OPENAI_AVAILABLE = True
    ANTHROPIC_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    ANTHROPIC_AVAILABLE = False

# Computer Vision
try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False

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
    """Represents a decision point in the competition entry process"""
    def __init__(self, node_id: str, page_url: str, screenshot_path: str, 
                 decision_type: str, options: List[Dict], chosen_option: Optional[Dict] = None):
        self.node_id = node_id
        self.page_url = page_url
        self.screenshot_path = screenshot_path
        self.decision_type = decision_type  # 'entry_method', 'form_field', 'navigation', etc.
        self.options = options
        self.chosen_option = chosen_option
        self.timestamp = datetime.now()
        self.children = []
        self.parent = None
        self.success = None
        self.error_message = None

    def add_child(self, child_node: 'DecisionNode'):
        """Add a child decision node"""
        child_node.parent = self
        self.children.append(child_node)

    def mark_success(self):
        """Mark this decision as successful"""
        self.success = True

    def mark_failure(self, error_message: str):
        """Mark this decision as failed"""
        self.success = False
        self.error_message = error_message

    def get_path_to_root(self) -> List['DecisionNode']:
        """Get the path from this node back to the root"""
        path = []
        current = self
        while current:
            path.append(current)
            current = current.parent
        return path[::-1]

@dataclass
class CompetitionEntry:
    """Represents a competition with adaptive entry tracking"""
    url: str
    title: str
    status: CompetitionStatus = CompetitionStatus.DISCOVERED
    decision_tree: Optional[DecisionNode] = None
    entry_methods: List[Dict] = field(default_factory=list)
    form_fields: List[Dict] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    ai_analysis: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

class AdaptiveCompetitionEntry:
    """
    Adaptive competition entry system using CV + LLM/MCP
    Can dynamically adapt to any competition format
    """
    
    def __init__(self, config_path: str = "config/config.json", headless: bool = True):
        self.config_path = config_path
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.personal_info = {}
        self.ai_client = None
        self.decision_history = []
        
        # Load configuration
        self._load_config()
        
        # Initialize AI client
        self._initialize_ai()
        
        # Ensure directories exist
        Path("screenshots").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("decision_trees").mkdir(exist_ok=True)

    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.personal_info = config.get('personal_info', {})
                logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            # Use default personal info
            self.personal_info = {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone': '+1234567890',
                'postal_code': '12345',
                'address': '123 Main St',
                'city': 'Sydney',
                'state': 'NSW',
                'country': 'Australia',
                'marketing': False
            }

    def _initialize_ai(self):
        """Initialize AI client for decision making"""
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.ai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            logger.info("OpenAI client initialized")
        elif ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.ai_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            logger.info("Anthropic client initialized")
        else:
            logger.warning("No AI client available. Running without AI assistance.")

    async def initialize(self):
        """Initialize the browser and context"""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        logger.info("Browser initialized successfully")

    async def close(self):
        """Close the browser and clean up"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def analyze_page_with_ai(self, page: Page, context: str, decision_type: str) -> Dict:
        """Use AI to analyze a page and make decisions"""
        if not self.ai_client:
            logger.warning("No AI client available for analysis")
            return {"error": "No AI client available"}

        try:
            # Take screenshot
            screenshot_path = f"screenshots/ai_analysis_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            
            # Get page content
            page_content = await page.content()
            page_text = await page.text_content('body')
            page_title = await page.title()
            current_url = page.url
            
            # Encode screenshot for AI
            with open(screenshot_path, 'rb') as f:
                screenshot_b64 = base64.b64encode(f.read()).decode()
            
            # Construct prompt based on decision type
            if decision_type == "entry_method_detection":
                prompt = f"""
                Analyze this competition webpage and identify all possible entry methods.
                
                Page URL: {current_url}
                Page Title: {page_title}
                Context: {context}
                
                Look for:
                1. Direct entry forms on this page
                2. Links to external competition platforms (Gleam, Woobox, RaffleCoter, etc.)
                3. Social media entry requirements
                4. Email entry methods
                5. Download/upload requirements
                6. Multi-step entry processes
                
                Return a JSON response with:
                {{
                    "entry_methods": [
                        {{
                            "type": "direct_form|external_link|social_media|email|download|multi_step",
                            "description": "Brief description of entry method",
                            "selector": "CSS selector or XPath to interact with",
                            "confidence": 0.0-1.0,
                            "requires_external_site": true/false,
                            "platform": "platform name if applicable"
                        }}
                    ],
                    "recommended_method": "index of recommended method",
                    "complexity": "simple|medium|complex",
                    "requires_human": true/false
                }}
                """
            
            elif decision_type == "form_field_analysis":
                prompt = f"""
                Analyze this page for form fields that need to be filled for competition entry.
                
                Page URL: {current_url}
                Page Title: {page_title}
                Context: {context}
                
                Identify:
                1. All visible form fields
                2. Hidden form fields that might become visible
                3. Required vs optional fields
                4. Field types (text, email, phone, etc.)
                5. Validation requirements
                6. Submit buttons
                
                Return a JSON response with:
                {{
                    "form_fields": [
                        {{
                            "type": "text|email|phone|checkbox|select|textarea",
                            "name": "field name or identifier",
                            "label": "visible label text",
                            "required": true/false,
                            "selector": "CSS selector",
                            "placeholder": "placeholder text if any",
                            "validation": "any validation requirements"
                        }}
                    ],
                    "submit_button": {{
                        "text": "button text",
                        "selector": "CSS selector"
                    }},
                    "form_complexity": "simple|medium|complex",
                    "estimated_success_rate": 0.0-1.0
                }}
                """
            
            elif decision_type == "navigation_decision":
                prompt = f"""
                Analyze this page to determine the best navigation path for competition entry.
                
                Page URL: {current_url}
                Page Title: {page_title}
                Context: {context}
                
                Determine:
                1. What actions are needed to proceed with entry
                2. Which links/buttons to click
                3. Whether to stay on this page or navigate elsewhere
                4. Any prerequisites or requirements
                
                Return a JSON response with:
                {{
                    "navigation_options": [
                        {{
                            "action": "click|navigate|fill_form|wait|scroll",
                            "target": "CSS selector or URL",
                            "description": "What this action does",
                            "confidence": 0.0-1.0,
                            "expected_result": "What should happen after this action"
                        }}
                    ],
                    "recommended_action": "index of recommended action",
                    "risk_level": "low|medium|high",
                    "requires_human": true/false
                }}
                """
            
            # Call AI API
            if hasattr(self.ai_client, 'chat'):  # OpenAI
                response = self.ai_client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                            ]
                        }
                    ],
                    max_tokens=2000
                )
                ai_response = response.choices[0].message.content
            else:  # Anthropic
                response = self.ai_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}}
                            ]
                        }
                    ]
                )
                ai_response = response.content[0].text
            
            # Parse AI response
            try:
                ai_analysis = json.loads(ai_response)
                ai_analysis["screenshot_path"] = screenshot_path
                return ai_analysis
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response: {ai_response}")
                return {"error": "Failed to parse AI response", "raw_response": ai_response}
                
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {"error": str(e)}

    async def create_decision_node(self, page: Page, decision_type: str, context: str) -> DecisionNode:
        """Create a new decision node with AI analysis"""
        node_id = f"{decision_type}_{int(time.time())}"
        screenshot_path = f"screenshots/decision_{node_id}.png"
        await page.screenshot(path=screenshot_path)
        
        # Get AI analysis
        ai_analysis = await self.analyze_page_with_ai(page, context, decision_type)
        
        # Extract options from AI analysis
        options = []
        if decision_type == "entry_method_detection" and "entry_methods" in ai_analysis:
            options = ai_analysis["entry_methods"]
        elif decision_type == "navigation_decision" and "navigation_options" in ai_analysis:
            options = ai_analysis["navigation_options"]
        elif decision_type == "form_field_analysis" and "form_fields" in ai_analysis:
            options = ai_analysis["form_fields"]
        
        node = DecisionNode(
            node_id=node_id,
            page_url=page.url,
            screenshot_path=screenshot_path,
            decision_type=decision_type,
            options=options
        )
        
        # Store AI analysis in node
        node.ai_analysis = ai_analysis
        
        return node

    async def execute_decision(self, page: Page, decision_node: DecisionNode) -> bool:
        """Execute the decision made by AI"""
        try:
            if not decision_node.options:
                logger.warning("No options available for decision")
                return False
            
            # Choose the best option (highest confidence or recommended)
            best_option = None
            
            if decision_node.decision_type == "entry_method_detection":
                # Use recommended method or highest confidence
                if "recommended_method" in decision_node.ai_analysis:
                    recommended_idx = decision_node.ai_analysis["recommended_method"]
                    if isinstance(recommended_idx, int) and 0 <= recommended_idx < len(decision_node.options):
                        best_option = decision_node.options[recommended_idx]
                
                if not best_option:
                    best_option = max(decision_node.options, key=lambda x: x.get('confidence', 0))
            
            elif decision_node.decision_type == "navigation_decision":
                # Use recommended action or highest confidence
                if "recommended_action" in decision_node.ai_analysis:
                    recommended_idx = decision_node.ai_analysis["recommended_action"]
                    if isinstance(recommended_idx, int) and 0 <= recommended_idx < len(decision_node.options):
                        best_option = decision_node.options[recommended_idx]
                
                if not best_option:
                    best_option = max(decision_node.options, key=lambda x: x.get('confidence', 0))
            
            elif decision_node.decision_type == "form_field_analysis":
                # For form fields, we'll handle them differently
                return await self._fill_form_fields(page, decision_node.options)
            
            if not best_option:
                logger.error("No valid option found")
                return False
            
            decision_node.chosen_option = best_option
            
            # Execute the chosen option
            if best_option.get('action') == 'click':
                selector = best_option.get('selector') or best_option.get('target')
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        logger.info(f"Clicked element: {selector}")
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        return True
            
            elif best_option.get('action') == 'navigate':
                url = best_option.get('target')
                if url:
                    await page.goto(url)
                    logger.info(f"Navigated to: {url}")
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    return True
            
            elif best_option.get('type') == 'external_link':
                selector = best_option.get('selector')
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        logger.info(f"Clicked external link: {selector}")
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        return True
            
            # Add more action types as needed
            logger.warning(f"Unknown action type: {best_option}")
            return False
            
        except Exception as e:
            logger.error(f"Error executing decision: {e}")
            decision_node.mark_failure(str(e))
            return False

    async def _fill_form_fields(self, page: Page, form_fields: List[Dict]) -> bool:
        """Fill form fields identified by AI"""
        filled_count = 0
        
        for field in form_fields:
            try:
                field_type = field.get('type', 'text')
                selector = field.get('selector', '')
                field_name = field.get('name', '')
                
                if not selector:
                    continue
                
                # Get the value to fill based on field type
                value = self._get_field_value(field_type, field_name, field.get('label', ''))
                
                if value is None:
                    continue
                
                # Find the element
                element = await page.query_selector(selector)
                if not element:
                    continue
                
                # Fill based on field type
                if field_type == 'checkbox':
                    if value and not await element.is_checked():
                        await element.click()
                    elif not value and await element.is_checked():
                        await element.click()
                elif field_type == 'select':
                    await element.select_option(value=str(value))
                else:
                    await element.fill(str(value))
                
                logger.info(f"Filled field {field_name} ({field_type}) with: {value}")
                filled_count += 1
                
            except Exception as e:
                logger.error(f"Error filling field {field.get('name', '')}: {e}")
        
        logger.info(f"Filled {filled_count} out of {len(form_fields)} fields")
        return filled_count > 0

    def _get_field_value(self, field_type: str, field_name: str, label: str) -> Any:
        """Get the appropriate value for a form field"""
        field_identifier = f"{field_name} {label}".lower()
        
        if field_type == 'email' or 'email' in field_identifier:
            return self.personal_info.get('email')
        elif field_type == 'phone' or any(keyword in field_identifier for keyword in ['phone', 'mobile', 'tel']):
            return self.personal_info.get('phone')
        elif 'first' in field_identifier:
            return self.personal_info.get('first_name')
        elif 'last' in field_identifier:
            return self.personal_info.get('last_name')
        elif 'name' in field_identifier:
            return self.personal_info.get('first_name')
        elif 'address' in field_identifier:
            return self.personal_info.get('address')
        elif 'city' in field_identifier:
            return self.personal_info.get('city')
        elif 'state' in field_identifier:
            return self.personal_info.get('state')
        elif any(keyword in field_identifier for keyword in ['zip', 'postal', 'postcode']):
            return self.personal_info.get('postal_code')
        elif 'country' in field_identifier:
            return self.personal_info.get('country')
        elif field_type == 'checkbox':
            if any(keyword in field_identifier for keyword in ['terms', 'conditions', 'agree']):
                return True
            elif any(keyword in field_identifier for keyword in ['marketing', 'newsletter']):
                return self.personal_info.get('marketing', False)
            else:
                return False
        else:
            return None

    async def backtrack_decision_tree(self, failed_node: DecisionNode) -> Optional[DecisionNode]:
        """Backtrack through the decision tree to find alternative paths"""
        logger.info(f"Backtracking from failed node: {failed_node.node_id}")
        
        # Get path to root
        path = failed_node.get_path_to_root()
        
        # Try to find alternative options in parent nodes
        for node in reversed(path):
            if len(node.options) > 1:
                # Find unused options
                unused_options = [opt for opt in node.options if opt != node.chosen_option]
                
                if unused_options:
                    # Choose the next best option
                    best_unused = max(unused_options, key=lambda x: x.get('confidence', 0))
                    
                    logger.info(f"Found alternative option in node {node.node_id}: {best_unused.get('description', '')}")
                    
                    # Create a new branch
                    node.chosen_option = best_unused
                    return node
        
        logger.warning("No alternative paths found in decision tree")
        return None

    async def save_decision_tree(self, competition: CompetitionEntry):
        """Save the decision tree for analysis and learning"""
        if not competition.decision_tree:
            return
        
        tree_data = self._serialize_decision_tree(competition.decision_tree)
        
        filename = f"decision_trees/{competition.title.replace(' ', '_')[:50]}_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(tree_data, f, indent=2, default=str)
        
        logger.info(f"Decision tree saved: {filename}")

    def _serialize_decision_tree(self, node: DecisionNode) -> Dict:
        """Serialize a decision tree node to JSON"""
        return {
            'node_id': node.node_id,
            'page_url': node.page_url,
            'screenshot_path': node.screenshot_path,
            'decision_type': node.decision_type,
            'options': node.options,
            'chosen_option': node.chosen_option,
            'success': node.success,
            'error_message': node.error_message,
            'timestamp': node.timestamp,
            'ai_analysis': getattr(node, 'ai_analysis', {}),
            'children': [self._serialize_decision_tree(child) for child in node.children]
        }

# ... (continued in next file)
