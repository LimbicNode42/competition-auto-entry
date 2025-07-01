"""
Web scraping functionality for competition discovery and entry.
"""

import asyncio
import time
import random
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import logging

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from fake_useragent import UserAgent

from ..utils.config import AppConfig
from ..utils.helpers import (
    is_valid_url, normalize_url, extract_domain, clean_text,
    is_free_competition, generate_delay
)
from ..utils.rejection_logger import RejectionLogger
from ..integrations.google_auth import GoogleAuthHandler
from .competition import Competition, CompetitionForm, FormField
from .form_detector import FormDetector

logger = logging.getLogger("competition_auto_entry.scraper")


class CompetitionScraper:
    """Handles web scraping for competition discovery and entry."""
    
    def __init__(self, config: AppConfig):
        """
        Initialize the scraper with configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.user_agent = UserAgent()
        self.form_detector = FormDetector()
        self.session: Optional[aiohttp.ClientSession] = None
        self.driver: Optional[webdriver.Chrome] = None
        
        # Initialize rejection logger (clear on each run for fresh feedback)
        rejection_log_path = getattr(config, 'rejection_log_path', 'data/rejection_log.json')
        self.rejection_logger = RejectionLogger(rejection_log_path, clear_on_init=True)
        
        # Google auth handler (initialized when driver is created)
        self.google_auth = None
        
        # Sites that require authentication
        self.auth_required_sites = {
            'competitions.com.au': 'competition_level',  # Login required for individual competitions
            'competitioncloud.com.au': 'site_level'      # Login required for site access
        }
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup()
    
    async def _init_session(self) -> None:
        """Initialize HTTP session."""
        headers = {
            'User-Agent': self.config.scraping.user_agent or self.user_agent.random
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.scraping.timeout)
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        )
        logger.info("HTTP session initialized")
    
    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
        
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _get_webdriver(self) -> webdriver.Chrome:
        """
        Get a configured Chrome WebDriver instance.
        
        Returns:
            Chrome WebDriver instance
        """
        if self.driver:
            return self.driver
        
        options = Options()
        
        if self.config.scraping.headless:
            options.add_argument('--headless')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f'--user-agent={self.config.scraping.user_agent}')
        
        # Additional privacy options
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Initialize Google auth handler
            self.google_auth = GoogleAuthHandler(self.config, self.driver)
            
            logger.info("Chrome WebDriver initialized")
            return self.driver
        except Exception as e:
            logger.error(f"Error initializing WebDriver: {e}")
            raise
    
    async def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a web page and return BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup object or None if failed
        """
        if not self.session:
            await self._init_session()
        
        try:
            await asyncio.sleep(generate_delay(
                self.config.scraping.delay_min,
                self.config.scraping.delay_max
            ))
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return BeautifulSoup(content, 'html.parser')
                else:
                    logger.warning(f"HTTP {response.status} for URL: {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def discover_competitions_from_page(
        self, 
        url: str, 
        source_name: str,
        use_pagination: bool = True
    ) -> List[Competition]:
        """
        Discover competitions from a single aggregator page.
        
        Args:
            url: Aggregator page URL
            source_name: Name of the source website
            use_pagination: Whether to use pagination and load more handling
            
        Returns:
            List of discovered competitions
        """
        logger.info(f"Discovering competitions from: {url}")
        
        # Check if authentication is required and handle it
        auth_type = self._requires_authentication(url)
        auth_success = await self._ensure_authenticated(url)
        if not auth_success:
            logger.error(f"Authentication failed for {url}, skipping")
            return []
        
        # Use pagination handling for comprehensive discovery
        if use_pagination:
            return await self._handle_pagination_and_load_more(url, source_name)
        else:
            # For sites requiring site-level auth, use Selenium
            # For competition-level auth sites, use aiohttp for aggregator pages
            if auth_type == 'site_level':
                return await self._discover_competitions_with_selenium(url, source_name)
            else:
                return await self._discover_competitions_with_aiohttp(url, source_name)
    
    async def _discover_competitions_with_aiohttp(self, url: str, source_name: str) -> List[Competition]:
        """Discover competitions using aiohttp (for sites not requiring auth)."""
        soup = await self.fetch_page(url)
        if not soup:
            return []
        
        return await self._process_competition_links(url, source_name, soup)
    
    async def _discover_competitions_with_selenium(self, url: str, source_name: str) -> List[Competition]:
        """Discover competitions using Selenium (for sites requiring auth)."""
        try:
            if not self.driver:
                self._get_webdriver()
            
            logger.debug(f"Using Selenium to fetch {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            return await self._process_competition_links(url, source_name, soup)
            
        except Exception as e:
            logger.error(f"Error fetching {url} with Selenium: {e}")
            return []
    
    async def _process_competition_links(self, url: str, source_name: str, soup) -> List[Competition]:
        """Process competition links from a parsed page."""
        competitions = []
        
        # Site-specific selectors for better accuracy
        if 'competitions.com.au' in url:
            # Updated selectors based on actual site structure
            link_selectors = [
                '.competition a',  # Main competition container
                'a[href*="/exit/"]',  # Direct competition links
                'a[href*="/win"]',  # Win-based URLs
                'a[href*="/prize"]',  # Prize-based URLs
                '.comp-item a', '.competition-link a', '.listing-item a'
            ]
        elif 'competitioncloud.com.au' in url:
            # Special handling for Competition Cloud - need to follow category links
            return await self._process_competition_cloud_links(url, source_name, soup)
        elif 'aussiecomps.com' in url:
            # Specific selectors for AussieComps - uses table structure with /index.php?id= pattern
            link_selectors = [
                'a[href*="/index.php?id="]',  # Main competition links pattern
                'table tr td a[href*="id="]',  # Competition links in table cells
                'a[href*="/ps/"]',  # Promotional/sponsored links
                'tr td:nth-child(2) a'  # Competition title links (2nd column in table)
            ]
        else:
            # Generic fallback selectors
            link_selectors = [
                '.competition a',  # Common container
                'a[href*="/exit/"]',  # Common pattern for competition exits
                'a[href*="/entry/"]',  # Entry links
                'a[href*="/enter/"]',  # Enter links
                'a[href*="competition"]',
                'a[href*="contest"]',
                'a[href*="giveaway"]',
                'a[href*="win"]',
                '.competition-link a',
                '.contest-link a',
                '.giveaway-link a'
            ]
        
        competition_links = set()
        
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = normalize_url(href, url)
                    if is_valid_url(full_url):
                        # Additional filtering for obvious non-competitions
                        if not any(skip in full_url.lower() for skip in [
                            'mailto:', 'tel:', 'javascript:', '#',
                            '/terms', '/privacy', '/contact', '/about',
                            '/faq', '/help', '/login', '/register',
                            '.pdf', '.jpg', '.png', '.gif', '.css', '.js'
                        ]):
                            # Additional check for competition-like URLs
                            if any(indicator in full_url.lower() for indicator in [
                                '/exit/', '/entry/', '/enter/', '/win', '/prize',
                                '/competition', '/contest', '/giveaway', '/comp/',
                                '/c/', '/ps/'  # promotional/sponsored
                            ]) or any(indicator in link.get_text().lower() for indicator in [
                                'win', 'prize', 'competition', 'contest', 'enter', 'giveaway'
                            ]):
                                competition_links.add(full_url)
        
        logger.info(f"Found {len(competition_links)} potential competition links")
        
        # Process each competition link (increased limit for pagination)
        for comp_url in list(competition_links)[:100]:  # Increased from 20 to 100
            try:
                competition = await self._analyze_competition_page(comp_url, source_name)
                if competition:
                    competitions.append(competition)
                    
            except Exception as e:
                logger.error(f"Error analyzing competition {comp_url}: {e}")
                continue
        
        logger.info(f"Successfully discovered {len(competitions)} competitions from {source_name}")
        return competitions
    
    async def _process_competition_cloud_links(self, url: str, source_name: str, soup) -> List[Competition]:
        """
        Process Competition Cloud links by extracting competition items directly from the loaded page.
        
        Args:
            url: Competition Cloud main page URL
            source_name: Name of the source
            soup: BeautifulSoup object of the main page (after Show More clicks)
            
        Returns:
            List of discovered competitions
        """
        competitions = []
        
        # Competition Cloud uses d-item class for individual competition containers
        competition_items = soup.select('.d-item')
        logger.info(f"Found {len(competition_items)} competition items on Competition Cloud")
        
        for item in competition_items:
            try:
                # Extract competition details from the item container
                title_elem = item.find('h4') or item.find('h3') or item.find('.title')
                if not title_elem:
                    # Look for any text that might be a title
                    text_content = item.get_text().strip()
                    if text_content and len(text_content) > 10:
                        # Use first meaningful line as title
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        if lines and not lines[0].lower().startswith('end:'):
                            title = lines[0][:100]  # First line as title, truncated
                        else:
                            title = lines[1] if len(lines) > 1 else "Competition"
                    else:
                        continue
                else:
                    title = clean_text(title_elem.get_text())
                
                if not title or len(title) < 5:
                    continue
                
                # Competition Cloud uses onclick handlers instead of href
                # Look for visitsite() JavaScript calls
                visit_links = item.find_all('a', onclick=True)
                competition_url = None
                
                for link in visit_links:
                    onclick = link.get('onclick', '')
                    # Extract parameters from visitsite('guid', id) calls
                    if 'visitsite(' in onclick:
                        import re
                        match = re.search(r"visitsite\('([^']+)',\s*(\d+)\)", onclick)
                        if match:
                            guid = match.group(1)
                            comp_id = match.group(2)
                            # Construct the Competition Cloud redirect URL
                            competition_url = f"https://competitioncloud.com.au/visitsite/{guid}/{comp_id}"
                            break
                
                if not competition_url:
                    logger.debug(f"No valid competition URL found for: {title}")
                    continue
                
                # Extract description from the item text
                item_text = item.get_text()
                description_lines = [line.strip() for line in item_text.split('\n') if line.strip()]
                description = ""
                
                # Look for description text (skip title, "End:", "Premium", and "Visit" lines)
                for line in description_lines:
                    if (line != title and 
                        not line.lower().startswith('end:') and 
                        not line.lower().startswith('visit') and
                        line.lower() != 'premium' and
                        len(line) > 10):  # Meaningful description line
                        description = line[:200]  # Limit length
                        break
                
                # Extract deadline if present
                deadline = None
                deadline_text = ""
                for line in description_lines:
                    if line.lower().startswith('end:'):
                        deadline_text = line
                        break
                
                if deadline_text:
                    import re
                    # Try to extract date from "End: Friday, 31 October 2025" format
                    date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', deadline_text)
                    if date_match:
                        try:
                            from datetime import datetime
                            day, month_name, year = date_match.groups()
                            # Convert month name to number
                            month_names = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            month_num = month_names.get(month_name.lower())
                            if month_num:
                                deadline = datetime(int(year), month_num, int(day))
                        except:
                            pass
                
                # Create competition object
                competition = Competition(
                    url=competition_url,
                    title=title,
                    source=source_name,
                    description=description,
                    deadline=deadline,
                    terms_url="",
                    entry_url=competition_url
                )
                
                competitions.append(competition)
                logger.debug(f"Found Competition Cloud competition: {title}")
                
            except Exception as e:
                logger.error(f"Error processing Competition Cloud item: {e}")
                continue
        
        logger.info(f"Successfully discovered {len(competitions)} competitions from Competition Cloud")
        return competitions
    
    async def _analyze_competition_page(self, url: str, source: str) -> Optional[Competition]:
        """
        Analyze a competition page to extract details.
        
        Args:
            url: Competition page URL
            source: Source website name
            
        Returns:
            Competition object or None if not valid
        """
        soup = await self.fetch_page(url)
        if not soup:
            return None
        
        # Skip obvious non-competition pages
        non_competition_indicators = [
            '/blog/', '/terms', '/privacy', '/contact', '/about',
            '/add-a-competition', '/promote', '/advertise', '/register'
        ]
        
        if any(indicator in url.lower() for indicator in non_competition_indicators):
            logger.debug(f"Skipping non-competition page: {url}")
            return None
        
        # Extract title
        title_selectors = ['h1', 'h2', '.title', '.competition-title', 'title']
        title = ""
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = clean_text(element.get_text())
                break
        
        if not title:
            logger.warning(f"No title found for competition: {url}")
            return None
        
        # Skip titles that don't look like competitions
        non_competition_titles = [
            'register', 'sign up', 'login', 'blog', 'how to', 'about',
            'contact', 'terms', 'privacy', 'add a competition', 'promote'
        ]
        
        title_lower = title.lower()
        if any(indicator in title_lower for indicator in non_competition_titles):
            # Exception: titles with "free" in them might be legitimate
            if 'free' not in title_lower and 'win' not in title_lower:
                logger.debug(f"Skipping non-competition title: {title}")
                return None
        
        # Extract description
        description_selectors = [
            '.description', '.competition-description', '.content',
            'p', '.summary', '.competition-details'
        ]
        description = ""
        for selector in description_selectors:
            element = soup.select_one(selector)
            if element:
                description = clean_text(element.get_text())[:500]  # Limit length
                break
        
        # Check if competition is free
        page_text = soup.get_text()
        terms_text = ""
        terms_link = soup.select_one('a[href*="terms"], a[href*="condition"]')
        if terms_link:
            terms_url = normalize_url(terms_link.get('href'), url)
            terms_soup = await self.fetch_page(terms_url)
            if terms_soup:
                terms_text = terms_soup.get_text()
        
        is_free, detection_reason = is_free_competition(page_text.lower(), terms_text.lower())
        logger.debug(f"Free competition check for '{title}': {is_free} - {detection_reason}")
        
        if not is_free:
            logger.info(f"Competition appears to require payment: {title}")
            logger.debug(f"Detection reason: {detection_reason}")
            
            # Log the rejection for review
            self.rejection_logger.log_paid_detection_rejection(
                url=url,
                title=title,
                detection_reason=detection_reason,
                page_text=page_text,
                terms_text=terms_text,
                source=source
            )
            
            return None
        
        # Extract deadline
        deadline = None
        deadline_patterns = [
            r'deadline.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'closes.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'ends.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]
        
        import re
        for pattern in deadline_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                from ..utils.helpers import parse_deadline
                deadline = parse_deadline(match.group(1))
                break
        
        # Find entry form URL
        entry_url = url  # Default to the current page
        entry_link = soup.select_one('a[href*="enter"], button[onclick*="enter"]')
        if entry_link and entry_link.get('href'):
            entry_url = normalize_url(entry_link.get('href'), url)
        
        competition = Competition(
            url=url,
            title=title,
            source=source,
            description=description,
            deadline=deadline,
            terms_url=terms_link.get('href') if terms_link else "",
            entry_url=entry_url
        )
        
        logger.debug(f"Analyzed competition: {title}")
        return competition
    
    async def enter_competition(self, competition: Competition) -> bool:
        """
        Attempt to enter a competition automatically.
        
        Args:
            competition: Competition to enter
            
        Returns:
            True if entry was successful, False otherwise
        """
        logger.info(f"Attempting to enter competition: {competition.title}")
        
        try:
            # First, try to find and analyze the entry form
            form = await self._detect_entry_form(competition.entry_url)
            if not form:
                logger.warning(f"No entry form found for: {competition.title}")
                return False
            
            # Use Selenium for form interaction
            driver = self._get_webdriver()
            driver.get(competition.entry_url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Fill the form
            success = await self._fill_and_submit_form(driver, form)
            
            if success:
                logger.info(f"Successfully entered competition: {competition.title}")
                return True
            else:
                logger.warning(f"Failed to enter competition: {competition.title}")
                return False
                
        except Exception as e:
            logger.error(f"Error entering competition {competition.title}: {e}")
            return False
    
    async def _detect_entry_form(self, url: str) -> Optional[CompetitionForm]:
        """
        Detect and analyze entry form on a competition page.
        
        Args:
            url: URL of the competition entry page
            
        Returns:
            CompetitionForm object or None if no form found
        """
        soup = await self.fetch_page(url)
        if not soup:
            return None
        
        return self.form_detector.detect_form(soup, url)
    
    async def _fill_and_submit_form(
        self, 
        driver: webdriver.Chrome, 
        form: CompetitionForm
    ) -> bool:
        """
        Fill and submit a competition entry form.
        
        Args:
            driver: Selenium WebDriver instance
            form: CompetitionForm object with form details
            
        Returns:
            True if form was submitted successfully, False otherwise
        """
        try:
            # Fill form fields
            for field in form.fields:
                try:
                    element = None
                    
                    # Try to find element by different methods
                    if field.css_selector:
                        element = driver.find_element(By.CSS_SELECTOR, field.css_selector)
                    elif field.xpath:
                        element = driver.find_element(By.XPATH, field.xpath)
                    elif field.name:
                        element = driver.find_element(By.NAME, field.name)
                    
                    if not element:
                        logger.warning(f"Could not find form field: {field.name}")
                        continue
                    
                    # Get the value to fill
                    value = self._get_field_value(field)
                    if not value:
                        continue
                    
                    # Fill based on field type
                    if field.field_type in ['text', 'email', 'tel']:
                        element.clear()
                        element.send_keys(value)
                    elif field.field_type == 'select':
                        select = Select(element)
                        select.select_by_visible_text(value)
                    elif field.field_type == 'checkbox' and field.required:
                        if not element.is_selected():
                            element.click()
                    elif field.field_type == 'radio':
                        element.click()
                    
                    logger.debug(f"Filled field {field.name} with value: {value}")
                    
                except Exception as e:
                    logger.warning(f"Error filling field {field.name}: {e}")
                    continue
            
            # Accept terms and conditions if present
            if form.terms_checkbox_selector:
                try:
                    terms_checkbox = driver.find_element(By.CSS_SELECTOR, form.terms_checkbox_selector)
                    if not terms_checkbox.is_selected():
                        terms_checkbox.click()
                        logger.debug("Accepted terms and conditions")
                except Exception as e:
                    logger.warning(f"Error accepting terms: {e}")
            
            # Submit the form
            if form.submit_button_selector:
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, form.submit_button_selector)
                    submit_button.click()
                    
                    # Wait for submission to complete
                    time.sleep(3)
                    
                    # Check for success indicators
                    success_indicators = [
                        'thank you', 'success', 'entered', 'confirmation',
                        'submitted', 'complete'
                    ]
                    
                    page_text = driver.page_source.lower()
                    for indicator in success_indicators:
                        if indicator in page_text:
                            return True
                    
                    # If no clear success indicator, assume success if no error
                    return True
                    
                except Exception as e:
                    logger.error(f"Error submitting form: {e}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error in form filling process: {e}")
            return False
    
    def _get_field_value(self, field: FormField) -> Optional[str]:
        """
        Get the appropriate value for a form field based on configuration.
        
        Args:
            field: FormField object
            
        Returns:
            Value to fill in the field
        """
        personal_info = self.config.personal_info
        
        field_name_lower = field.name.lower()
        field_label_lower = field.label.lower()
        
        # Map common field patterns to personal info
        if any(x in field_name_lower for x in ['first', 'fname', 'given']):
            return personal_info.first_name
        elif any(x in field_name_lower for x in ['last', 'lname', 'surname', 'family']):
            return personal_info.last_name
        elif 'email' in field_name_lower:
            return personal_info.email
        elif any(x in field_name_lower for x in ['phone', 'mobile', 'tel']):
            return personal_info.phone
        elif 'address' in field_name_lower:
            return personal_info.address_line1
        elif 'city' in field_name_lower:
            return personal_info.city
        elif any(x in field_name_lower for x in ['state', 'province']):
            return personal_info.state
        elif any(x in field_name_lower for x in ['zip', 'postal', 'postcode']):
            return personal_info.postal_code
        elif 'country' in field_name_lower:
            return personal_info.country
        elif any(x in field_name_lower for x in ['birth', 'dob', 'birthday']):
            return personal_info.date_of_birth
        
        # Check label text as well
        if any(x in field_label_lower for x in ['name']) and not any(x in field_label_lower for x in ['last', 'sur']):
            return f"{personal_info.first_name} {personal_info.last_name}"
        
        # For required fields we can't identify, return a default
        if field.required and field.field_type == 'text':
            return "N/A"
        
        return None
    
    def _requires_authentication(self, url: str) -> str:
        """
        Check if a URL requires authentication and what type.
        
        Args:
            url: URL to check
            
        Returns:
            'site_level', 'competition_level', or 'none'
        """
        domain = extract_domain(url)
        for auth_domain, auth_type in self.auth_required_sites.items():
            if auth_domain in domain:
                return auth_type
        return 'none'
    
    async def _ensure_authenticated(self, url: str) -> bool:
        """
        Ensure user is authenticated for sites that require it.
        
        Args:
            url: URL that will be accessed
            
        Returns:
            True if authentication successful or not required, False otherwise
        """
        auth_type = self._requires_authentication(url)
        if auth_type == 'none':
            return True
        
        if not self.driver:
            self._get_webdriver()
        
        domain = extract_domain(url)
        logger.info(f"Authentication required for {domain} (type: {auth_type})")
        
        # For site-level auth, authenticate before accessing the site
        if auth_type == 'site_level':
            # Check if already logged in
            if self.google_auth.check_if_logged_in(domain):
                logger.info(f"Already authenticated to {domain}")
                return True
            
            # Attempt login
            success = self.google_auth.login_to_site(url, domain)
            if success:
                logger.info(f"Successfully authenticated to {domain}")
            else:
                logger.warning(f"Failed to authenticate to {domain}")
            
            return success
        
        # For competition-level auth, we'll handle it in _analyze_competition_page
        elif auth_type == 'competition_level':
            return True  # Don't block aggregator page access
        
        return True
    
    async def discover_competitions(self) -> List[Competition]:
        """
        Discover competitions from configured aggregator sites.
        
        Returns:
            List of discovered competitions
        """
        all_competitions = []
        
        for source in self.config.sources:
            logger.info(f"Processing source: {source.name}")
            
            # Ensure authentication if required
            if self._requires_authentication(source.url):
                auth_success = await self._ensure_authenticated(source.url)
                if not auth_success:
                    logger.warning(f"Skipping authenticated source due to failed authentication: {source.name}")
                    continue
            
            # Discover competitions from the source URL
            competitions = await self.discover_competitions_from_page(source.url, source.name)
            all_competitions.extend(competitions)
        
        logger.info(f"Total competitions discovered: {len(all_competitions)}")
        return all_competitions
    
    async def _fetch_competition_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a competition page, handling authentication if required.
        
        Args:
            url: Competition page URL
            
        Returns:
            BeautifulSoup object or None if failed
        """
        auth_type = self._requires_authentication(url)
        
        # For competition-level auth sites, try regular fetch first
        if auth_type == 'competition_level':
            # First try with aiohttp
            soup = await self.fetch_page(url)
            if soup:
                # Check if we got a login page or blocked content
                page_text = soup.get_text().lower()
                login_indicators = [
                    'sign in', 'log in', 'login required', 'please login',
                    'authentication required', 'access denied', 'unauthorized',
                    'you must be logged in', 'sign up', 'create account'
                ]
                
                if any(indicator in page_text for indicator in login_indicators):
                    logger.info(f"Login required for competition page: {url}")
                    
                    # Switch to Selenium and authenticate
                    if not self.driver:
                        self._get_webdriver()
                    
                    try:
                        # Navigate to the page with Selenium
                        self.driver.get(url)
                        time.sleep(3)
                        
                        # Look for and handle Google login
                        domain = extract_domain(url)
                        auth_success = self.google_auth.login_to_site(url, domain)
                        
                        if auth_success:
                            logger.info(f"Successfully authenticated for competition: {url}")
                            # Wait a bit for page to load after login
                            time.sleep(5)
                            
                            # Get the authenticated page content
                            page_source = self.driver.page_source
                            return BeautifulSoup(page_source, 'html.parser')
                        else:
                            logger.warning(f"Failed to authenticate for competition: {url}")
                            return None
                            

                    except Exception as e:
                        logger.error(f"Error handling authentication for {url}: {e}")
                        return None
                else:
                    # No login required, return the soup we got
                    return soup
            else:
                return None
        
        # For site-level auth or no auth, use the standard fetch
        elif auth_type == 'site_level':
            # Should already be authenticated, use Selenium
            if not self.driver:
                self._get_webdriver()
            
            try:
                self.driver.get(url)
                time.sleep(3)
                page_source = self.driver.page_source
                return BeautifulSoup(page_source, 'html.parser')
            except Exception as e:
                logger.error(f"Error fetching {url} with Selenium: {e}")
                return None
        
        else:
            # No auth required
            return await self.fetch_page(url)
    
    async def _handle_pagination_and_load_more(self, url: str, source_name: str) -> List[Competition]:
        """
        Handle pagination and 'show more' buttons for comprehensive competition discovery.
        
        Args:
            url: Base URL of the aggregator site
            source_name: Name of the source for logging
            
        Returns:
            List of all competitions found across all pages
        """
        domain = urlparse(url).netloc.lower()
        
        if 'competitioncloud.com.au' in domain:
            return await self._handle_competitioncloud_loading(url, source_name)
        elif 'aussiecomps.com' in domain:
            return await self._handle_aussiecomps_pagination(url, source_name)
        elif 'competitions.com.au' in domain:
            return await self._handle_competitions_au_pagination(url, source_name)
        else:
            # Fallback to single page processing
            return await self._discover_competitions_with_aiohttp(url, source_name)

    async def _handle_competitioncloud_loading(self, url: str, source_name: str) -> List[Competition]:
        """Handle CompetitionCloud's dynamic loading with 'Show More' buttons."""
        if not self.driver:
            self._get_webdriver()
        
        logger.info(f"Handling CompetitionCloud pagination/loading for {url}")
        
        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for initial load
            
            # Look for and click "Show More" or "Load More" buttons
            show_more_selectors = [
                "//button[contains(text(), 'Show More')]",
                "//button[contains(text(), 'Load More')]",
                "//a[contains(text(), 'Show More')]", 
                "//a[contains(text(), 'Load More')]",
                "//button[contains(@class, 'show-more')]",
                "//button[contains(@class, 'load-more')]",
                "//button[@data-action='load-more']",
                "//div[contains(@class, 'load-more')]//button",
                "//div[contains(@class, 'show-more')]//button"
            ]
            
            clicks_attempted = 0
            max_clicks = 15  # Prevent infinite loops
            
            while clicks_attempted < max_clicks:
                button_found = False
                
                for selector in show_more_selectors:
                    try:
                        buttons = self.driver.find_elements(By.XPATH, selector)
                        
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                logger.info(f"Clicking show more button: {selector}")
                                # Scroll into view first
                                self.driver.execute_script("arguments[0].scrollIntoView();", button)
                                time.sleep(1)
                                # Use JavaScript click to avoid interception
                                self.driver.execute_script("arguments[0].click();", button)
                                button_found = True
                                clicks_attempted += 1
                                time.sleep(3)  # Wait for content to load
                                break
                        
                        if button_found:
                            break
                    except Exception as e:
                        logger.debug(f"No button found for selector {selector}: {e}")
                        continue
                
                if not button_found:
                    logger.info("No more 'Show More' buttons found")
                    break
            
            # Now extract all competitions from the fully loaded page
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            return await self._process_competition_links(url, source_name, soup)
            
        except Exception as e:
            logger.error(f"Error handling CompetitionCloud loading: {e}")
            return []

    async def _handle_aussiecomps_pagination(self, url: str, source_name: str) -> List[Competition]:
        """Handle AussieComps pagination through multiple pages."""
        all_competitions = []
        base_url = url.rstrip('/')
        
        page = 1
        max_pages = 10  # Reasonable limit based on site structure
        
        logger.info(f"Handling AussieComps pagination for {url}")
        
        while page <= max_pages:
            try:
                # AussieComps uses /index.php?p=X&cat_id=0 pattern
                if page == 1:
                    page_url = url  # First page is the base URL
                else:
                    page_url = f"{base_url}/index.php?p={page}&cat_id=0"
                
                try:
                    soup = await self.fetch_page(page_url)
                    if soup and self._has_competitions_on_page(soup):
                        logger.info(f"Processing AussieComps page {page}: {page_url}")
                        competitions = await self._process_competition_links(page_url, source_name, soup)
                        if competitions:  # Only continue if we found competitions
                            all_competitions.extend(competitions)
                        else:
                            logger.info(f"No competitions found on page {page}, ending pagination")
                            break
                    else:
                        logger.info(f"No content found on page {page}, ending pagination")
                        break
                except Exception as e:
                    logger.debug(f"Failed to fetch AussieComps page {page_url}: {e}")
                    break
                
                page += 1
                await asyncio.sleep(2)  # Be respectful with delays
                
            except Exception as e:
                logger.error(f"Error processing AussieComps page {page}: {e}")
                break
        
        logger.info(f"Found {len(all_competitions)} total competitions across {page-1} AussieComps pages")
        return all_competitions

    async def _handle_competitions_au_pagination(self, url: str, source_name: str) -> List[Competition]:
        """Handle Competitions.com.au pagination and category browsing."""
        all_competitions = []
        base_url = url.rstrip('/')
        
        logger.info(f"Handling Competitions.com.au pagination for {url}")
        
        # First, get competitions from main page
        soup = await self.fetch_page(url)
        if soup:
            competitions = await self._process_competition_links(url, source_name, soup)
            all_competitions.extend(competitions)
        
        # Then try pagination
        page = 2  # Start from page 2 since we got page 1 above
        max_pages = 15
        
        while page <= max_pages:
            try:
                # Common pagination patterns for competitions.com.au
                page_urls = [
                    f"{base_url}/page/{page}/",
                    f"{base_url}?page={page}",
                    f"{base_url}/competitions/page/{page}/",
                    f"{base_url}/page{page}/",
                    f"{base_url}/?paged={page}"
                ]
                
                page_found = False
                
                for page_url in page_urls:
                    try:
                        soup = await self.fetch_page(page_url)
                        if soup and self._has_competitions_on_page(soup):
                            logger.info(f"Processing Competitions.com.au page {page}: {page_url}")
                            competitions = await self._process_competition_links(page_url, source_name, soup)
                            if competitions:  # Only continue if we found competitions
                                all_competitions.extend(competitions)
                                page_found = True
                                break
                        else:
                            logger.info(f"No content found on page {page_url}, skipping")
                    except Exception as e:
                        logger.debug(f"Failed to fetch Competitions.com.au page {page_url}: {e}")
                        continue
                
                if not page_found:
                    logger.info(f"No more valid pages found at page {page}")
                    break
                
                page += 1
                await asyncio.sleep(1)  # Be respectful
                
            except Exception as e:
                logger.error(f"Error processing Competitions.com.au page {page}: {e}")
                break
        
        logger.info(f"Found {len(all_competitions)} total competitions across {page-1} Competitions.com.au pages")
        return all_competitions

    def _has_competitions_on_page(self, soup) -> bool:
        """Check if a page contains competitions."""
        if not soup:
            return False
        
        # Check for AussieComps specific patterns first
        aussiecomps_indicators = soup.select('a[href*="/index.php?id="]')
        if aussiecomps_indicators:
            return True
        
        # Look for general competition indicators
        competition_indicators = [
            '.competition', '.contest', '.giveaway', '.entry',
            '[href*="/win"]', '[href*="/entry"]', '[href*="/exit"]',
            '[href*="competition"]', '[href*="contest"]'
        ]
        
        for indicator in competition_indicators:
            if soup.select(indicator):
                return True
        
        # Check text content for competition keywords
        page_text = soup.get_text().lower()
        if any(keyword in page_text for keyword in ['win', 'prize', 'competition', 'contest', 'enter', 'giveaway']):
            return True
        
        return False
