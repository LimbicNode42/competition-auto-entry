"""
Competition Entry Tracker
Tracks successful and failed competition entries to prevent duplicates and improve system.
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ..utils.logger import setup_logging

logger = setup_logging()


class EntryStatus(Enum):
    """Status of competition entry."""
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    INELIGIBLE = "ineligible"


@dataclass
class EntryRecord:
    """Record of a competition entry attempt."""
    url: str
    title: str
    timestamp: str
    status: EntryStatus
    reason: Optional[str] = None
    form_data_hash: Optional[str] = None
    confirmation: Optional[str] = None
    source: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EntryRecord':
        """Create from dictionary."""
        data['status'] = EntryStatus(data['status'])
        return cls(**data)


class EntryTracker:
    """Tracks competition entries to prevent duplicates and analyze failures."""
    
    def __init__(self, database_path: str = "data/entry_tracker.db"):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize the database tables."""
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            
            # Create entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    form_data_hash TEXT,
                    confirmation TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entries_url 
                ON entries(url)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entries_status 
                ON entries(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entries_timestamp 
                ON entries(timestamp)
            """)
            
            # Create failure patterns table for analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failure_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def has_entered_competition(self, url: str) -> bool:
        """Check if we've already successfully entered this competition."""
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM entries 
                WHERE url = ? AND status = ?
            """, (url, EntryStatus.SUCCESS.value))
            
            count = cursor.fetchone()[0]
            return count > 0
    
    def record_entry(self, record: EntryRecord) -> None:
        """Record a competition entry attempt."""
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO entries (
                    url, title, timestamp, status, reason, 
                    form_data_hash, confirmation, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.url,
                record.title,
                record.timestamp,
                record.status.value,
                record.reason,
                record.form_data_hash,
                record.confirmation,
                record.source
            ))
            
            # Update failure patterns if this was a failure
            if record.status == EntryStatus.FAILED and record.reason:
                self._update_failure_pattern(record.reason, cursor)
            
            conn.commit()
            
        logger.info(f"Recorded entry: {record.status.value} for {record.title}")
    
    def _update_failure_pattern(self, reason: str, cursor) -> None:
        """Update failure pattern statistics."""
        # Extract pattern type from reason
        pattern_type = "general"
        if "form" in reason.lower():
            pattern_type = "form_error"
        elif "authentication" in reason.lower() or "login" in reason.lower():
            pattern_type = "auth_error"
        elif "captcha" in reason.lower():
            pattern_type = "captcha_error"
        elif "timeout" in reason.lower():
            pattern_type = "timeout_error"
        elif "eligibility" in reason.lower():
            pattern_type = "eligibility_error"
        
        # Check if pattern exists
        cursor.execute("""
            SELECT id, failure_count FROM failure_patterns 
            WHERE pattern_type = ? AND pattern_value = ?
        """, (pattern_type, reason))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing pattern
            cursor.execute("""
                UPDATE failure_patterns 
                SET failure_count = failure_count + 1, last_seen = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (result[0],))
        else:
            # Insert new pattern
            cursor.execute("""
                INSERT INTO failure_patterns (pattern_type, pattern_value)
                VALUES (?, ?)
            """, (pattern_type, reason))
    
    def get_entry_stats(self, days: int = 7) -> Dict:
        """Get entry statistics for the last N days."""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            
            # Get overall stats
            cursor.execute("""
                SELECT status, COUNT(*) FROM entries 
                WHERE timestamp >= ? 
                GROUP BY status
            """, (since_date,))
            
            status_counts = dict(cursor.fetchall())
            
            # Get daily stats
            cursor.execute("""
                SELECT DATE(timestamp) as day, status, COUNT(*) 
                FROM entries 
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp), status
                ORDER BY day DESC
            """, (since_date,))
            
            daily_stats = {}
            for day, status, count in cursor.fetchall():
                if day not in daily_stats:
                    daily_stats[day] = {}
                daily_stats[day][status] = count
            
            # Get top failure reasons
            cursor.execute("""
                SELECT pattern_value, failure_count 
                FROM failure_patterns 
                ORDER BY failure_count DESC 
                LIMIT 10
            """, )
            
            top_failures = dict(cursor.fetchall())
            
            return {
                'total_entries': sum(status_counts.values()),
                'status_breakdown': status_counts,
                'daily_stats': daily_stats,
                'top_failure_reasons': top_failures,
                'period_days': days
            }
    
    def get_successful_entries(self, days: int = 30) -> List[EntryRecord]:
        """Get successful entries from the last N days."""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, title, timestamp, status, reason, 
                       form_data_hash, confirmation, source
                FROM entries 
                WHERE status = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (EntryStatus.SUCCESS.value, since_date))
            
            records = []
            for row in cursor.fetchall():
                record = EntryRecord(
                    url=row[0],
                    title=row[1],
                    timestamp=row[2],
                    status=EntryStatus(row[3]),
                    reason=row[4],
                    form_data_hash=row[5],
                    confirmation=row[6],
                    source=row[7]
                )
                records.append(record)
            
            return records
    
    def get_failed_entries(self, days: int = 7) -> List[EntryRecord]:
        """Get failed entries from the last N days for analysis."""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, title, timestamp, status, reason, 
                       form_data_hash, confirmation, source
                FROM entries 
                WHERE status = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (EntryStatus.FAILED.value, since_date))
            
            records = []
            for row in cursor.fetchall():
                record = EntryRecord(
                    url=row[0],
                    title=row[1],
                    timestamp=row[2],
                    status=EntryStatus(row[3]),
                    reason=row[4],
                    form_data_hash=row[5],
                    confirmation=row[6],
                    source=row[7]
                )
                records.append(record)
            
            return records
    
    def cleanup_old_entries(self, keep_days: int = 90) -> int:
        """Clean up old entries to keep database size manageable."""
        cutoff_date = (datetime.now() - timedelta(days=keep_days)).isoformat()
        
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            
            # Count entries to be deleted
            cursor.execute("""
                SELECT COUNT(*) FROM entries WHERE timestamp < ?
            """, (cutoff_date,))
            count_to_delete = cursor.fetchone()[0]
            
            # Delete old entries
            cursor.execute("""
                DELETE FROM entries WHERE timestamp < ?
            """, (cutoff_date,))
            
            conn.commit()
            
        logger.info(f"Cleaned up {count_to_delete} old entries (older than {keep_days} days)")
        return count_to_delete
    
    def export_entries(self, output_path: str, days: int = 30) -> None:
        """Export entries to JSON file for backup/analysis."""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.database_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, title, timestamp, status, reason, 
                       form_data_hash, confirmation, source
                FROM entries 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (since_date,))
            
            entries = []
            for row in cursor.fetchall():
                record = EntryRecord(
                    url=row[0],
                    title=row[1],
                    timestamp=row[2],
                    status=EntryStatus(row[3]),
                    reason=row[4],
                    form_data_hash=row[5],
                    confirmation=row[6],
                    source=row[7]
                )
                entries.append(record.to_dict())
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump({
                'export_date': datetime.now().isoformat(),
                'period_days': days,
                'total_entries': len(entries),
                'entries': entries
            }, f, indent=2)
        
        logger.info(f"Exported {len(entries)} entries to {output_file}")
    
    def generate_hash(self, form_data: Dict) -> str:
        """Generate a hash of form data for duplicate detection."""
        # Sort keys to ensure consistent hashing
        sorted_data = json.dumps(form_data, sort_keys=True)
        return hashlib.md5(sorted_data.encode()).hexdigest()
