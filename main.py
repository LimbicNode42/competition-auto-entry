#!/usr/bin/env python3
"""
Competition Auto-Entry System
Main entry point for the competition automation system.
"""

import asyncio
import sys
from pathlib import Path
import click
from typing import Optional

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_logging
from src.utils.config import load_config
from src.core.scraper import CompetitionScraper
from src.core.tracker import CompetitionTracker
from src.integrations.aggregators import AggregatorManager

# Setup logging
logger = setup_logging()


@click.command()
@click.option('--config', '-c', default='config/config.json', 
              help='Path to configuration file')
@click.option('--dry-run', is_flag=True, 
              help='Run in dry-run mode (no actual entries)')
@click.option('--verbose', '-v', is_flag=True, 
              help='Enable verbose logging')
@click.option('--max-entries', '-m', default=10, 
              help='Maximum number of competitions to enter per run')
def main(config: str, dry_run: bool, verbose: bool, max_entries: int) -> None:
    """
    Competition Auto-Entry System
    
    Automatically discovers and enters free competitions from aggregation websites.
    """
    if verbose:
        logger.setLevel("DEBUG")
    
    logger.info("Starting Competition Auto-Entry System")
    logger.info(f"Configuration file: {config}")
    logger.info(f"Dry run mode: {dry_run}")
    logger.info(f"Max entries per run: {max_entries}")
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        app_config = load_config(config)
        
        # Initialize components
        tracker = CompetitionTracker()
        scraper = CompetitionScraper(app_config)
        aggregator_manager = AggregatorManager(app_config)
        
        # Run the main process
        asyncio.run(run_competition_entry_process(
            tracker, scraper, aggregator_manager, 
            dry_run, max_entries
        ))
        
        logger.info("Competition Auto-Entry System completed successfully")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if verbose:
            logger.exception("Full error traceback:")
        sys.exit(1)


async def run_competition_entry_process(
    tracker: CompetitionTracker,
    scraper: CompetitionScraper,
    aggregator_manager: AggregatorManager,
    dry_run: bool,
    max_entries: int
) -> None:
    """
    Main competition entry process.
    
    Args:
        tracker: Competition tracking system
        scraper: Web scraping system
        aggregator_manager: Aggregator website manager
        dry_run: Whether to run in dry-run mode
        max_entries: Maximum entries per run
    """
    logger.info("Starting competition discovery and entry process")
    
    # Step 1: Discover new competitions
    logger.info("Discovering new competitions from aggregator websites...")
    new_competitions = await aggregator_manager.discover_competitions()
    logger.info(f"Found {len(new_competitions)} new competitions")
    
    # Step 2: Filter competitions (free only, not previously entered)
    logger.info("Filtering competitions...")
    eligible_competitions = await tracker.filter_eligible_competitions(
        new_competitions, max_entries
    )
    logger.info(f"Found {len(eligible_competitions)} eligible competitions")
    
    # Step 3: Enter competitions
    entries_attempted = 0
    entries_successful = 0
    
    for competition in eligible_competitions:
        if entries_attempted >= max_entries:
            logger.info(f"Reached maximum entries limit ({max_entries})")
            break
            
        logger.info(f"Processing competition: {competition.title}")
        entries_attempted += 1
        
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would enter competition: {competition.url}")
                success = True
            else:
                success = await scraper.enter_competition(competition)
            
            if success:
                entries_successful += 1
                await tracker.record_entry(competition, success=True)
                logger.info(f"Successfully entered: {competition.title}")
            else:
                await tracker.record_entry(competition, success=False)
                logger.warning(f"Failed to enter: {competition.title}")
                
        except Exception as e:
            logger.error(f"Error entering competition {competition.title}: {e}")
            await tracker.record_entry(competition, success=False, error=str(e))
    
    # Step 4: Summary
    logger.info("=" * 50)
    logger.info("ENTRY SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Competitions discovered: {len(new_competitions)}")
    logger.info(f"Competitions eligible: {len(eligible_competitions)}")
    logger.info(f"Entries attempted: {entries_attempted}")
    logger.info(f"Entries successful: {entries_successful}")
    logger.info(f"Success rate: {(entries_successful/entries_attempted*100):.1f}%" if entries_attempted > 0 else "N/A")


if __name__ == "__main__":
    main()
