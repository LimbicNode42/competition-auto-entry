#!/usr/bin/env python3
"""
Test the adaptive system's ability to handle multi-step navigation to competition forms.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_competition_system import AdaptiveCompetitionEntry


async def test_adaptive_system():
    """Test the adaptive system on a specific competition"""
    system = AdaptiveCompetitionEntry()
    
    # Test URL that we know leads to Gleam.io
    test_url = "https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads"
    
    print(f"Testing adaptive system for: {test_url}")
    print("-" * 80)
    
    try:
        # Initialize the system
        await system.initialize()
        
        # Process the competition
        success = await system.process_competition_adaptively(test_url, "Test Pergola Competition", max_depth=10)
        
        print(f"\nProcessing complete. Success: {success}")
        
        # Check if decision tree was created
        decision_trees = os.listdir("decision_trees")
        print(f"Decision trees created: {len(decision_trees)}")
        
        if decision_trees:
            latest_tree = max(decision_trees, key=lambda x: os.path.getctime(os.path.join("decision_trees", x)))
            print(f"Latest decision tree: {latest_tree}")
            
            # Read the decision tree
            with open(os.path.join("decision_trees", latest_tree), 'r') as f:
                tree_data = f.read()
                print(f"Decision tree content (first 500 chars):\n{tree_data[:500]}...")
        
        await system.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_adaptive_system())
