#!/usr/bin/env python3
"""
Simple example script showing how to use the competition auto-entry system.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_logging
from src.utils.config import AppConfig, PersonalInfo, SocialMediaCredentials
from src.core.competition import Competition
from src.core.tracker import CompetitionTracker

async def example_usage():
    """Example of how to use the competition system."""
    
    # Setup logging
    logger = setup_logging(log_level="INFO")
    
    # Create a sample configuration
    personal_info = PersonalInfo(
        first_name="John",
        last_name="Doe", 
        email="john.doe@example.com",
        phone="+1-555-123-4567",
        city="New York",
        state="NY",
        country="United States"
    )
    
    social_media = SocialMediaCredentials()
    
    config = AppConfig(
        personal_info=personal_info,
        social_media=social_media,
        max_daily_entries=5
    )
    
    # Initialize tracker
    tracker = CompetitionTracker("data/example_competitions.db")
    
    # Create a sample competition
    sample_competition = Competition(
        url="https://example.com/competition",
        title="Sample Free Competition",
        source="Example Site",
        description="This is a sample free competition for testing purposes."
    )
    
    # Save the competition
    await tracker.save_competition(sample_competition)
    logger.info(f"Saved sample competition: {sample_competition.title}")
    
    # Get statistics
    stats = await tracker.get_entry_statistics()
    logger.info(f"Competition statistics: {stats}")
    
    logger.info("✅ Example completed successfully!")
    logger.info("To run the full system, configure config/config.json and run main.py")

if __name__ == "__main__":
    asyncio.run(example_usage())
