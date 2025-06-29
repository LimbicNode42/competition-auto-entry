"""
Competition aggregator website integrations.
"""

import asyncio
from typing import List, Dict, Any
import logging

from ..core.scraper import CompetitionScraper
from ..core.competition import Competition
from ..utils.config import AppConfig

logger = logging.getLogger("competition_auto_entry.aggregators")


class AggregatorManager:
    """Manages interactions with competition aggregator websites."""
    
    def __init__(self, config: AppConfig):
        """
        Initialize the aggregator manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.scraper = CompetitionScraper(config)
        
        # Default aggregator sites if none configured
        self.default_aggregators = [
            {
                'name': 'Contest Girl',
                'url': 'https://www.contestgirl.com/',
                'enabled': True
            },
            {
                'name': 'Sweeties Sweeps',
                'url': 'https://www.sweetiessweeps.com/',
                'enabled': True
            },
            {
                'name': 'Contest Bee',
                'url': 'https://www.contestbee.com/',
                'enabled': True
            },
            {
                'name': 'Online Sweepstakes',
                'url': 'https://www.online-sweepstakes.com/',
                'enabled': True
            }
        ]
    
    async def discover_competitions(self) -> List[Competition]:
        """
        Discover competitions from all configured aggregator websites.
        
        Returns:
            List of discovered competitions
        """
        logger.info("Starting competition discovery from aggregator websites")
        
        all_competitions = []
        aggregators = self._get_aggregator_list()
        
        async with self.scraper:
            # Process aggregators concurrently (but with limits)
            semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
            
            tasks = []
            for aggregator in aggregators:
                if aggregator.get('enabled', True):
                    task = self._discover_from_aggregator(semaphore, aggregator)
                    tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for result in results:
                if isinstance(result, list):
                    all_competitions.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error during discovery: {result}")
        
        logger.info(f"Total competitions discovered: {len(all_competitions)}")
        return all_competitions
    
    async def _discover_from_aggregator(
        self, 
        semaphore: asyncio.Semaphore, 
        aggregator: Dict[str, Any]
    ) -> List[Competition]:
        """
        Discover competitions from a single aggregator.
        
        Args:
            semaphore: Semaphore for rate limiting
            aggregator: Aggregator configuration
            
        Returns:
            List of competitions from this aggregator
        """
        async with semaphore:
            try:
                competitions = await self.scraper.discover_competitions_from_page(
                    aggregator['url'], 
                    aggregator['name']
                )
                logger.info(f"Found {len(competitions)} competitions from {aggregator['name']}")
                return competitions
                
            except Exception as e:
                logger.error(f"Error discovering from {aggregator['name']}: {e}")
                return []
    
    def _get_aggregator_list(self) -> List[Dict[str, Any]]:
        """
        Get the list of aggregator websites to check.
        
        Returns:
            List of aggregator configurations
        """
        # Use configured URLs if available
        if self.config.aggregator_urls:
            return [
                {
                    'name': f"Aggregator {i+1}",
                    'url': url,
                    'enabled': True
                }
                for i, url in enumerate(self.config.aggregator_urls)
            ]
        
        # Otherwise use defaults
        return self.default_aggregators


class SpecificAggregatorHandlers:
    """Specific handlers for known aggregator websites."""
    
    @staticmethod
    async def handle_contest_girl(scraper: CompetitionScraper) -> List[Competition]:
        """
        Handle Contest Girl specific scraping logic.
        
        Args:
            scraper: CompetitionScraper instance
            
        Returns:
            List of competitions
        """
        # Contest Girl specific implementation
        # This would include site-specific selectors and logic
        pass
    
    @staticmethod
    async def handle_sweeties_sweeps(scraper: CompetitionScraper) -> List[Competition]:
        """
        Handle Sweeties Sweeps specific scraping logic.
        
        Args:
            scraper: CompetitionScraper instance
            
        Returns:
            List of competitions
        """
        # Sweeties Sweeps specific implementation
        pass
    
    @staticmethod
    async def handle_contest_bee(scraper: CompetitionScraper) -> List[Competition]:
        """
        Handle Contest Bee specific scraping logic.
        
        Args:
            scraper: CompetitionScraper instance
            
        Returns:
            List of competitions
        """
        # Contest Bee specific implementation
        pass
