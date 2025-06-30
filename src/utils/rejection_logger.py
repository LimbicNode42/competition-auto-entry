"""
Rejection logging utilities for tracking why competitions are not entered.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from .logger import setup_logging

logger = setup_logging()


class RejectionLogger:
    """
    Logs detailed information about why competitions are rejected.
    """
    
    def __init__(self, log_file_path: str, clear_on_init: bool = False):
        """
        Initialize the rejection logger.
        
        Args:
            log_file_path: Path to the JSON log file
            clear_on_init: Whether to clear the log file on initialization
        """
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or clear log file
        if clear_on_init or not self.log_file_path.exists():
            self._write_log_data([])
    
    def log_rejection(
        self,
        url: str,
        title: str,
        reason: str,
        reason_type: str,
        page_text_sample: str = "",
        source: str = "",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a competition rejection with detailed information.
        
        Args:
            url: Competition URL
            title: Competition title
            reason: Detailed reason for rejection
            reason_type: Type of rejection (paid_detection, age_restriction, etc.)
            page_text_sample: Sample of the page text that triggered rejection
            source: Source aggregator site
            additional_data: Any additional metadata
        """
        try:
            # Load existing data
            existing_data = self._read_log_data()
            
            # Create rejection entry
            rejection_entry = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "title": title,
                "reason": reason,
                "reason_type": reason_type,
                "page_text_sample": page_text_sample[:500],  # Limit length
                "source": source,
                "reviewed": False,  # Flag for manual review
                "feedback": None,  # For manual feedback
                "additional_data": additional_data or {}
            }
            
            # Add to existing data
            existing_data.append(rejection_entry)
            
            # Write back to file
            self._write_log_data(existing_data)
            
            logger.debug(f"Logged rejection for {url}: {reason}")
            
        except Exception as e:
            logger.error(f"Error logging rejection for {url}: {e}")
    
    def log_paid_detection_rejection(
        self,
        url: str,
        title: str,
        detection_reason: str,
        page_text: str,
        terms_text: str = "",
        source: str = ""
    ) -> None:
        """
        Log a rejection specifically due to paid competition detection.
        
        Args:
            url: Competition URL
            title: Competition title  
            detection_reason: Specific reason from is_free_competition function
            page_text: Full page text analyzed
            terms_text: Terms and conditions text
            source: Source aggregator site
        """
        # Extract relevant text samples around detected keywords
        page_sample = self._extract_relevant_text_sample(page_text, detection_reason)
        
        additional_data = {
            "page_text_length": len(page_text),
            "terms_text_length": len(terms_text),
            "has_terms": bool(terms_text.strip())
        }
        
        self.log_rejection(
            url=url,
            title=title,
            reason=detection_reason,
            reason_type="paid_detection",
            page_text_sample=page_sample,
            source=source,
            additional_data=additional_data
        )
    
    def get_rejection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about rejections.
        
        Returns:
            Dictionary with rejection statistics
        """
        try:
            data = self._read_log_data()
            
            total_rejections = len(data)
            reason_types = {}
            reviewed_count = 0
            feedback_count = 0
            
            for entry in data:
                reason_type = entry.get("reason_type", "unknown")
                reason_types[reason_type] = reason_types.get(reason_type, 0) + 1
                
                if entry.get("reviewed", False):
                    reviewed_count += 1
                
                if entry.get("feedback"):
                    feedback_count += 1
            
            return {
                "total_rejections": total_rejections,
                "reason_types": reason_types,
                "reviewed_count": reviewed_count,
                "feedback_count": feedback_count,
                "review_percentage": (reviewed_count / total_rejections * 100) if total_rejections > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting rejection stats: {e}")
            return {}
    
    def get_unreviewed_rejections(self, limit: int = 10) -> list:
        """
        Get unreviewed rejections for manual review.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of unreviewed rejection entries
        """
        try:
            data = self._read_log_data()
            unreviewed = [entry for entry in data if not entry.get("reviewed", False)]
            return unreviewed[-limit:]  # Return most recent
            
        except Exception as e:
            logger.error(f"Error getting unreviewed rejections: {e}")
            return []
    
    def mark_reviewed(self, url: str, feedback: str = None) -> bool:
        """
        Mark a rejection as reviewed with optional feedback.
        
        Args:
            url: Competition URL to mark as reviewed
            feedback: Optional feedback about the rejection accuracy
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            data = self._read_log_data()
            
            for entry in data:
                if entry.get("url") == url:
                    entry["reviewed"] = True
                    entry["review_timestamp"] = datetime.now().isoformat()
                    if feedback:
                        entry["feedback"] = feedback
                    break
            
            self._write_log_data(data)
            return True
            
        except Exception as e:
            logger.error(f"Error marking {url} as reviewed: {e}")
            return False
    
    def clear_log(self) -> None:
        """
        Clear all entries from the rejection log.
        """
        try:
            self._write_log_data([])
            logger.info("Rejection log cleared")
        except Exception as e:
            logger.error(f"Error clearing rejection log: {e}")
    
    def _read_log_data(self) -> list:
        """Read the log data from file."""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _write_log_data(self, data: list) -> None:
        """Write log data to file."""
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _extract_relevant_text_sample(self, text: str, detection_reason: str) -> str:
        """
        Extract relevant text sample around the detected keywords.
        
        Args:
            text: Full text
            detection_reason: Detection reason containing keywords
            
        Returns:
            Relevant text sample
        """
        # Extract keywords from detection reason
        keywords = []
        if "Found strong paid indicator:" in detection_reason:
            keyword = detection_reason.split("'")[1] if "'" in detection_reason else ""
            if keyword:
                keywords.append(keyword)
        elif "Currency" in detection_reason and "found in payment context" in detection_reason:
            # Already has context in the reason
            return detection_reason.split("Context: '")[1].split("'")[0] if "Context: '" in detection_reason else text[:500]
        elif "Found weak paid indicator" in detection_reason:
            keyword = detection_reason.split("'")[1] if "'" in detection_reason else ""
            if keyword:
                keywords.append(keyword)
        
        # Find and extract context around keywords
        text_lower = text.lower()
        samples = []
        
        for keyword in keywords:
            pos = text_lower.find(keyword.lower())
            if pos != -1:
                start = max(0, pos - 100)
                end = min(len(text), pos + 100)
                sample = text[start:end]
                samples.append(f"...{sample}...")
        
        if samples:
            return " | ".join(samples)
        else:
            return text[:500]  # Fallback to beginning of text
