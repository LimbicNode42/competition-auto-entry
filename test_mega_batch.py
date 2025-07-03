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

async def test_mega_batch():
    """Test an even larger batch of competitions for maximum entries"""
    
    # Test competitions with various types from different ranges
    test_competitions = [
        # First batch (already tested but will try again)
        {
            "title": "Samsung Galaxy S23",
            "url": "https://www.aussiecomps.com/index.php?id=24720&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Sony PlayStation 5",
            "url": "https://www.aussiecomps.com/index.php?id=24719&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "iPhone 14 Pro Max",
            "url": "https://www.aussiecomps.com/index.php?id=24718&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "MacBook Pro M2",
            "url": "https://www.aussiecomps.com/index.php?id=24717&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Tesla Model 3",
            "url": "https://www.aussiecomps.com/index.php?id=24716&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "BMW X5 SUV",
            "url": "https://www.aussiecomps.com/index.php?id=24715&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Home Cinema System",
            "url": "https://www.aussiecomps.com/index.php?id=24714&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Gaming PC Bundle",
            "url": "https://www.aussiecomps.com/index.php?id=24713&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Vacation Package",
            "url": "https://www.aussiecomps.com/index.php?id=24712&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Kitchen Appliances",
            "url": "https://www.aussiecomps.com/index.php?id=24711&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Fitness Equipment",
            "url": "https://www.aussiecomps.com/index.php?id=24710&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Home Theater Setup",
            "url": "https://www.aussiecomps.com/index.php?id=24709&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Smart Home Package",
            "url": "https://www.aussiecomps.com/index.php?id=24708&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Outdoor Furniture",
            "url": "https://www.aussiecomps.com/index.php?id=24707&cat_id=0&p=&search=#onads",
            "expected_type": "form_fill"
        },
        {
            "title": "Power Tools Set",
            "url": "https://www.aussiecomps.com/index.php?id=24706&cat_id=0&p=&search=#onads",
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
        print("MEGA BATCH RESULTS SUMMARY")
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
        results_file = f"mega_batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
    finally:
        await system.close()

if __name__ == "__main__":
    asyncio.run(test_mega_batch())
