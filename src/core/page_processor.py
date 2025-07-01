"""
Competition page processing and link discovery functionality.
"""

import logging
from datetime import datetime
from typing import List, Optional, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..utils.helpers import (
    normalize_url, is_valid_url, clean_text, is_free_competition
)
from .competition import Competition
from .form_detector import FormDetector

logger = logging.getLogger("competition_auto_entry.page_processor")


class PageProcessor:
    """Handles processing of competition pages and link discovery."""
    
    def __init__(self, base_scraper, form_detector: FormDetector):
        """
        Initialize page processor.
        
        Args:
            base_scraper: Instance of BaseScraper for HTTP functionality
            form_detector: FormDetector instance for form analysis
        """
        self.base_scraper = base_scraper
        self.form_detector = form_detector
    
    async def process_competition_links(self, url: str, source_name: str, soup: BeautifulSoup) -> List[Competition]:
        """Process competition links from a parsed page."""
        competitions = []
        
        # Get site-specific selectors
        link_selectors = self._get_link_selectors(url)
        
        competition_links = self._extract_competition_links(soup, link_selectors, url)
        
        logger.info(f"Found {len(competition_links)} potential competition links")
        
        # Process each competition link
        for comp_url in list(competition_links)[:50]:  # Increased limit from 20 to 50
            try:
                competition = await self._analyze_competition_page(comp_url, source_name)
                if competition:
                    competitions.append(competition)
                    
            except Exception as e:
                logger.error(f"Error analyzing competition {comp_url}: {e}")
                continue
        
        logger.info(f"Successfully discovered {len(competitions)} competitions from {source_name}")
        return competitions
    
    def _get_link_selectors(self, url: str) -> List[str]:
        """Get site-specific selectors for competition links."""
        domain = urlparse(url).netloc.lower()
        
        if 'competitions.com.au' in domain:
            # Updated selectors based on actual site structure
            return [
                '.competition a',  # Main competition container
                'a[href*="/exit/"]',  # Direct competition links
                'a[href*="/win"]',  # Win-based URLs
                'a[href*="/prize"]',  # Prize-based URLs
                '.comp-item a', '.competition-link a', '.listing-item a'
            ]
        elif 'competitioncloud.com.au' in domain:
            # Specific selectors for Competition Cloud
            return [
                '.competition-card a', '.comp-listing a', '.entry-link a',
                'a[href*="/comp/"]', 'a[href*="/competition/"]',
                'a[href*="/entry/"]', 'a[href*="/enter/"]',
                '.card a', '.item a'
            ]
        elif 'aussiecomps.com' in domain:
            # Specific selectors for AussieComps - using actual URL patterns
            return [
                'a[href*="/index.php?id="]',  # Main competition links
                'a[href*="?id="]',  # Alternative ID pattern
                'tr a[href*="id="]',  # Links within table rows
                '.competition a', '.comp-item a'  # Fallback selectors
            ]
        else:
            # Generic fallback selectors
            return [
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
    
    def _extract_competition_links(self, soup: BeautifulSoup, link_selectors: List[str], base_url: str) -> Set[str]:
        """Extract competition links using the provided selectors."""
        competition_links = set()
        
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = normalize_url(href, base_url)
                    if is_valid_url(full_url) and self._is_valid_competition_link(full_url, link):
                        competition_links.add(full_url)
        
        return competition_links
    
    def _is_valid_competition_link(self, url: str, link_element) -> bool:
        """Check if a URL and link element represent a valid competition."""
        
        # Skip obvious non-competition URLs
        skip_patterns = [
            'mailto:', 'tel:', 'javascript:',
            '/terms', '/privacy', '/contact', '/about',
            '/faq', '/help', '/login', '/register',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            '/add-a-competition', '/promote', '/advertise'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Skip standalone anchor links (but not URLs with fragments like #onads)
        if url.strip() == '#' or url.startswith('#'):
            return False
        
        # Check for competition-like URL patterns
        competition_url_patterns = [
            '/exit/', '/entry/', '/enter/', '/win', '/prize',
            '/competition', '/contest', '/giveaway', '/comp/',
            '/c/', '/ps/',  # promotional/sponsored
            'index.php?id=', '?id='  # AussieComps patterns
        ]
        
        has_competition_url = any(pattern in url_lower for pattern in competition_url_patterns)
        
        # Check link text for competition keywords
        link_text = link_element.get_text().lower() if link_element else ""
        competition_text_patterns = [
            'win', 'prize', 'competition', 'contest', 'enter', 'giveaway'
        ]
        
        has_competition_text = any(pattern in link_text for pattern in competition_text_patterns)
        
        return has_competition_url or has_competition_text
    
    async def _analyze_competition_page(self, url: str, source: str) -> Optional[Competition]:
        """
        Analyze a competition page to extract details.
        
        Args:
            url: Competition page URL
            source: Source website name
            
        Returns:
            Competition object or None if not valid
        """
        
        # Skip obvious non-competition pages
        non_competition_indicators = [
            '/blog/', '/terms', '/privacy', '/contact', '/about',
            '/add-a-competition', '/promote', '/advertise', '/register'
        ]
        
        if any(indicator in url.lower() for indicator in non_competition_indicators):
            logger.debug(f"Skipping non-competition page: {url}")
            return None
        
        # Determine if we need authentication for this specific URL
        requires_auth, auth_type = self.base_scraper._requires_authentication(url)
        
        if requires_auth and auth_type == "competition_level":
            # Use Selenium for sites requiring login per competition
            soup = self.base_scraper.fetch_page_selenium(url)
            
            # Handle authentication if needed
            if 'competitions.com.au' in url and self.base_scraper.google_auth:
                try:
                    await self.base_scraper.google_auth.handle_competition_login(url)
                except Exception as e:
                    logger.debug(f"Authentication not needed or failed for {url}: {e}")
        else:
            # Use regular HTTP for other sites
            soup = await self.base_scraper.fetch_page(url)
        
        if not soup:
            return None
        
        # Extract title
        title = self._extract_title(soup)
        if not title:
            logger.warning(f"No title found for competition: {url}")
            return None
        
        # Extract page text and terms
        page_text = soup.get_text()
        terms_text = self._extract_terms_text(soup)
        
        # Check if competition is free
        is_free, rejection_reason = is_free_competition(page_text, terms_text)
        
        if not is_free:
            # Log the rejection
            self.base_scraper.rejection_logger.log_paid_detection_rejection(
                url=url,
                title=title,
                detection_reason=rejection_reason,
                page_text=page_text,
                terms_text=terms_text,
                source=source
            )
            
            logger.info(f"Competition appears to require payment: {title}")
            return None
        
        # Detect forms
        form = self.form_detector.detect_form(soup, url)
        # Note: For now, we'll store form info separately since Competition doesn't support forms yet
        
        # Create competition object
        competition = Competition(
            url=url,
            title=title,
            description=self._extract_description(soup),
            deadline=self._extract_deadline(soup),
            source=source
        )
        
        return competition
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from competition page."""
        title_selectors = ['h1', 'h2', '.title', '.competition-title', 'title']
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = clean_text(element.get_text())
                if title:
                    return title
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description from competition page."""
        description_selectors = [
            '.description', '.content', '.competition-description',
            '.entry-content', '.main-content', 'p'
        ]
        
        for selector in description_selectors:
            element = soup.select_one(selector)
            if element:
                description = clean_text(element.get_text())
                if len(description) > 50:  # Ensure it's substantial
                    return description[:500]  # Limit length
        
        return ""
    
    def _extract_deadline(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract deadline from competition page."""
        deadline_selectors = [
            '.deadline', '.closing-date', '.end-date',
            '.expires', '[class*="date"]', '[class*="deadline"]'
        ]
        
        for selector in deadline_selectors:
            element = soup.select_one(selector)
            if element:
                deadline = clean_text(element.get_text())
                if deadline:
                    # Try to parse the deadline string into a datetime object
                    from ..utils.helpers import parse_deadline
                    parsed_deadline = parse_deadline(deadline)
                    if parsed_deadline:
                        return parsed_deadline
        
        # Look for date patterns in text
        page_text = soup.get_text()
        import re
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'\d{4}-\d{1,2}-\d{1,2}'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                # Try to parse the first match
                from ..utils.helpers import parse_deadline
                parsed_deadline = parse_deadline(matches[0])
                if parsed_deadline:
                    return parsed_deadline
        
        return None
    
    def _extract_terms_text(self, soup: BeautifulSoup) -> str:
        """Extract terms and conditions text."""
        terms_selectors = [
            '.terms', '.conditions', '.rules',
            '.terms-and-conditions', '.competition-rules',
            '[class*="terms"]', '[class*="conditions"]'
        ]
        
        terms_text = ""
        for selector in terms_selectors:
            elements = soup.select(selector)
            for element in elements:
                terms_text += " " + element.get_text()
        
        return clean_text(terms_text)
