#!/usr/bin/env python3

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from intelligent_competition_system import AdaptiveCompetitionEntry

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_extended_batch():
    """Test a larger batch of competitions for maximum entries"""
    
    # Test competitions with various types
    test_competitions = [
        {
            "title": "Cubot P90 Smartphones",
            "url": "https://www.aussiecomps.com/index.php?id=24733&cat_id=0&p=&search=#onads",
            "expected_type": "button_click"
        },
        {
            "title": "Red Poppy Coins",
            "url": "https://www.aussiecomps.com/index.php?id=24729&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Drewmark Carpets",
            "url": "https://www.aussiecomps.com/index.php?id=24728&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Lego Batman Movie",
            "url": "https://www.aussiecomps.com/index.php?id=24727&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Bosch Home Appliances",
            "url": "https://www.aussiecomps.com/index.php?id=24726&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Heinz Baked Beans",
            "url": "https://www.aussiecomps.com/index.php?id=24725&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Coinxchange Crypto",
            "url": "https://www.aussiecomps.com/index.php?id=24724&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Taco Bell Lunch",
            "url": "https://www.aussiecomps.com/index.php?id=24723&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Apple iPad Pro",
            "url": "https://www.aussiecomps.com/index.php?id=24722&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Nintendo Switch Bundle",
            "url": "https://www.aussiecomps.com/index.php?id=24721&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        }
    ]
    
    system = AdaptiveCompetitionEntry()
    
    try:
        await system.initialize()
        
        results = {
            "successful": [],
            "failed": [],
            "total_processed": 0,
            "success_rate": 0
        }
        
        for idx, competition in enumerate(test_competitions, 1):
            print("=" * 80)
            print(f"Testing Competition {idx}: {competition['title']}")
            print(f"URL: {competition['url']}")
            print(f"Expected Type: {competition['expected_type']}")
            print("=" * 80)
            
            try:
                # Process the competition
                success = await system.process_competition_adaptively(
                    competition['url'],
                    competition['title']
                )
                
                results["total_processed"] += 1
                
                if success:
                    results["successful"].append(competition['title'])
                    print(f"✅ SUCCESS: {competition['title']}")
                else:
                    results["failed"].append(competition['title'])
                    print(f"❌ FAILED: {competition['title']}")
                
                # Small delay between competitions
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing {competition['title']}: {e}")
                results["failed"].append(competition['title'])
                results["total_processed"] += 1
                print(f"❌ ERROR: {competition['title']}")
        
        # Calculate success rate
        if results["total_processed"] > 0:
            results["success_rate"] = len(results["successful"]) / results["total_processed"] * 100
        
        # Print final summary
        print("\n" + "=" * 80)
        print("FINAL RESULTS SUMMARY")
        print("=" * 80)
        print(f"Successfully processed: {len(results['successful'])}/{results['total_processed']} competitions")
        print(f"Success rate: {results['success_rate']:.1f}%")
        
        print("\n✅ SUCCESSFUL ENTRIES:")
        for title in results["successful"]:
            print(f"  - {title}")
        
        print("\n❌ FAILED ENTRIES:")
        for title in results["failed"]:
            print(f"  - {title}")
        
        # Save results
        results_file = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
    finally:
        await system.close()

if __name__ == "__main__":
    asyncio.run(test_extended_batch())
