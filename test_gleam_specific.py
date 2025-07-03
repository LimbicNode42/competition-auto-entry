#!/usr/bin/env python3
"""
Test specific competition that redirects to Gleam.io to verify form filling
"""

import asyncio
import logging
from intelligent_competition_system import AdaptiveCompetitionEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_gleam_competition():
    """Test PERGOLUX Pergola competition that redirects to Gleam.io"""
    
    system = AdaptiveCompetitionEntry(headless=False)
    
    try:
        await system.initialize()
        
        # Test the specific competition that redirects to Gleam.io
        competition_url = "https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads"
        competition_title = "Win a 3m x 3m PERGOLUX Pergola"
        
        logger.info(f"Testing Gleam.io competition: {competition_title}")
        logger.info(f"URL: {competition_url}")
        
        success = await system.process_competition_adaptively(competition_url, competition_title, max_depth=8)
        
        if success:
            logger.info("✅ Competition processed successfully!")
        else:
            logger.warning("❌ Competition processing failed")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        
    finally:
        await system.close()

if __name__ == '__main__':
    asyncio.run(test_gleam_competition())
