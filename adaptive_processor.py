#!/usr/bin/env python3
"""
Adaptive Competition Entry - Main Processing Logic
Continuation of the adaptive competition entry system
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional
from .adaptive_competition_entry import AdaptiveCompetitionEntry, CompetitionEntry, CompetitionStatus

logger = logging.getLogger(__name__)

class AdaptiveCompetitionProcessor:
    """Main processor for adaptive competition entry"""
    
    def __init__(self, entry_system: AdaptiveCompetitionEntry):
        self.entry_system = entry_system
        self.max_decision_depth = 10
        self.max_backtrack_attempts = 3

    async def process_competition(self, competition: CompetitionEntry) -> bool:
        """Process a competition using adaptive AI-driven approach"""
        logger.info(f"Processing competition: {competition.title}")
        
        try:
            # Initialize browser page
            page = await self.entry_system.context.new_page()
            
            # Navigate to competition
            await page.goto(competition.url)
            await page.wait_for_load_state('domcontentloaded')
            
            # Create root decision node
            root_node = await self.entry_system.create_decision_node(
                page, 
                "entry_method_detection", 
                f"Initial analysis of competition: {competition.title}"
            )
            competition.decision_tree = root_node
            
            # Start the adaptive decision process
            success = await self._adaptive_decision_process(page, competition, root_node)
            
            if success:
                competition.status = CompetitionStatus.SUCCESS
                logger.info(f"✅ Successfully processed competition: {competition.title}")
            else:
                competition.status = CompetitionStatus.FAILED
                logger.warning(f"❌ Failed to process competition: {competition.title}")
            
            # Save decision tree for learning
            await self.entry_system.save_decision_tree(competition)
            
            await page.close()
            return success
            
        except Exception as e:
            logger.error(f"Error processing competition {competition.title}: {e}")
            competition.status = CompetitionStatus.FAILED
            return False

    async def _adaptive_decision_process(self, page, competition: CompetitionEntry, current_node, depth: int = 0) -> bool:
        """Recursive adaptive decision-making process"""
        if depth > self.max_decision_depth:
            logger.warning(f"Maximum decision depth reached for {competition.title}")
            return False
        
        logger.info(f"Decision process depth {depth}: {current_node.decision_type}")
        
        try:
            # Execute current decision
            success = await self.entry_system.execute_decision(page, current_node)
            
            if not success:
                current_node.mark_failure("Decision execution failed")
                return await self._handle_decision_failure(page, competition, current_node, depth)
            
            current_node.mark_success()
            
            # Wait for page to settle
            await asyncio.sleep(2)
            
            # Determine next step based on current state
            next_decision_type = await self._determine_next_decision_type(page, current_node)
            
            if next_decision_type == "complete":
                logger.info("Competition entry process completed successfully")
                return True
            elif next_decision_type == "needs_human":
                logger.warning("Human intervention required")
                competition.status = CompetitionStatus.NEEDS_HUMAN
                return False
            elif next_decision_type:
                # Create next decision node
                next_node = await self.entry_system.create_decision_node(
                    page, 
                    next_decision_type, 
                    f"Following up on {current_node.decision_type}"
                )
                current_node.add_child(next_node)
                
                # Continue recursively
                return await self._adaptive_decision_process(page, competition, next_node, depth + 1)
            else:
                logger.warning("Unable to determine next step")
                return False
                
        except Exception as e:
            logger.error(f"Error in adaptive decision process: {e}")
            current_node.mark_failure(str(e))
            return await self._handle_decision_failure(page, competition, current_node, depth)

    async def _determine_next_decision_type(self, page, current_node) -> Optional[str]:
        """Determine what type of decision to make next"""
        try:
            # Check if we're on a success page
            page_text = await page.text_content('body')
            success_indicators = [
                'thank you', 'thanks', 'entered', 'submission received', 
                'success', 'confirmed', 'complete', 'registered'
            ]
            
            if any(indicator in page_text.lower() for indicator in success_indicators):
                return "complete"
            
            # Check if we need to fill a form
            forms = await page.query_selector_all('form')
            visible_inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
            
            if forms and visible_inputs:
                return "form_field_analysis"
            
            # Check if we need to navigate somewhere
            links = await page.query_selector_all('a')
            buttons = await page.query_selector_all('button')
            
            if links or buttons:
                return "navigation_decision"
            
            # Check for iframes (might contain competition forms)
            iframes = await page.query_selector_all('iframe')
            if iframes:
                return "iframe_analysis"
            
            # If we can't determine next step, might need human intervention
            return "needs_human"
            
        except Exception as e:
            logger.error(f"Error determining next decision type: {e}")
            return None

    async def _handle_decision_failure(self, page, competition: CompetitionEntry, failed_node, depth: int) -> bool:
        """Handle decision failure with backtracking"""
        logger.info(f"Handling decision failure at depth {depth}")
        
        # Try to backtrack and find alternative path
        alternative_node = await self.entry_system.backtrack_decision_tree(failed_node)
        
        if alternative_node and competition.retry_count < competition.max_retries:
            logger.info(f"Attempting alternative path (retry {competition.retry_count + 1})")
            competition.retry_count += 1
            
            # Navigate back to the alternative node's page
            try:
                await page.goto(alternative_node.page_url)
                await page.wait_for_load_state('domcontentloaded')
                
                # Continue from alternative node
                return await self._adaptive_decision_process(page, competition, alternative_node, depth)
                
            except Exception as e:
                logger.error(f"Error navigating to alternative path: {e}")
        
        logger.warning("No viable alternative paths found")
        return False

    async def discover_competitions(self, aggregator_url: str) -> List[CompetitionEntry]:
        """Discover competitions from an aggregator site using AI"""
        logger.info(f"Discovering competitions from: {aggregator_url}")
        
        try:
            page = await self.entry_system.context.new_page()
            await page.goto(aggregator_url)
            await page.wait_for_load_state('domcontentloaded')
            
            # Use AI to identify competition listings
            discovery_node = await self.entry_system.create_decision_node(
                page, 
                "competition_discovery", 
                f"Discovering competitions from {aggregator_url}"
            )
            
            # Extract competition links using AI analysis
            competitions = []
            
            # Get all links on the page
            links = await page.query_selector_all('a')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    
                    if href and text and self._is_competition_link(text, href):
                        # Make absolute URL
                        if not href.startswith('http'):
                            href = urljoin(aggregator_url, href)
                        
                        competition = CompetitionEntry(
                            url=href,
                            title=text.strip()
                        )
                        competitions.append(competition)
                        
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue
            
            await page.close()
            
            logger.info(f"Discovered {len(competitions)} competitions")
            return competitions
            
        except Exception as e:
            logger.error(f"Error discovering competitions: {e}")
            return []

    def _is_competition_link(self, text: str, href: str) -> bool:
        """Simple heuristic to identify competition links"""
        text_lower = text.lower()
        href_lower = href.lower()
        
        # Competition keywords
        competition_keywords = [
            'win', 'giveaway', 'contest', 'competition', 'prize', 'enter', 'chance'
        ]
        
        # Check if text contains competition keywords
        if any(keyword in text_lower for keyword in competition_keywords):
            return True
        
        # Check if URL contains competition patterns
        if any(pattern in href_lower for pattern in ['comp', 'contest', 'giveaway', 'prize']):
            return True
        
        return False

async def main():
    """Main entry point for adaptive competition entry"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Adaptive Competition Auto-Entry System')
    parser.add_argument('--aggregator-url', default='https://www.aussiecomps.com/', 
                       help='URL of competition aggregator site')
    parser.add_argument('--max-competitions', type=int, default=5, 
                       help='Maximum number of competitions to process')
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode')
    parser.add_argument('--config', default='config/config.json', 
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Initialize the adaptive entry system
    entry_system = AdaptiveCompetitionEntry(config_path=args.config, headless=args.headless)
    processor = AdaptiveCompetitionProcessor(entry_system)
    
    try:
        await entry_system.initialize()
        
        # Discover competitions
        competitions = await processor.discover_competitions(args.aggregator_url)
        
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
            
            success = await processor.process_competition(competition)
            
            if success:
                successful_entries += 1
            
            # Small delay between competitions
            await asyncio.sleep(2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY: {successful_entries}/{min(len(competitions), args.max_competitions)} competitions processed successfully")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        await entry_system.close()

if __name__ == "__main__":
    asyncio.run(main())
