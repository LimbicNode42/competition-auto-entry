#!/usr/bin/env python3
"""
Test the Competition Auto-Entry Final System with a public competition form
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure the correct paths are set up
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import the main entry system
from competition_auto_entry_final import CompetitionAutoEntry, logger

# Configure logging
logging.getLogger().setLevel(logging.INFO)

# Test with a public competition form that doesn't require login
async def run_test():
    """Run the test with a public competition form"""
    
    # Load environment variables
    load_dotenv()
    
    # Use a public competition form that doesn't require login
    # Note: This URL should point to a real, working entry form
    target_url = "https://gleam.io/kgvZb/xbox-series-x-giveaway-july-2025"
    
    logger.info(f"Using public competition form: {target_url}")
    
    # Initialize the auto-entry system (visible browser for debugging)
    headless = False
    auto_entry = CompetitionAutoEntry(config_path="config/config.json", headless=headless)
    
    try:
        # Initialize the browser
        await auto_entry.initialize()
        
        # Enter the competition
        logger.info(f"Attempting to enter competition at: {target_url}")
        success = await auto_entry.enter_competition(target_url, needs_auth=False)
        
        if success:
            logger.info("✓ Competition entry successful!")
        else:
            logger.warning("✗ Competition entry failed")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        await auto_entry.close()

if __name__ == "__main__":
    asyncio.run(run_test())
