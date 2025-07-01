"""
Pagination and "Load More" button handling for aggregator sites.
"""

import time
import asyncio
import logging
from typing import List, Optional
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

from ..utils.helpers import normalize_url, is_valid_url
from .competition import Competition

logger = logging.getLogger("competition_auto_entry.pagination_handler")


class PaginationHandler:
    """Handles pagination and dynamic loading for aggregator sites."""
    
    def __init__(self, base_scraper):
        """
        Initialize pagination handler.
        
        Args:
            base_scraper: Instance of BaseScraper for HTTP and Selenium functionality
        """
        self.base_scraper = base_scraper
    
    async def handle_site_pagination(self, url: str, source_name: str, page_processor) -> List[Competition]:
        """
        Handle pagination and 'show more' buttons for comprehensive competition discovery.
        
        Args:
            url: Base URL of the aggregator site
            source_name: Name of the source for logging
            page_processor: Function to process competition links from soup
            
        Returns:
            List of all competitions found across all pages
        """
        domain = urlparse(url).netloc.lower()
        
        if 'competitioncloud.com.au' in domain:
            return await self._handle_competitioncloud_loading(url, source_name, page_processor)
        elif 'aussiecomps.com' in domain:
            return await self._handle_aussiecomps_pagination(url, source_name, page_processor)
        elif 'competitions.com.au' in domain:
            return await self._handle_competitions_au_pagination(url, source_name, page_processor)
        else:
            # Generic handling for other sites
            return await self._handle_generic_pagination(url, source_name, page_processor)
    
    async def _handle_competitioncloud_loading(self, url: str, source_name: str, page_processor) -> List[Competition]:
        """Handle CompetitionCloud's dynamic loading with 'Show More' buttons."""
        if not self.base_scraper.driver:
            self.base_scraper._init_selenium()
        
        logger.info(f"Handling CompetitionCloud pagination/loading for {url}")
        
        try:
            self.base_scraper.driver.get(url)
            time.sleep(3)  # Wait for initial load
            
            # Look for and click "Show More" or "Load More" buttons
            show_more_selectors = [
                "//button[contains(text(), 'Show More')]",
                "//button[contains(text(), 'Load More')]",
                "//a[contains(text(), 'Show More')]",
                "//a[contains(text(), 'Load More')]",
                "//button[contains(@class, 'show-more')]",
                "//button[contains(@class, 'load-more')]",
                "//button[@data-action='load-more']"
            ]
            
            clicks_attempted = 0
            max_clicks = 15  # Prevent infinite loops
            
            while clicks_attempted < max_clicks:
                button_found = False
                
                for selector in show_more_selectors:
                    try:
                        buttons = self.base_scraper.driver.find_elements(By.XPATH, selector)
                        
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                logger.info(f"Clicking show more button: {selector}")
                                self.base_scraper.driver.execute_script("arguments[0].scrollIntoView();", button)
                                time.sleep(1)
                                self.base_scraper.driver.execute_script("arguments[0].click();", button)
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
            soup = BeautifulSoup(self.base_scraper.driver.page_source, 'html.parser')
            return await page_processor(url, source_name, soup)
            
        except Exception as e:
            logger.error(f"Error handling CompetitionCloud loading: {e}")
            return []
    
    async def _handle_aussiecomps_pagination(self, url: str, source_name: str, page_processor) -> List[Competition]:
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
                    soup = await self.base_scraper.fetch_page(page_url)
                    if soup and self._has_competitions_on_page(soup):
                        logger.info(f"Processing AussieComps page {page}: {page_url}")
                        competitions = await page_processor(page_url, source_name, soup)
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
    
    async def _handle_competitions_au_pagination(self, url: str, source_name: str, page_processor) -> List[Competition]:
        """Handle Competitions.com.au pagination and category browsing."""
        all_competitions = []
        base_url = url.rstrip('/')
        
        logger.info(f"Handling Competitions.com.au pagination for {url}")
        
        # First, get competitions from main page
        soup = await self.base_scraper.fetch_page(url)
        if soup:
            competitions = await page_processor(url, source_name, soup)
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
                    f"{base_url}/page{page}/"
                ]
                
                page_found = False
                
                for page_url in page_urls:
                    try:
                        soup = await self.base_scraper.fetch_page(page_url)
                        if soup and self._has_competitions_on_page(soup):
                            logger.info(f"Processing Competitions.com.au page {page}: {page_url}")
                            competitions = await page_processor(page_url, source_name, soup)
                            if competitions:  # Only continue if we found competitions
                                all_competitions.extend(competitions)
                                page_found = True
                                break
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
    
    async def _handle_generic_pagination(self, url: str, source_name: str, page_processor) -> List[Competition]:
        """Generic pagination handler for unknown sites."""
        all_competitions = []
        
        # Start with the main page
        soup = await self.base_scraper.fetch_page(url)
        if soup:
            competitions = await page_processor(url, source_name, soup)
            all_competitions.extend(competitions)
            
            # Look for pagination links
            pagination_selectors = [
                '.pagination a', '.pager a', '.page-numbers a',
                'a[rel="next"]', '.next-page', '.load-more'
            ]
            
            next_urls = set()
            for selector in pagination_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and any(keyword in link.get_text().lower() for keyword in ['next', 'more', '>', '2', '3']):
                        full_url = normalize_url(href, url)
                        if is_valid_url(full_url):
                            next_urls.add(full_url)
            
            # Process found pagination URLs
            for next_url in list(next_urls)[:5]:  # Limit to prevent infinite loops
                try:
                    soup = await self.base_scraper.fetch_page(next_url)
                    if soup and self._has_competitions_on_page(soup):
                        competitions = await page_processor(next_url, source_name, soup)
                        all_competitions.extend(competitions)
                except Exception as e:
                    logger.debug(f"Error processing pagination URL {next_url}: {e}")
        
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
