"""
Base scraper functionality for HTTP requests and Selenium WebDriver management.
"""

import time
import logging
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from fake_useragent import UserAgent

from ..utils.config import AppConfig
from ..utils.rejection_logger import RejectionLogger
from ..integrations.google_auth import GoogleAuthHandler
from ..integrations.basic_auth import BasicAuthHandler

logger = logging.getLogger("competition_auto_entry.base_scraper")


class BaseScraper:
    """Base scraper class handling HTTP requests and WebDriver management."""
    
    def __init__(self, config: AppConfig):
        """
        Initialize the base scraper.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.user_agent = UserAgent()
        self.session: Optional[aiohttp.ClientSession] = None
        self.driver: Optional[webdriver.Chrome] = None
        
        # Initialize rejection logger (clear on each run for fresh feedback)
        rejection_log_path = getattr(config, 'rejection_log_path', 'data/rejection_log.json')
        self.rejection_logger = RejectionLogger(rejection_log_path, clear_on_init=True)
        
        # Auth handlers (initialized when driver is created)
        self.google_auth = None
        self.basic_auth = None
        
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
            
            # Initialize auth handlers
            self.google_auth = GoogleAuthHandler(self.config, self.driver)
            self.basic_auth = BasicAuthHandler(self.driver, self.config)
            
            logger.info("Chrome WebDriver initialized")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise WebDriverException(f"Failed to initialize WebDriver: {e}")
    
    def _init_selenium(self) -> None:
        """Initialize Selenium WebDriver if not already done."""
        if not self.driver:
            self._get_webdriver()
    
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
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return BeautifulSoup(html, 'html.parser')
                elif response.status == 404:
                    logger.warning(f"HTTP 404 for URL: {url}")
                    return None
                else:
                    logger.warning(f"HTTP {response.status} for URL: {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def fetch_page_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a web page using Selenium and return BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup object or None if failed
        """
        if not self.driver:
            self._init_selenium()
        
        try:
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            
            # Get page source and parse with BeautifulSoup
            html = self.driver.page_source
            return BeautifulSoup(html, 'html.parser')
            
        except Exception as e:
            logger.error(f"Error fetching {url} with Selenium: {e}")
            return None
    
    def _requires_authentication(self, url: str) -> tuple[bool, str]:
        """
        Check if a URL requires authentication.
        
        Args:
            url: URL to check
            
        Returns:
            Tuple of (requires_auth: bool, auth_type: str)
        """
        domain = urlparse(url).netloc.lower()
        
        for auth_domain, auth_type in self.auth_required_sites.items():
            if auth_domain in domain:
                return True, auth_type
        
        return False, ""
    
    async def authenticate_if_required(self, url: str) -> bool:
        """
        Authenticate to a site if required.
        
        Args:
            url: URL that may require authentication
            
        Returns:
            True if authentication successful or not required, False otherwise
        """
        requires_auth, auth_type = self._requires_authentication(url)
        
        if not requires_auth:
            return True
        
        domain = urlparse(url).netloc.lower()
        logger.info(f"Authentication required for {domain} (type: {auth_type})")
        
        if not self.google_auth or not self.basic_auth:
            self._init_selenium()  # This initializes auth handlers
        
        try:
            if auth_type == "site_level":
                # Authenticate at the site level (before browsing)
                return await self._authenticate_site_level(url)
            elif auth_type == "competition_level":
                # Authentication happens per competition
                return True  # Will authenticate when needed
            else:
                logger.warning(f"Unknown authentication type: {auth_type}")
                return True
                
        except Exception as e:
            logger.error(f"Authentication failed for {domain}: {e}")
            return False
    
    async def _authenticate_site_level(self, url: str) -> bool:
        """Authenticate at the site level."""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            # Use basic auth for Competition Cloud, Google auth for others
            if 'competitioncloud.com.au' in domain:
                success = self.basic_auth.login_to_site(url, domain)
            else:
                success = self.google_auth.login_to_site(url, domain)
                
            if success:
                logger.info(f"Successfully authenticated to {domain}")
                return True
            else:
                logger.error(f"Failed to authenticate to {domain}")
                return False
        except Exception as e:
            logger.error(f"Site-level authentication error: {e}")
            return False
