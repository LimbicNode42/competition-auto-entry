"""
Competition tracking and database operations.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from .competition import Competition, CompetitionEntry, CompetitionStatus, EntryStatus

logger = logging.getLogger("competition_auto_entry.tracker")


class CompetitionTracker:
    """Manages competition tracking and database operations."""
    
    def __init__(self, db_path: str = "data/competitions.db"):
        """
        Initialize the competition tracker.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Competitions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS competitions (
                    hash_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    description TEXT,
                    deadline TEXT,
                    status TEXT NOT NULL,
                    terms_url TEXT,
                    entry_url TEXT,
                    requirements TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    competition_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confirmation_data TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    FOREIGN KEY (competition_id) REFERENCES competitions (hash_id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitions_status ON competitions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitions_created ON competitions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_competition ON entries(competition_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    async def save_competition(self, competition: Competition) -> bool:
        """
        Save or update a competition in the database.
        
        Args:
            competition: Competition object to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            competition.updated_at = datetime.now()
            data = competition.to_dict()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if competition already exists
                cursor.execute("SELECT hash_id FROM competitions WHERE hash_id = ?", 
                             (competition.hash_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing competition
                    cursor.execute("""
                        UPDATE competitions SET
                            url = ?, title = ?, source = ?, description = ?,
                            deadline = ?, status = ?, terms_url = ?, entry_url = ?,
                            requirements = ?, updated_at = ?
                        WHERE hash_id = ?
                    """, (
                        data['url'], data['title'], data['source'], data['description'],
                        data['deadline'], data['status'], data['terms_url'], 
                        data['entry_url'], data['requirements'], data['updated_at'],
                        data['hash_id']
                    ))
                    logger.debug(f"Updated competition: {competition.title}")
                else:
                    # Insert new competition
                    cursor.execute("""
                        INSERT INTO competitions (
                            hash_id, url, title, source, description, deadline,
                            status, terms_url, entry_url, requirements, 
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['hash_id'], data['url'], data['title'], data['source'],
                        data['description'], data['deadline'], data['status'],
                        data['terms_url'], data['entry_url'], data['requirements'],
                        data['created_at'], data['updated_at']
                    ))
                    logger.debug(f"Saved new competition: {competition.title}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving competition {competition.title}: {e}")
            return False
    
    async def get_competition(self, hash_id: str) -> Optional[Competition]:
        """
        Retrieve a competition by hash ID.
        
        Args:
            hash_id: Competition hash ID
            
        Returns:
            Competition object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM competitions WHERE hash_id = ?", (hash_id,))
                row = cursor.fetchone()
                
                if row:
                    return Competition.from_dict(dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving competition {hash_id}: {e}")
            return None
    
    async def filter_eligible_competitions(
        self, 
        competitions: List[Competition], 
        max_entries: int = 10
    ) -> List[Competition]:
        """
        Filter competitions to find eligible ones for entry.
        
        Args:
            competitions: List of discovered competitions
            max_entries: Maximum number of competitions to return
            
        Returns:
            List of eligible competitions
        """
        eligible = []
        
        for competition in competitions:
            # Check if already entered
            if await self._is_already_entered(competition.hash_id):
                logger.debug(f"Already entered: {competition.title}")
                continue
            
            # Check if expired
            if competition.is_expired():
                logger.debug(f"Expired: {competition.title}")
                competition.status = CompetitionStatus.EXPIRED
                await self.save_competition(competition)
                continue
            
            # Check if eligible
            if competition.is_eligible():
                competition.status = CompetitionStatus.ELIGIBLE
                await self.save_competition(competition)
                eligible.append(competition)
                
                if len(eligible) >= max_entries:
                    break
        
        logger.info(f"Found {len(eligible)} eligible competitions")
        return eligible
    
    async def _is_already_entered(self, competition_id: str) -> bool:
        """
        Check if a competition has already been entered.
        
        Args:
            competition_id: Competition hash ID
            
        Returns:
            True if already entered, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM entries 
                    WHERE competition_id = ? AND status = ?
                """, (competition_id, EntryStatus.SUCCESS.value))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Error checking entry status for {competition_id}: {e}")
            return False
    
    async def record_entry(
        self, 
        competition: Competition, 
        success: bool, 
        confirmation_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Record a competition entry attempt.
        
        Args:
            competition: Competition that was entered
            success: Whether the entry was successful
            confirmation_data: Any confirmation data received
            error: Error message if entry failed
            
        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            entry = CompetitionEntry(
                competition_id=competition.hash_id,
                entry_date=datetime.now(),
                status=EntryStatus.SUCCESS if success else EntryStatus.FAILED,
                confirmation_data=confirmation_data or {},
                error_message=error or ""
            )
            
            # Update competition status
            competition.status = CompetitionStatus.ENTERED if success else CompetitionStatus.FAILED
            await self.save_competition(competition)
            
            # Save entry record
            data = entry.to_dict()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO entries (
                        entry_id, competition_id, entry_date, status,
                        confirmation_data, error_message, retry_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['entry_id'], data['competition_id'], data['entry_date'],
                    data['status'], data['confirmation_data'], data['error_message'],
                    data['retry_count']
                ))
                conn.commit()
            
            logger.info(f"Recorded entry for {competition.title}: {'Success' if success else 'Failed'}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording entry for {competition.title}: {e}")
            return False
    
    async def get_recent_entries(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent competition entries.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent entries with competition details
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT e.*, c.title, c.url, c.deadline, c.source
                    FROM entries e
                    JOIN competitions c ON e.competition_id = c.hash_id
                    WHERE e.entry_date > ?
                    ORDER BY e.entry_date DESC
                """, (cutoff_date.isoformat(),))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error retrieving recent entries: {e}")
            return []
    
    async def get_entry_statistics(self) -> Dict[str, Any]:
        """
        Get entry statistics and summary.
        
        Returns:
            Dictionary with various statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total competitions discovered
                cursor.execute("SELECT COUNT(*) FROM competitions")
                total_discovered = cursor.fetchone()[0]
                
                # Total entries attempted
                cursor.execute("SELECT COUNT(*) FROM entries")
                total_entries = cursor.fetchone()[0]
                
                # Successful entries
                cursor.execute("SELECT COUNT(*) FROM entries WHERE status = ?", 
                             (EntryStatus.SUCCESS.value,))
                successful_entries = cursor.fetchone()[0]
                
                # Entries in last 7 days
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                cursor.execute("SELECT COUNT(*) FROM entries WHERE entry_date > ?", (week_ago,))
                recent_entries = cursor.fetchone()[0]
                
                # Success rate
                success_rate = (successful_entries / total_entries * 100) if total_entries > 0 else 0
                
                return {
                    'total_discovered': total_discovered,
                    'total_entries': total_entries,
                    'successful_entries': successful_entries,
                    'recent_entries': recent_entries,
                    'success_rate': round(success_rate, 2)
                }
                
        except Exception as e:
            logger.error(f"Error retrieving statistics: {e}")
            return {}
    
    async def cleanup_old_data(self, days: int = 90) -> None:
        """
        Clean up old competition and entry data.
        
        Args:
            days: Number of days to retain data
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete old entries
                cursor.execute("DELETE FROM entries WHERE entry_date < ?", 
                             (cutoff_date.isoformat(),))
                entries_deleted = cursor.rowcount
                
                # Delete old competitions that haven't been entered
                cursor.execute("""
                    DELETE FROM competitions 
                    WHERE created_at < ? AND status NOT IN (?, ?)
                """, (cutoff_date.isoformat(), CompetitionStatus.ENTERED.value, 
                     CompetitionStatus.ELIGIBLE.value))
                competitions_deleted = cursor.rowcount
                
                conn.commit()
                logger.info(f"Cleaned up {entries_deleted} old entries and "
                          f"{competitions_deleted} old competitions")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
