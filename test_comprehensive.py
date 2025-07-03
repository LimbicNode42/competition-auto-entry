#!/usr/bin/env python3
"""
Comprehensive test for the intelligent competition system
Tests various scenarios and edge cases
"""

import asyncio
import logging
from intelligent_competition_system import AdaptiveCompetitionEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_comprehensive_scenarios():
    """Test various competition scenarios"""
    
    # Test with different aggregator URLs
    test_urls = [
        "https://www.aussiecomps.com/",
        # Could add more aggregators later
    ]
    
    for url in test_urls:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing aggregator: {url}")
        logger.info(f"{'='*60}")
        
        system = AdaptiveCompetitionEntry(headless=False)
        
        try:
            await system.initialize()
            
            # Test discovery
            competitions = await system.discover_competitions(url)
            logger.info(f"Discovered {len(competitions)} competitions")
            
            if not competitions:
                logger.warning("No competitions found - check discovery logic")
                continue
            
            # Test processing first 3 competitions
            for i, comp in enumerate(competitions[:3]):
                logger.info(f"\nProcessing competition {i+1}: {comp['title']}")
                
                try:
                    success = await system.process_competition_adaptively(comp['url'], comp['title'])
                    if success:
                        logger.info(f"✅ Success: {comp['title']}")
                    else:
                        logger.warning(f"❌ Failed: {comp['title']}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {comp['title']}: {e}")
                
                # Small delay between competitions
                await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error testing {url}: {e}")
            
        finally:
            await system.close()
    
    logger.info("\n" + "="*60)
    logger.info("Comprehensive testing completed")
    logger.info("="*60)

async def test_decision_tree_backtracking():
    """Test the decision tree backtracking capabilities"""
    logger.info("\n" + "="*60)
    logger.info("Testing decision tree backtracking")
    logger.info("="*60)
    
    system = AdaptiveCompetitionEntry(headless=False)
    
    try:
        await system.initialize()
        
        # Create a mock competition that might require backtracking
        mock_comp = {
            'url': 'https://www.aussiecomps.com/index.php?id=24763&cat_id=0&p=&search=#onads',
            'title': 'Test Competition for Backtracking',
            'source': 'test'
        }
        
        # Process and observe decision tree behavior
        success = await system.process_competition_adaptively(mock_comp['url'], mock_comp['title'])
        
        if success:
            logger.info("✅ Decision tree system working correctly")
        else:
            logger.warning("❌ Decision tree system needs improvement")
            
    except Exception as e:
        logger.error(f"Error testing decision tree: {e}")
        
    finally:
        await system.close()

async def test_error_handling():
    """Test error handling and recovery"""
    logger.info("\n" + "="*60)
    logger.info("Testing error handling and recovery")
    logger.info("="*60)
    
    system = AdaptiveCompetitionEntry(headless=False)
    
    try:
        await system.initialize()
        
        # Test with invalid URL
        invalid_competitions = [
            {'url': 'https://invalid-url-that-does-not-exist.com/', 'title': 'Invalid URL Test', 'source': 'test'},
            {'url': 'https://www.google.com/', 'title': 'No competition on Google', 'source': 'test'}
        ]
        
        for comp in invalid_competitions:
            logger.info(f"Testing error handling for: {comp['title']}")
            try:
                success = await system.process_competition_adaptively(comp['url'], comp['title'])
                logger.info(f"Result: {'Success' if success else 'Failed (expected)'}")
            except Exception as e:
                logger.info(f"Caught exception (expected): {e}")
                
    except Exception as e:
        logger.error(f"Error in error handling test: {e}")
        
    finally:
        await system.close()

if __name__ == '__main__':
    asyncio.run(test_comprehensive_scenarios())
    asyncio.run(test_decision_tree_backtracking())
    asyncio.run(test_error_handling())
