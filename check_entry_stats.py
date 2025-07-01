#!/usr/bin/env python3
"""
Check Entry Tracker Statistics
Quick utility to view entry statistics and recent activity.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.entry_tracker import EntryTracker, EntryStatus
from src.utils.logger import setup_logging

logger = setup_logging()


def main():
    """Display entry tracker statistics."""
    logger.info("Entry Tracker Statistics")
    logger.info("=" * 50)
    
    try:
        tracker = EntryTracker()
        
        # Get stats for different periods
        for days in [1, 7, 30]:
            stats = tracker.get_entry_stats(days=days)
            
            logger.info(f"\nLAST {days} DAY(S)")
            logger.info("-" * 20)
            
            if stats['total_entries'] == 0:
                logger.info("No entries recorded")
                continue
            
            logger.info(f"Total entries: {stats['total_entries']}")
            
            # Status breakdown
            for status, count in stats['status_breakdown'].items():
                logger.info(f"  {status.upper()}: {count}")
            
            # Success rate
            successful = stats['status_breakdown'].get('success', 0)
            if stats['total_entries'] > 0:
                success_rate = (successful / stats['total_entries']) * 100
                logger.info(f"Success rate: {success_rate:.1f}%")
        
        # Show recent successful entries
        recent_successful = tracker.get_successful_entries(days=7)
        if recent_successful:
            logger.info(f"\nRECENT SUCCESSFUL ENTRIES ({len(recent_successful)})")
            logger.info("-" * 40)
            for entry in recent_successful[:5]:  # Show last 5
                logger.info(f"• {entry.title}")
                logger.info(f"  URL: {entry.url}")
                logger.info(f"  Time: {entry.timestamp}")
                if entry.confirmation:
                    logger.info(f"  Confirmation: {entry.confirmation}")
        
        # Show recent failures
        recent_failures = tracker.get_failed_entries(days=7)
        if recent_failures:
            logger.info(f"\nRECENT FAILED ENTRIES ({len(recent_failures)})")
            logger.info("-" * 40)
            for entry in recent_failures[:5]:  # Show last 5
                logger.info(f"• {entry.title}")
                logger.info(f"  Reason: {entry.reason}")
                logger.info(f"  Time: {entry.timestamp}")
        
        # Show top failure patterns
        stats_7day = tracker.get_entry_stats(days=7)
        if stats_7day['top_failure_reasons']:
            logger.info("\nTOP FAILURE PATTERNS (LAST 7 DAYS)")
            logger.info("-" * 40)
            for reason, count in list(stats_7day['top_failure_reasons'].items())[:5]:
                logger.info(f"• {reason}: {count} times")
    
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
