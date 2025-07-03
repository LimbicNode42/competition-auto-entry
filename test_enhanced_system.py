#!/usr/bin/env python3
"""
Test the enhanced adaptive system with multi-step navigation
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_competition_system import AdaptiveCompetitionEntry


async def test_enhanced_system():
    """Test the enhanced system with different types of ps/ links"""
    system = AdaptiveCompetitionEntry()
    
    # Test different competition types
    test_competitions = [
        {
            'name': 'PERGOLUX Pergola (Gleam.io social actions)',
            'url': 'https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads',
            'expected_pattern': 'social_media_actions'
        },
        {
            'name': 'Cubot P90 (Join Giveaway button)',
            'url': 'https://www.aussiecomps.com/index.php?id=24733&cat_id=0&p=&search=#onads',
            'expected_pattern': 'navigation_button'
        }
    ]
    
    for test in test_competitions:
        print(f"\n{'='*80}")
        print(f"Testing: {test['name']}")
        print(f"URL: {test['url']}")
        print(f"Expected pattern: {test['expected_pattern']}")
        print(f"{'='*80}")
        
        try:
            result = await system.process_competition_adaptively(test['url'], test['name'])
            
            print(f"Success: {result}")
            
            if result:
                print("✅ Competition processed successfully")
            else:
                print("❌ Competition processing failed")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "-"*80)
        await asyncio.sleep(3)  # Wait between tests
    
    await system.close()


if __name__ == "__main__":
    asyncio.run(test_enhanced_system())
