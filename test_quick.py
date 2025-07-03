#!/usr/bin/env python3
"""
Quick test of the enhanced intelligent competition system
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_competition_system import AdaptiveCompetitionEntry


async def test_specific_competition():
    """Test a specific competition URL"""
    system = AdaptiveCompetitionEntry()
    
    # Test the PERGOLUX Pergola competition
    test_url = "https://www.aussiecomps.com/index.php?id=24734&cat_id=0&p=&search=#onads"
    
    print(f"Testing: {test_url}")
    
    try:
        # Initialize the system
        await system.initialize()
        
        # Process the competition
        success = await system.process_competition_adaptively(test_url, "PERGOLUX Pergola Test", max_depth=10)
        
        print(f"Success: {success}")
        
        # Check the latest decision tree
        import os
        decision_trees = [f for f in os.listdir("decision_trees") if f.endswith('.json')]
        if decision_trees:
            latest_tree = max(decision_trees, key=lambda x: os.path.getctime(os.path.join("decision_trees", x)))
            print(f"Latest decision tree: {latest_tree}")
        
        await system.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_specific_competition())
