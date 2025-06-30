"""
Main competition scraper that orchestrates the modular components.
"""

import asyncio
import logging
from typing import List

from .base_scraper import BaseScraper
from .pagination_handler import PaginationHandler
from .page_processor import PageProcessor
from .form_detector import FormDetector
from .competition import Competition
from ..utils.config import AppConfig

logger = logging.getLogger("competition_auto_entry.scraper")


class CompetitionScraper(BaseScraper):
    """Main competition scraper that coordinates all scraping functionality."""
    
    def __init__(self, config: AppConfig):
        """
        Initialize the competition scraper.
        
        Args:
            config: Application configuration
        """
        super().__init__(config)
        
        # Initialize components
        self.form_detector = FormDetector()
        self.page_processor = PageProcessor(self, self.form_detector)
        self.pagination_handler = PaginationHandler(self)
    
    async def discover_competitions_from_page(
        self, 
        url: str, 
        source_name: str, 
        use_pagination: bool = True
    ) -> List[Competition]:
        """
        Discover competitions from an aggregator page.
        
        Args:
            url: URL of the aggregator page
            source_name: Name of the source for logging
            use_pagination: Whether to handle pagination and load more buttons
            
        Returns:
            List of discovered competitions
        """
        logger.info(f"Discovering competitions from: {url}")
        
        # Check if authentication is required
        auth_success = await self.authenticate_if_required(url)
        if not auth_success:
            logger.error(f"Failed to authenticate to {url}")
            return []
        
        try:
            if use_pagination:
                # Use pagination handler for comprehensive discovery
                competitions = await self.pagination_handler.handle_site_pagination(
                    url, source_name, self.page_processor.process_competition_links
                )
            else:
                # Simple single-page processing
                requires_auth, auth_type = self._requires_authentication(url)
                
                if requires_auth and auth_type == "site_level":
                    soup = self.fetch_page_selenium(url)
                else:
                    soup = await self.fetch_page(url)
                
                if soup:
                    competitions = await self.page_processor.process_competition_links(
                        url, source_name, soup
                    )
                else:
                    competitions = []
            
            return competitions
            
        except Exception as e:
            logger.error(f"Error discovering competitions from {url}: {e}")
            return []
    
    async def discover_competitions(self) -> List[Competition]:
        """
        Discover competitions from all configured aggregator sources.
        
        Returns:
            List of all discovered competitions
        """
        all_competitions = []
        
        # Get aggregator sources from config
        sources = getattr(self.config, 'aggregator_sources', [])
        
        for source in sources:
            if not source.get('enabled', True):
                logger.info(f"Skipping disabled source: {source.get('name', 'Unknown')}")
                continue
            
            try:
                competitions = await self.discover_competitions_from_page(
                    source['url'], 
                    source.get('name', 'Unknown Source')
                )
                all_competitions.extend(competitions)
                
                # Add delay between sources to be respectful
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing source {source.get('name', 'Unknown')}: {e}")
                continue
        
        logger.info(f"Total competitions discovered: {len(all_competitions)}")
        return all_competitions
    
    async def enter_competition(self, competition: Competition) -> bool:
        """
        Enter a specific competition.
        
        Args:
            competition: Competition to enter
            
        Returns:
            True if entry was successful, False otherwise
        """
        logger.info(f"Entering competition: {competition.title}")
        
        try:
            # Navigate to competition page
            if not self.driver:
                self._init_selenium()
            
            self.driver.get(competition.url)
            
            # Handle authentication if required
            requires_auth, auth_type = self._requires_authentication(competition.url)
            if requires_auth and auth_type == "competition_level":
                try:
                    await self.google_auth.handle_competition_login(competition.url)
                except Exception as e:
                    logger.debug(f"Authentication not needed or failed for {competition.url}: {e}")
            
            # Process each form in the competition
            for form in competition.forms:
                try:
                    success = await self._fill_and_submit_form(form, competition)
                    if success:
                        logger.info(f"Successfully entered competition: {competition.title}")
                        return True
                except Exception as e:
                    logger.error(f"Error filling form for {competition.title}: {e}")
                    continue
            
            logger.warning(f"No forms successfully submitted for: {competition.title}")
            return False
            
        except Exception as e:
            logger.error(f"Error entering competition {competition.title}: {e}")
            return False
    
    async def _fill_and_submit_form(self, form, competition: Competition) -> bool:
        """
        Fill and submit a competition entry form.
        
        Args:
            form: Form to fill and submit
            competition: Competition this form belongs to
            
        Returns:
            True if form was successfully submitted, False otherwise
        """
        # This would implement the actual form filling logic
        # For now, this is a placeholder that would be implemented based on
        # the existing form filling functionality from the original scraper
        
        logger.info(f"Would fill and submit form for: {competition.title}")
        return True  # Placeholder
