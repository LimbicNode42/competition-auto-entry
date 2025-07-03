#!/usr/bin/env python3
"""
Run the competition auto-entry system on multiple competitions to test real-world performance
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_competition_system import AdaptiveCompetitionEntry


async def test_multiple_competitions():
    """Test the system on multiple competitions from AussieComps"""
    system = AdaptiveCompetitionEntry()
    
    # Test URLs for different competitions
    test_competitions = [
        {
            'url': 'https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads',
            'name': 'PERGOLUX Pergola (Gleam.io)',
            'expected_type': 'social_media'
        },
        {
            'url': 'https://www.aussiecomps.com/index.php?id=24733&cat_id=0&p=&search=#onads', 
            'name': 'Cubot P90 Smartphones',
            'expected_type': 'button_click'
        },
        {
            'url': 'https://www.aussiecomps.com/index.php?id=24729&cat_id=0&p=&search=#onads',
            'name': 'Red Poppy Coins',
            'expected_type': 'form_fill'
        }
    ]
    
    results = []
    
    try:
        await system.initialize()
        
        for i, comp in enumerate(test_competitions):
            print(f"\n{'='*80}")
            print(f"Testing Competition {i+1}: {comp['name']}")
            print(f"URL: {comp['url']}")
            print(f"Expected Type: {comp['expected_type']}")
            print(f"{'='*80}")
            
            try:
                # Process with limited depth to avoid infinite loops
                success = await system.process_competition_adaptively(
                    comp['url'], 
                    comp['name'], 
                    max_depth=3  # Limit depth to avoid infinite loops
                )
                
                result = {
                    'name': comp['name'],
                    'url': comp['url'],
                    'success': success,
                    'expected_type': comp['expected_type']
                }
                results.append(result)
                
                if success:
                    print(f"✅ SUCCESS: {comp['name']}")
                else:
                    print(f"❌ FAILED: {comp['name']}")
                    
            except Exception as e:
                print(f"❌ ERROR: {comp['name']} - {e}")
                results.append({
                    'name': comp['name'],
                    'url': comp['url'],
                    'success': False,
                    'error': str(e),
                    'expected_type': comp['expected_type']
                })
            
            # Wait between competitions
            await asyncio.sleep(3)
        
        # Print summary
        print(f"\n{'='*80}")
        print("FINAL RESULTS SUMMARY")
        print(f"{'='*80}")
        
        successful = sum(1 for r in results if r.get('success', False))
        total = len(results)
        
        print(f"Successfully processed: {successful}/{total} competitions")
        print()
        
        for result in results:
            status = "✅ SUCCESS" if result.get('success', False) else "❌ FAILED"
            error_info = f" - {result.get('error', '')}" if 'error' in result else ""
            print(f"{status}: {result['name']} ({result['expected_type']}){error_info}")
        
        await system.close()
        
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_multiple_competitions())
